"""
1.1 메타데이터 서비스 단위 테스트 — SQLite in-memory
"""
import pytest

from api.programming.metadata.schemas import ContentCreate
from api.programming.metadata.service import (
    create_content,
    get_service_readiness,
    bulk_complete_video_meta,
    suggest_text_meta,
)
from api.programming.metadata.models import (
    Content,
    ContentMetadata,
    ContentType,
    ContentStatus,
    ExternalMetaSource,
    ExternalSourceType,
)


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def _make_content(db, title="테스트 영화", content_type=ContentType.movie):
    data = ContentCreate(title=title, content_type=content_type)
    return create_content(db, data)


# ── 테스트 1: create_content ───────────────────────────────────────────────────

def test_create_content(db):
    """Content 생성 시 ContentMetadata 레코드가 함께 초기화된다."""
    content = _make_content(db, title="신작 영화")

    assert content.id is not None
    assert content.title == "신작 영화"
    assert content.status == ContentStatus.waiting

    meta = db.query(ContentMetadata).filter_by(content_id=content.id).first()
    assert meta is not None
    assert meta.quality_score == 0.0


# ── 테스트 2: get_service_readiness_rates ────────────────────────────────────

def test_get_service_readiness_rates(db):
    """완료 콘텐츠 비율이 정확히 계산된다 (0%, 50%, 100% 케이스)."""
    # 콘텐츠 2개 생성
    c1 = _make_content(db, "A")
    c2 = _make_content(db, "B")

    # 초기 — 모두 0%
    stats = get_service_readiness(db)
    assert stats.total == 2
    assert stats.text_rate == 0.0
    assert stats.image_rate == 0.0
    assert stats.video_rate == 0.0
    assert stats.all_rate == 0.0

    # c1 글자메타 완료
    m1 = db.query(ContentMetadata).filter_by(content_id=c1.id).first()
    m1.text_meta_completed = True
    db.commit()

    stats = get_service_readiness(db)
    assert stats.text_completed == 1
    assert stats.text_rate == 50.0

    # c1, c2 모두 글자+이미지+영상 완료
    m2 = db.query(ContentMetadata).filter_by(content_id=c2.id).first()
    for m in (m1, m2):
        m.text_meta_completed = True
        m.image_meta_completed = True
        m.video_meta_completed = True
    db.commit()

    stats = get_service_readiness(db)
    assert stats.text_rate == 100.0
    assert stats.image_rate == 100.0
    assert stats.video_rate == 100.0
    assert stats.all_rate == 100.0
    assert stats.all_completed == 2


# ── 테스트 3: bulk_complete_video_meta_guard ─────────────────────────────────

def test_bulk_complete_video_meta_guard(db):
    """해상도·코덱 미입력 콘텐츠는 skipped에 포함되고 완료 처리되지 않는다."""
    c_ok = _make_content(db, "해상도 있음")
    c_no = _make_content(db, "해상도 없음")

    # c_ok 만 해상도·코덱 입력
    m_ok = db.query(ContentMetadata).filter_by(content_id=c_ok.id).first()
    m_ok.video_resolution = "1920x1080"
    m_ok.codec_video = "H.264"
    db.commit()

    result = bulk_complete_video_meta(db, [c_ok.id, c_no.id])

    assert result["updated"] == 1
    assert c_no.id in result["skipped"]
    assert c_ok.id not in result["skipped"]

    m_ok_after = db.query(ContentMetadata).filter_by(content_id=c_ok.id).first()
    m_no_after = db.query(ContentMetadata).filter_by(content_id=c_no.id).first()
    assert m_ok_after.video_meta_completed is True
    assert not m_no_after.video_meta_completed


# ── 테스트 4: suggest_text_meta — TMDB 우선 ──────────────────────────────────

def test_suggest_text_meta_tmdb_priority(db):
    """TMDB 소스가 있으면 KOBIS보다 먼저 반환되고, source='tmdb' 이다."""
    content = _make_content(db, "TMDB 영화")

    # TMDB 소스 추가
    tmdb_src = ExternalMetaSource(
        content_id=content.id,
        source_type=ExternalSourceType.tmdb,
        external_id="12345",
        raw_json={
            "overview": "TMDB 시놉시스",
            "genres": [{"id": 28, "name": "액션"}, {"id": 35, "name": "코미디"}],
        },
    )
    # KOBIS 소스도 추가 (우선순위 낮음)
    kobis_src = ExternalMetaSource(
        content_id=content.id,
        source_type=ExternalSourceType.kobis,
        external_id="K999",
        raw_json={"movieInfo": {"genreAlt": "드라마"}},
    )
    db.add_all([tmdb_src, kobis_src])
    db.commit()

    suggestion = suggest_text_meta(db, content.id)

    assert suggestion is not None
    assert suggestion.source == "tmdb"
    assert suggestion.synopsis == "TMDB 시놉시스"
    assert suggestion.genre_primary == "액션"
    assert suggestion.genre_secondary == "코미디"
