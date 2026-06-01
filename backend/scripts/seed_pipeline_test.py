"""
Pipeline Test Console 시드 스크립트 (총 15건 + 계층 자식)

cp_name='TEST_PIPELINE' 으로 격리. cleanup은 해당 cp_name 만 삭제.

카테고리:
  - 영화-완전  (3): 모든 필드 채움, ExternalMetaSource + 크레딧 + 이미지 포함
  - 영화-불완전(5): title+year 만, AI 추천 대상
  - 시리즈-완전(2): 시리즈+시즌2+에피소드(총4~2개), 완전한 계층 구조
  - 시리즈-불완전(3): 시리즈 루트만 또는 빈 시즌 껍데기
  - 충돌(2): year/genre 의도적 오류 입력 → MetadataDiffPanel conflict 검증

실행:
    cd backend && python3 scripts/seed_pipeline_test.py
    python3 scripts/seed_pipeline_test.py --clean   # 기존 TEST_PIPELINE 데이터 삭제 후 재삽입
    python3 scripts/seed_pipeline_test.py --summary # 현황만 출력
"""
import sys
import os
import argparse
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import SessionLocal, engine, Base
from api.meta_core.scoring import normalize_title
import api.programming.metadata.models  # noqa — 모든 모델 로드
# clean 시 FK 자식 테이블 전체 탐지를 위해 모든 모델 메타데이터 로드 (conftest와 동일)
import api.meta_core.models  # noqa
import api.meta_core.public_api.models  # noqa
import api.distribution.models  # noqa

from api.programming.metadata.models import (
    Content, ContentMetadata, ContentType, ContentStatus, MetaSource,
    PersonMaster, ContentCredit, CreditRole,
    ContentImage, ImageType,
    ExternalMetaSource, ExternalSourceType, ContentAIResult, AITaskType,
)
from api.programming.metadata.models.content import PipelineStage
from api.programming.metadata.models.stage_event import StageEvent

CP = "TEST_PIPELINE"
TMDB_BASE = "https://image.tmdb.org/t/p/w500"


# ─────────────────────────────────────────────────────────────────────────────
# Data definitions
# ─────────────────────────────────────────────────────────────────────────────

COMPLETE_MOVIES = [
    # (title, orig_title, year, runtime, genre_primary, genre_secondary,
    #  synopsis, tmdb_id, poster_path, director, actors)
    (
        "기생충", "Parasite", 2019, 132, "DRM", "THR",
        "전원 백수인 기택 가족이 부유한 박 사장 가족의 집에 하나둘 침투하면서 벌어지는 이야기. "
        "봉준호 감독의 걸작으로 칸 황금종려상, 아카데미 작품상 등 4관왕을 달성.",
        496243, "/7IiTTgloJzvGI1TAYymCfbfl3vT.jpg",
        ("봉준호", "Bong Joon-ho", 21879),
        [("송강호", "Song Kang-ho", 14292), ("최우식", "Choi Woo-shik", 1596804)],
    ),
    (
        "부산행", "Train to Busan", 2016, 118, "ACT", "HOR",
        "부산행 KTX에서 좀비 바이러스가 퍼지면서 생존을 위한 사투를 벌이는 사람들의 이야기. "
        "연상호 감독의 첫 실사 영화로 전 세계적 인기를 얻었다.",
        396535, "/hABCyC8sFVEEMkWDkVoZNFRGAWx.jpg",
        ("연상호", "Yeon Sang-ho", 1178162),
        [("공유", "Gong Yoo", 1029950), ("마동석", "Don Lee", 1506980)],
    ),
    (
        "서울의 봄", "12.12: The Day", 2023, 141, "HIS", "DRM",
        "1979년 12월 12일, 군사 반란을 일으킨 전두광과 이를 막으려는 이태신의 9시간을 그린 작품. "
        "황정민, 정우성 주연으로 1,300만 관객을 동원한 흥행작.",
        1165227, "/kbsD6JV1J7LvTMCfKUQH4MZbJqP.jpg",
        ("김성수", "Kim Sung-su", 184496),
        [("황정민", "Hwang Jung-min", 85576), ("정우성", "Jung Woo-sung", 68823)],
    ),
]

INCOMPLETE_MOVIES = [
    # (title, year)  — 나머지 필드 없음, AI enrich 대상
    ("어둠의 사냥꾼", 2024),
    ("봄날의 기억",   2023),
    ("레드 문",       2024),
    ("더 체이스",     2023),
    ("미스터리 X",    2024),
]

COMPLETE_SERIES = [
    # (title, year, synopsis, num_seasons, eps_per_season)
    (
        "판타지 킹덤", 2023,
        "마법이 사라진 왕국을 배경으로 선택받은 소녀가 세계를 구하기 위해 여정을 떠나는 판타지 드라마. "
        "4개국 합작으로 제작된 대형 판타지 시리즈.",
        2, 2,
    ),
    (
        "별빛 여정", 2024,
        "우주 탐험가들이 미지의 행성을 탐험하며 인류의 미래를 결정짓는 선택과 마주하는 SF 드라마.",
        1, 2,
    ),
]

INCOMPLETE_SERIES = [
    # (title, year, include_empty_season)
    ("미완성 교향곡",     2024, False),  # 시리즈 루트만
    ("더 챌린지: 미래편", 2023, True),   # 시리즈 + 빈 시즌 껍데기
    ("코드네임 제로",     2024, False),  # 시리즈 루트만
]

CONFLICT_MOVIES = [
    # (title, stored_year, correct_year, stored_genre, correct_genre, tmdb_id, tmdb_title)
    (
        "타임 루프",
        2019, 2023,       # stored=2019(오류), TMDB=2023(정답)
        "COM", "THR",     # stored=COM(오류), TMDB=THR(정답)
        1234567, "Time Loop",
    ),
    (
        "더블 에이전트",
        2020, 2022,       # stored=2020(오류), TMDB=2022(정답)
        "ROM", "ACT",     # stored=ROM(오류), TMDB=ACT(정답)
        2345678, "Double Agent",
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _find_existing_content(db, title: str, year: int | None, content_type) -> "Content | None":
    """전체 카탈로그(CP 무관)에서 동일 콘텐츠 탐색.
    영화: normalize_title 일치 + production_year ±1.
    시리즈: normalize_title 일치 (연도는 보조 — 없으면 무시).
    """
    from api.programming.metadata.models.content import ContentType as CT
    norm = normalize_title(title)
    prefix = title[:10]

    if content_type == CT.movie and year is not None:
        candidates = (
            db.query(Content)
            .filter(
                Content.content_type == content_type,
                Content.is_deleted.is_(False),
                Content.title.ilike(f"%{prefix}%"),
                Content.production_year.between(year - 1, year + 1),
            )
            .limit(20)
            .all()
        )
    else:
        candidates = (
            db.query(Content)
            .filter(
                Content.content_type == content_type,
                Content.is_deleted.is_(False),
                Content.title.ilike(f"%{prefix}%"),
            )
            .limit(20)
            .all()
        )
    for c in candidates:
        if normalize_title(c.title) == norm:
            return c
    return None


def _get_or_create_person(db, name_ko: str, name_en: str, tmdb_person_id: int) -> PersonMaster:
    p = db.query(PersonMaster).filter(PersonMaster.name_ko == name_ko).first()
    if not p:
        p = PersonMaster(name_ko=name_ko, name_en=name_en, tmdb_person_id=tmdb_person_id)
        db.add(p)
        db.flush()
    return p


# ─────────────────────────────────────────────────────────────────────────────
# Seed
# ─────────────────────────────────────────────────────────────────────────────

def seed_pipeline_test(db) -> dict:
    counts = {
        "movie_complete": 0, "movie_incomplete": 0,
        "series_complete": 0, "series_incomplete": 0, "conflict": 0,
        "skipped_in_pipeline": 0, "skipped_registered": 0,
    }

    # ── 영화-완전 ────────────────────────────────────────────────────────────
    for (title, orig, year, runtime, genre_p, genre_s, synopsis,
         tmdb_id, poster_path, director_data, actors_data) in COMPLETE_MOVIES:

        existing = _find_existing_content(db, title, year, ContentType.movie)
        if existing:
            if existing.status == ContentStatus.approved:
                counts["skipped_registered"] += 1
            else:
                counts["skipped_in_pipeline"] += 1
            continue

        c = Content(
            title=title, original_title=orig,
            content_type=ContentType.movie, status=ContentStatus.raw,
            cp_name=CP, production_year=year, runtime_minutes=runtime, country="KR",
        )
        db.add(c)
        db.flush()

        db.add(ContentMetadata(
            content_id=c.id,
            cp_synopsis=synopsis,
            ai_synopsis=synopsis,
            ai_genre_primary=genre_p, ai_genre_secondary=genre_s,
            ai_mood_tags=["검증완전", "테스트"],
            ai_rating_suggestion="15세이상관람가",
            quality_score=92.0,
            score_breakdown={"synopsis_quality": 28, "genre_confidence": 22,
                             "tag_coverage": 12, "external_meta": 20, "field_coverage": 10},
            final_synopsis=synopsis, final_genre=genre_p, final_source=MetaSource.ai,
            ai_processed_at=_now(),
        ))
        db.flush()

        db.add(ContentImage(
            content_id=c.id, image_type=ImageType.poster,
            url=f"{TMDB_BASE}{poster_path}", width=500, height=750,
            source="tmdb", is_primary=True,
        ))

        dir_name_ko, dir_name_en, dir_tmdb_id = director_data
        director = _get_or_create_person(db, dir_name_ko, dir_name_en, dir_tmdb_id)
        db.add(ContentCredit(content_id=c.id, person_id=director.id,
                             role=CreditRole.director, cast_order=0, source="tmdb"))

        for order, (a_ko, a_en, a_tmdb) in enumerate(actors_data):
            actor = _get_or_create_person(db, a_ko, a_en, a_tmdb)
            db.add(ContentCredit(content_id=c.id, person_id=actor.id,
                                 role=CreditRole.actor, cast_order=order + 1, source="tmdb"))

        db.add(ExternalMetaSource(
            content_id=c.id, source_type=ExternalSourceType.tmdb,
            external_id=str(tmdb_id), title_on_source=orig,
            raw_json={"id": tmdb_id, "original_title": orig, "release_date": f"{year}-01-01"},
            match_confidence=0.97, matched_at=_now(),
        ))
        db.flush()
        counts["movie_complete"] += 1

    # ── 영화-불완전 ──────────────────────────────────────────────────────────
    for title, year in INCOMPLETE_MOVIES:
        existing = _find_existing_content(db, title, year, ContentType.movie)
        if existing:
            if existing.status == ContentStatus.approved:
                counts["skipped_registered"] += 1
            else:
                counts["skipped_in_pipeline"] += 1
            continue

        c = Content(
            title=title, content_type=ContentType.movie,
            status=ContentStatus.raw, cp_name=CP,
            production_year=year, country="KR",
        )
        db.add(c)
        db.flush()

        db.add(ContentMetadata(
            content_id=c.id,
            cp_synopsis=None, ai_synopsis=None,
            ai_genre_primary=None, ai_mood_tags=[],
            quality_score=5.0,
            score_breakdown={"synopsis_quality": 0, "genre_confidence": 0,
                             "tag_coverage": 0, "external_meta": 0, "field_coverage": 5},
        ))
        db.flush()
        counts["movie_incomplete"] += 1

    # ── 시리즈-완전 ──────────────────────────────────────────────────────────
    for title, year, synopsis, num_seasons, eps_per_season in COMPLETE_SERIES:
        existing = _find_existing_content(db, title, year, ContentType.series)
        if existing:
            if existing.status == ContentStatus.approved:
                counts["skipped_registered"] += 1
            else:
                counts["skipped_in_pipeline"] += 1
            continue  # 시즌/에피소드 전체 스킵 (cascade)

        series = Content(
            title=title, content_type=ContentType.series,
            status=ContentStatus.raw, cp_name=CP,
            production_year=year, country="KR",
        )
        db.add(series)
        db.flush()

        db.add(ContentMetadata(
            content_id=series.id, cp_synopsis=synopsis, ai_synopsis=synopsis,
            ai_genre_primary="FAN", ai_mood_tags=["판타지", "어드벤처"],
            quality_score=91.0,
            final_synopsis=synopsis, final_source=MetaSource.ai,
            ai_processed_at=_now(),
        ))
        db.add(ContentImage(
            content_id=series.id, image_type=ImageType.poster,
            url=f"{TMDB_BASE}/test_series_{title[:4]}.jpg",
            width=500, height=750, source="cp", is_primary=True,
        ))
        db.flush()

        for sn in range(1, num_seasons + 1):
            season = Content(
                title=f"{title} 시즌 {sn}", content_type=ContentType.season,
                status=ContentStatus.raw, cp_name=CP,
                production_year=year + (sn - 1), country="KR",
                parent_id=series.id, season_number=sn,
            )
            db.add(season)
            db.flush()

            db.add(ContentMetadata(
                content_id=season.id,
                cp_synopsis=f"{title} {sn}시즌 — {synopsis[:60]}...",
                quality_score=89.0, ai_processed_at=_now(),
            ))
            db.flush()

            for ep in range(1, eps_per_season + 1):
                episode = Content(
                    title=f"{title} {ep}화", content_type=ContentType.episode,
                    status=ContentStatus.raw, cp_name=CP,
                    production_year=year, runtime_minutes=55, country="KR",
                    parent_id=season.id, season_number=sn, episode_number=ep,
                )
                db.add(episode)
                db.flush()

                db.add(ContentMetadata(
                    content_id=episode.id,
                    cp_synopsis=f"{title} {sn}시즌 {ep}화 줄거리 요약",
                    ai_synopsis=f"{title} {ep}화 — {synopsis[:50]}...",
                    quality_score=88.0, ai_processed_at=_now(),
                ))
                db.flush()

        counts["series_complete"] += 1

    # ── 시리즈-불완전 ─────────────────────────────────────────────────────────
    for title, year, include_empty_season in INCOMPLETE_SERIES:
        existing = _find_existing_content(db, title, year, ContentType.series)
        if existing:
            if existing.status == ContentStatus.approved:
                counts["skipped_registered"] += 1
            else:
                counts["skipped_in_pipeline"] += 1
            continue  # 빈 시즌 포함 전체 스킵 (cascade)

        series = Content(
            title=title, content_type=ContentType.series,
            status=ContentStatus.raw, cp_name=CP,
            production_year=year, country="KR",
        )
        db.add(series)
        db.flush()

        db.add(ContentMetadata(
            content_id=series.id, cp_synopsis=None,
            ai_synopsis=None, quality_score=3.0,
            score_breakdown={"field_coverage": 3},
        ))
        db.flush()

        if include_empty_season:
            season = Content(
                title=f"{title} 시즌 1", content_type=ContentType.season,
                status=ContentStatus.raw, cp_name=CP,
                production_year=year, country="KR",
                parent_id=series.id, season_number=1,
            )
            db.add(season)
            db.flush()

            db.add(ContentMetadata(
                content_id=season.id, cp_synopsis=None, quality_score=0.0,
            ))
            db.flush()

        counts["series_incomplete"] += 1

    # ── 충돌 ─────────────────────────────────────────────────────────────────
    for (title, stored_year, correct_year, stored_genre,
         correct_genre, tmdb_id, tmdb_title) in CONFLICT_MOVIES:

        existing = _find_existing_content(db, title, stored_year, ContentType.movie)
        if existing:
            if existing.status == ContentStatus.approved:
                counts["skipped_registered"] += 1
            else:
                counts["skipped_in_pipeline"] += 1
            continue

        c = Content(
            title=title, content_type=ContentType.movie,
            status=ContentStatus.raw, cp_name=CP,
            production_year=stored_year,   # 오류 연도 의도적 입력
            country="KR",
        )
        db.add(c)
        db.flush()

        db.add(ContentMetadata(
            content_id=c.id,
            cp_synopsis=f"{title} — CP 제공 시놉시스 (연도/장르 불일치)",
            ai_synopsis=None,
            ai_genre_primary=None,
            ai_mood_tags=[],
            quality_score=2.0,
            ai_processed_at=None,
        ))

        # TMDB 데이터는 올바른 값 (conflict 발생)
        db.add(ExternalMetaSource(
            content_id=c.id, source_type=ExternalSourceType.tmdb,
            external_id=str(tmdb_id), title_on_source=tmdb_title,
            raw_json={
                "id": tmdb_id,
                "original_title": tmdb_title,
                "release_date": f"{correct_year}-06-15",
                "genres": [{"id": 53, "name": correct_genre}],
            },
            match_confidence=0.85, matched_at=_now(),
        ))
        db.flush()
        counts["conflict"] += 1

    # 위치(stage) 초기화: 시드 콘텐츠는 S1에서 시작 (status=raw, 완료 축과 분리).
    # current_stage(위치)와 status(완료)는 두 축 — 시드는 S1 위치·미완료(raw) 상태.
    for c in db.query(Content).filter(
        Content.cp_name == CP, Content.current_stage.is_(None)
    ).all():
        c.current_stage = PipelineStage.S1_INTAKE

    db.commit()
    return counts


# ─────────────────────────────────────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────────────────────────────────────

def clean_pipeline_test(db, dry_run: bool = False) -> int:
    """cp_name='TEST_PIPELINE' 인 Content 와 연관 레코드만 삭제."""
    ids = [r.id for r in db.query(Content.id).filter(Content.cp_name == CP).all()]
    if not ids:
        return 0
    if dry_run:
        print(f"[dry-run] 삭제 예정: {len(ids)}건 (id={ids[:5]}...)")
        return len(ids)

    # contents.id를 참조하는 모든 자식 테이블에서 행 삭제 — FK 메타데이터 기반 동적 처리.
    # 하드코딩 목록은 처리/advance로 새 자식(genres/tags/stage_event 등)이 생기면 FK 위반으로
    # clean이 통째로 롤백돼 재시드가 S1로 리셋되지 않는 문제를 유발 → 동적 탐지로 견고화.
    contents_table = Content.__table__
    for table in reversed(Base.metadata.sorted_tables):
        if table is contents_table:
            continue
        fk_cols = {fk.parent.name for fk in table.foreign_keys
                   if fk.column.table is contents_table}
        for col in fk_cols:
            db.execute(table.delete().where(table.c[col].in_(ids)))

    # Content는 parent_id 자기참조 FK → 자식(season/episode) 먼저
    db.query(Content).filter(
        Content.parent_id.in_(ids), Content.cp_name == CP
    ).delete(synchronize_session=False)
    db.query(Content).filter(Content.cp_name == CP).delete(synchronize_session=False)

    db.commit()
    return len(ids)


def clean_by_ids(db, ids: list[int], dry_run: bool = False) -> int:
    """특정 ID 목록만 삭제 — stage-based cleanup. CP 무관.
    clean_pipeline_test와 동일한 FK-safe 동적 삭제 로직 사용.
    """
    if not ids:
        return 0
    if dry_run:
        return len(ids)

    contents_table = Content.__table__
    for table in reversed(Base.metadata.sorted_tables):
        if table is contents_table:
            continue
        fk_cols = {fk.parent.name for fk in table.foreign_keys
                   if fk.column.table is contents_table}
        for col in fk_cols:
            db.execute(table.delete().where(table.c[col].in_(ids)))

    # parent_id 자기참조 FK — 자식(season/episode) 먼저 삭제
    db.query(Content).filter(Content.parent_id.in_(ids)).delete(synchronize_session=False)
    db.query(Content).filter(Content.id.in_(ids)).delete(synchronize_session=False)

    db.commit()
    return len(ids)


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

def print_summary(db):
    rows = db.query(Content).filter(Content.cp_name == CP).all()
    total = len(rows)
    by_status = {}
    by_type = {}
    for r in rows:
        by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        by_type[r.content_type.value] = by_type.get(r.content_type.value, 0) + 1

    print(f"\n=== TEST_PIPELINE 시드 현황 ===")
    print(f"  전체: {total}건")
    print(f"  타입: {by_type}")
    print(f"  상태: {by_status}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline Test 시드 스크립트")
    parser.add_argument("--clean",   action="store_true", help="기존 TEST_PIPELINE 데이터 삭제 후 재삽입")
    parser.add_argument("--summary", action="store_true", help="현황만 출력")
    parser.add_argument("--dry-run", action="store_true", help="cleanup dry-run (삭제 없이 건수만 확인)")
    args = parser.parse_args()

    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if args.summary:
            print_summary(db)
        elif args.dry_run:
            n = clean_pipeline_test(db, dry_run=True)
            print(f"dry-run: {n}건 삭제 예정")
        else:
            if args.clean:
                n = clean_pipeline_test(db)
                print(f"✓ 기존 TEST_PIPELINE 데이터 {n}건 삭제 완료")
            counts = seed_pipeline_test(db)
            total = sum(counts.values())
            print(f"✓ 시드 완료 — {counts} (총 루트 {total}건)")
            print_summary(db)
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()
