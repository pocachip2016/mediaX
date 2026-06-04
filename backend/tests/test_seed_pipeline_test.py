"""
seed_pipeline_test.py 검증

확인 항목:
  - 15건 루트 Content (영화완전3 / 영화불완전5 / 시리즈완전2 / 시리즈불완전3 / 충돌2)
  - 시리즈 자식(시즌+에피소드) 자동 생성
  - cleanup 안전성: cp_name=TEST_PIPELINE 만 삭제
  - 불완전 영화: 주요 필드 NULL 확인
  - 충돌 영화: stored year ≠ TMDB year 확인
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.programming.metadata.models import (
    Content, ContentMetadata, ContentType, ContentStatus,
    ExternalMetaSource, ContentImage, ContentCredit,
)
from scripts.seed_pipeline_test import seed_pipeline_test, clean_pipeline_test, CP


def test_seed_counts(db):
    counts = seed_pipeline_test(db)
    assert counts["movie_complete"] == 3
    assert counts["movie_incomplete"] == 5
    assert counts["series_complete"] == 2
    assert counts["series_incomplete"] == 3
    assert counts["conflict"] == 2

    root_total = db.query(Content).filter(Content.cp_name == CP, Content.parent_id.is_(None)).count()
    assert root_total == 15, f"루트 콘텐츠 15건 기대, 실제 {root_total}건"


def test_complete_movies_have_full_metadata(db):
    seed_pipeline_test(db)
    movies = (
        db.query(Content)
        .filter(Content.cp_name == CP, Content.content_type == ContentType.movie,
                Content.status == ContentStatus.ai)
        .all()
    )
    # 완전 영화 3 + 충돌 영화 2 = staging 5건
    assert len(movies) == 5

    complete = [m for m in movies if "타임" not in m.title and "에이전트" not in m.title]
    for c in complete:
        meta = db.query(ContentMetadata).filter(ContentMetadata.content_id == c.id).first()
        assert meta is not None
        assert meta.ai_synopsis is not None, f"{c.title}: synopsis 누락"
        assert meta.ai_genre_primary is not None, f"{c.title}: genre 누락"
        assert meta.quality_score >= 90, f"{c.title}: quality_score 낮음"

        images = db.query(ContentImage).filter(ContentImage.content_id == c.id).count()
        assert images >= 1, f"{c.title}: 이미지 없음"

        credits = db.query(ContentCredit).filter(ContentCredit.content_id == c.id).count()
        assert credits >= 2, f"{c.title}: 크레딧(감독+배우) 없음"

        ext = db.query(ExternalMetaSource).filter(ExternalMetaSource.content_id == c.id).count()
        assert ext >= 1, f"{c.title}: 외부소스 없음"


def test_incomplete_movies_have_empty_fields(db):
    seed_pipeline_test(db)
    incomplete = (
        db.query(Content)
        .filter(Content.cp_name == CP, Content.content_type == ContentType.movie,
                Content.status == ContentStatus.raw)
        .all()
    )
    assert len(incomplete) == 5
    for c in incomplete:
        meta = db.query(ContentMetadata).filter(ContentMetadata.content_id == c.id).first()
        assert meta is not None
        assert meta.ai_synopsis is None, f"{c.title}: synopsis 이 비어있어야 함"
        assert meta.ai_genre_primary is None, f"{c.title}: genre 이 비어있어야 함"
        assert meta.quality_score < 15, f"{c.title}: quality_score 낮아야 함"


def test_complete_series_hierarchy(db):
    seed_pipeline_test(db)
    series_list = (
        db.query(Content)
        .filter(Content.cp_name == CP, Content.content_type == ContentType.series,
                Content.status == ContentStatus.approved)
        .all()
    )
    assert len(series_list) == 2

    for series in series_list:
        seasons = db.query(Content).filter(
            Content.parent_id == series.id, Content.content_type == ContentType.season
        ).all()
        assert len(seasons) >= 1, f"{series.title}: 시즌 없음"

        for season in seasons:
            eps = db.query(Content).filter(
                Content.parent_id == season.id, Content.content_type == ContentType.episode
            ).all()
            assert len(eps) >= 1, f"{series.title} 시즌{season.season_number}: 에피소드 없음"


def test_conflict_movies_have_year_mismatch(db):
    seed_pipeline_test(db)
    for title, stored_year, correct_year, stored_genre, correct_genre, tmdb_id, _ in [
        ("타임 루프", 2019, 2023, "COM", "THR", 1234567, ""),
        ("더블 에이전트", 2020, 2022, "ROM", "ACT", 2345678, ""),
    ]:
        c = db.query(Content).filter(Content.title == title, Content.cp_name == CP).first()
        assert c is not None, f"{title}: 충돌 콘텐츠 없음"
        assert c.production_year == stored_year, f"{title}: stored year 불일치"

        ext = db.query(ExternalMetaSource).filter(
            ExternalMetaSource.content_id == c.id,
            ExternalMetaSource.external_id == str(tmdb_id),
        ).first()
        assert ext is not None, f"{title}: TMDB 외부소스 없음"

        raw = ext.raw_json
        assert str(correct_year) in raw.get("release_date", ""), f"{title}: TMDB correct year 없음"


def test_cleanup_only_removes_test_pipeline(db):
    seed_pipeline_test(db)

    # TEST_PIPELINE 외 콘텐츠 추가 (운영 데이터 시뮬레이션)
    from api.programming.metadata.models import ContentMetadata as CM
    other = Content(title="운영 콘텐츠", content_type=ContentType.movie,
                    status=ContentStatus.approved, cp_name="REAL_CP",
                    production_year=2023, country="KR")
    db.add(other)
    db.flush()
    db.add(CM(content_id=other.id, quality_score=90.0))
    db.commit()

    deleted = clean_pipeline_test(db)
    # clean_pipeline_test은 루트 + 자식 전체 Content 건수 반환 (루트15 + 시즌/에피소드 자식)
    assert deleted >= 15, f"최소 15건 삭제 기대, 실제 {deleted}건"

    remaining_test = db.query(Content).filter(Content.cp_name == CP).count()
    assert remaining_test == 0, "TEST_PIPELINE 콘텐츠 잔존"

    surviving_real = db.query(Content).filter(Content.title == "운영 콘텐츠").first()
    assert surviving_real is not None, "운영 데이터가 삭제됨 — cleanup 버그"
