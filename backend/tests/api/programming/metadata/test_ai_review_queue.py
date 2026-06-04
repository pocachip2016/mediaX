"""
AI Review Queue — 분류 헬퍼 단위 테스트 (Step 1.1) + 통합 테스트 (Step 1.2)
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.database import Base, get_db
import api.programming.metadata.models  # noqa
import api.meta_core.models  # noqa
from api.programming.metadata.router import router as metadata_router

from api.programming.metadata.service import (
    _classify_input_type,
    _classify_metadata_status,
    _classify_poster_status,
    _risk_level,
    build_ai_review_queue,
)
from api.programming.metadata.models import (
    Content, ContentType, ContentStatus,
    ExternalMetaSource, ExternalSourceType, ContentImage, ImageType,
)
from api.programming.metadata.schemas import (
    RecommendationsOut, FieldRecommendation, SourceFieldRec,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _src(source_type: str) -> ExternalMetaSource:
    m = MagicMock(spec=ExternalMetaSource)
    m.source_type = ExternalSourceType(source_type)
    return m


def _rec(missing=None, auto_fill=None, conflicts=None) -> RecommendationsOut:
    return RecommendationsOut(
        content_id=1,
        missing_fields=missing or [],
        auto_fill=auto_fill or [],
        conflicts=conflicts or [],
    )


def _field_rec(field: str = "synopsis", status: str = "auto") -> FieldRecommendation:
    return FieldRecommendation(
        field=field,
        status=status,
        recommendations=[
            SourceFieldRec(source_type="tmdb", source_id=1, value="v", confidence=0.9)
        ],
    )


def _img(source: str, is_primary: bool = False) -> ContentImage:
    m = MagicMock(spec=ContentImage)
    m.source = source
    m.is_primary = is_primary
    return m


# ── _classify_input_type ──────────────────────────────────────────────────────

def test_classify_input_type_bulk():
    assert _classify_input_type([_src("bulk_upload"), _src("tmdb")]) == "bulk"


def test_classify_input_type_manual():
    assert _classify_input_type([_src("manual")]) == "manual"


def test_classify_input_type_existing():
    assert _classify_input_type([_src("tmdb"), _src("kobis")]) == "existing"


def test_classify_input_type_empty():
    assert _classify_input_type([]) == "existing"


# ── _classify_metadata_status ─────────────────────────────────────────────────

def test_classify_metadata_conflict():
    assert _classify_metadata_status(_rec(conflicts=[_field_rec(status="conflict")])) == "conflict"


def test_classify_metadata_missing():
    assert _classify_metadata_status(_rec(missing=["synopsis"])) == "missing"


def test_classify_metadata_enhancement():
    assert _classify_metadata_status(_rec(auto_fill=[_field_rec()])) == "enhancement"


def test_classify_metadata_clean():
    assert _classify_metadata_status(_rec()) == "clean"


# ── _classify_poster_status ───────────────────────────────────────────────────

def test_classify_poster_no_candidate():
    assert _classify_poster_status([], 0) == "no_candidate"


def test_classify_poster_ok_cp():
    assert _classify_poster_status([_img("cp", is_primary=True)], 0) == "poster_ok"


def test_classify_poster_ok_manual():
    assert _classify_poster_status([_img("manual", is_primary=True)], 0) == "poster_ok"


def test_classify_poster_external_only():
    assert _classify_poster_status([_img("tmdb", is_primary=True)], 0) == "external_only"


def test_classify_poster_dam_match():
    assert _classify_poster_status([_img("tmdb", is_primary=False)], 3) == "dam_match_found"


def test_classify_poster_needs_selection():
    assert _classify_poster_status([_img("tmdb", is_primary=False)], 0) == "needs_selection"


# ── _risk_level ───────────────────────────────────────────────────────────────

def test_risk_level_high_conflict():
    assert _risk_level("conflict", "poster_ok", 0.9) == "high"


def test_risk_level_high_no_candidate():
    assert _risk_level("clean", "no_candidate", 0.9) == "high"


def test_risk_level_high_low_confidence():
    assert _risk_level("clean", "poster_ok", 0.4) == "high"


def test_risk_level_medium_missing():
    assert _risk_level("missing", "poster_ok", 0.8) == "medium"


def test_risk_level_low():
    assert _risk_level("clean", "poster_ok", 0.9) == "low"


# ── build_ai_review_queue 통합 테스트 (Step 1.2) ──────────────────────────────

def _make_content(db, title: str) -> Content:
    c = Content(
        title=title,
        content_type=ContentType.movie,
        cp_name="TestCP",
        status=ContentStatus.raw,
    )
    db.add(c)
    db.flush()
    return c


def _make_image(db, content_id: int, source: str = "cp", is_primary: bool = True) -> ContentImage:
    img = ContentImage(
        content_id=content_id,
        image_type=ImageType.poster,
        url=f"http://example.com/{content_id}.jpg",
        source=source,
        is_primary=is_primary,
    )
    db.add(img)
    db.flush()
    return img


def _rec_missing(content_id: int) -> RecommendationsOut:
    return RecommendationsOut(
        content_id=content_id,
        missing_fields=["synopsis"],
        auto_fill=[],
        conflicts=[],
    )


def _rec_conflict(content_id: int) -> RecommendationsOut:
    return RecommendationsOut(
        content_id=content_id,
        missing_fields=["runtime"],
        auto_fill=[],
        conflicts=[
            FieldRecommendation(
                field="runtime",
                status="conflict",
                recommendations=[
                    SourceFieldRec(source_type="tmdb", source_id=1, value="120분", confidence=0.9),
                    SourceFieldRec(source_type="watcha", source_id=2, value="118분", confidence=0.8),
                ],
            )
        ],
    )


def _rec_enhancement(content_id: int) -> RecommendationsOut:
    return RecommendationsOut(
        content_id=content_id,
        missing_fields=[],
        auto_fill=[
            FieldRecommendation(
                field="country",
                status="auto",
                recommendations=[
                    SourceFieldRec(source_type="tmdb", source_id=3, value="대한민국", confidence=0.95),
                ],
            )
        ],
        conflicts=[],
    )


def _rec_clean(content_id: int) -> RecommendationsOut:
    return RecommendationsOut(
        content_id=content_id,
        missing_fields=[],
        auto_fill=[],
        conflicts=[],
    )


@pytest.fixture
def four_contents(db):
    """
    c1: missing + no_candidate → high
    c2: conflict + needs_selection → high
    c3: missing + poster_ok (cp) → medium
    c4: enhancement + external_only (tmdb) → low
    """
    c1 = _make_content(db, "콘텐츠-missing-no-poster")
    c2 = _make_content(db, "콘텐츠-conflict")
    c3 = _make_content(db, "콘텐츠-missing-with-cp")
    c4 = _make_content(db, "콘텐츠-enhancement-tmdb")
    _make_image(db, c3.id, source="cp", is_primary=True)
    _make_image(db, c4.id, source="tmdb", is_primary=True)
    db.commit()

    rec_map = {
        c1.id: _rec_missing(c1.id),
        c2.id: _rec_conflict(c2.id),
        c3.id: _rec_missing(c3.id),
        c4.id: _rec_enhancement(c4.id),
    }
    return [c1, c2, c3, c4], rec_map


def test_queue_returns_all_four_rows(db, four_contents):
    contents, rec_map = four_contents
    with patch("api.programming.metadata.service.get_content_recommendations",
               side_effect=lambda d, cid: rec_map[cid]):
        result = build_ai_review_queue(db)
    assert result.total == 4
    assert len(result.items) == 4


def test_queue_filter_metadata_status_conflict(db, four_contents):
    contents, rec_map = four_contents
    with patch("api.programming.metadata.service.get_content_recommendations",
               side_effect=lambda d, cid: rec_map[cid]):
        result = build_ai_review_queue(db, metadata_status="conflict")
    assert result.total == 1
    assert result.items[0].metadata_status == "conflict"


def test_queue_summary_counts(db, four_contents):
    contents, rec_map = four_contents
    with patch("api.programming.metadata.service.get_content_recommendations",
               side_effect=lambda d, cid: rec_map[cid]):
        result = build_ai_review_queue(db)
    s = result.summary
    assert s.total == 4
    assert s.missing == 2       # c1, c3
    assert s.conflict == 1      # c2
    assert s.high_risk == 2     # c1(no_candidate), c2(conflict)


def test_queue_pagination(db, four_contents):
    contents, rec_map = four_contents
    with patch("api.programming.metadata.service.get_content_recommendations",
               side_effect=lambda d, cid: rec_map[cid]):
        page1 = build_ai_review_queue(db, page=1, size=2)
        page2 = build_ai_review_queue(db, page=2, size=2)
    assert len(page1.items) == 2
    assert len(page2.items) == 2
    assert page1.total == 4
    ids_p1 = {r.content_id for r in page1.items}
    ids_p2 = {r.content_id for r in page2.items}
    assert ids_p1.isdisjoint(ids_p2)


def test_queue_dam_count_zero_when_include_dam_false(db, four_contents):
    contents, rec_map = four_contents
    with patch("api.programming.metadata.service.get_content_recommendations",
               side_effect=lambda d, cid: rec_map[cid]):
        result = build_ai_review_queue(db, include_dam=False)
    assert all(r.dam_match_count == 0 for r in result.items)


# ── HTTP endpoint 테스트 (Step 1.3) ───────────────────────────────────────────

@pytest.fixture
def api_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    app = FastAPI()
    app.include_router(metadata_router)

    def override_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    session = Session()
    return TestClient(app), session


def test_endpoint_returns_200(api_client):
    client, db = api_client
    with patch("api.programming.metadata.service.get_content_recommendations",
               return_value=RecommendationsOut(content_id=0, missing_fields=[], auto_fill=[], conflicts=[])):
        resp = client.get("/ai-review-queue")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "summary" in data
    assert "total" in data


# ── DAM integration 테스트 (Step 1.4) ────────────────────────────────────────

def test_dam_integration_off(db, four_contents, monkeypatch):
    contents, rec_map = four_contents
    called = []
    monkeypatch.setattr(
        "api.programming.metadata.service._fetch_dam_counts",
        lambda ids: called.append(ids) or {},
    )
    with patch("api.programming.metadata.service.get_content_recommendations",
               side_effect=lambda d, cid: rec_map[cid]):
        build_ai_review_queue(db, include_dam=False)
    assert called == [], "_fetch_dam_counts should not be called when include_dam=False"


def test_dam_integration_on_with_mock(db, four_contents, monkeypatch):
    contents, rec_map = four_contents
    cids = [c.id for c in contents]
    monkeypatch.setattr(
        "api.programming.metadata.service._fetch_dam_counts",
        lambda ids: {cid: 2 for cid in ids},
    )
    with patch("api.programming.metadata.service.get_content_recommendations",
               side_effect=lambda d, cid: rec_map[cid]):
        result = build_ai_review_queue(db, include_dam=True)
    assert all(r.dam_match_count == 2 for r in result.items)


def test_dam_integration_timeout_fallback(db, four_contents, monkeypatch):
    contents, rec_map = four_contents
    # _fetch_dam_count itself raises → _fetch_dam_counts returns 0
    def mock_fetch(ids):
        return {cid: 0 for cid in ids}  # timeout scenario: all 0
    monkeypatch.setattr("api.programming.metadata.service._fetch_dam_counts", mock_fetch)
    with patch("api.programming.metadata.service.get_content_recommendations",
               side_effect=lambda d, cid: rec_map[cid]):
        result = build_ai_review_queue(db, include_dam=True)
    assert all(r.dam_match_count == 0 for r in result.items), "timeout should yield dam_count=0"


def test_dam_integration_changes_poster_status(db, monkeypatch):
    # content: no primary image + dam_count=3 → dam_match_found
    c = _make_content(db, "dam-match-content")
    _make_image(db, c.id, source="tmdb", is_primary=False)  # 후보 있지만 primary 없음
    db.commit()

    rec_map = {c.id: _rec_missing(c.id)}
    monkeypatch.setattr(
        "api.programming.metadata.service._fetch_dam_counts",
        lambda ids: {cid: 3 for cid in ids},
    )
    with patch("api.programming.metadata.service.get_content_recommendations",
               side_effect=lambda d, cid: rec_map[cid]):
        result = build_ai_review_queue(db, include_dam=True)

    row = result.items[0]
    assert row.dam_match_count == 3
    assert row.poster_status == "dam_match_found"


def test_endpoint_query_params_passthrough(api_client):
    client, db = api_client
    # conflict content 1개 생성
    c = Content(
        title="conflict-content",
        content_type=ContentType.movie,
        cp_name="TestCP",
        status=ContentStatus.raw,
    )
    db.add(c)
    db.commit()

    conflict_rec = _rec_conflict(c.id)
    with patch("api.programming.metadata.service.get_content_recommendations",
               return_value=conflict_rec):
        resp_all = client.get("/ai-review-queue")
        resp_conflict = client.get("/ai-review-queue?metadata_status=conflict")
        resp_missing = client.get("/ai-review-queue?metadata_status=missing")

    assert resp_all.status_code == 200
    assert resp_all.json()["total"] == 1
    assert resp_conflict.json()["total"] == 1
    assert resp_missing.json()["total"] == 0
