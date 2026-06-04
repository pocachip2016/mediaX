"""
Review Backend (step9) 테스트 — POST 쓰기 엔드포인트

시나리오:
  1. accept — auto 결정 확정 / 이미 applied면 no-op
  2. pick — suggestion 1개 manual_pick
  3. merge union — C형 텍스트 병합
  4. merge llm_merge — LLM 호출 (mock) + external_sync_log 행 확인
  5. reject — 결정 rejected, applied=false
  6. bulk-accept — 여러 필드 일괄
"""

import pytest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from shared.database import get_db
from api.meta_core.intelligence.router import router

import api.programming.metadata.models  # noqa: F401
import api.meta_core.models             # noqa: F401
from api.programming.metadata.models.content import Content, ContentType, ContentStatus
from api.meta_core.models.intelligence import FieldResolution, FieldSuggestion
from api.programming.metadata.models.tmdb_cache import ExternalSyncLog, TmdbSyncSource


# ── 픽스처 ────────────────────────────────────────────────────────────────────

def _make_app(db):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    return app


@pytest.fixture
def client(db):
    db.execute(text("SELECT 1"))
    with TestClient(_make_app(db)) as c:
        yield c


def _content(db) -> Content:
    c = Content(title="기생충", content_type=ContentType.movie, status=ContentStatus.ai)
    db.add(c)
    db.flush()
    return c


def _resolution(db, cid, field, decision="pending", applied=False) -> FieldResolution:
    r = FieldResolution(
        content_id=cid, field_name=field, decision=decision,
        chosen_value_json="봉준호" if decision != "pending" else None,
        chosen_suggestion_ids=[], agreement_count=2,
        agreeing_sources_json=["tmdb", "kmdb"],
        applied_to_content=applied,
    )
    db.add(r); db.flush(); return r


def _suggestion(db, cid, field, value="봉준호", source="tmdb") -> FieldSuggestion:
    s = FieldSuggestion(
        content_id=cid, field_name=field, value_json=value,
        source_type=source, confidence=0.9, status="pending",
    )
    db.add(s); db.flush(); return s


# ── 1. accept ─────────────────────────────────────────────────────────────────

def test_accept_applies_resolution(client, db):
    c = _content(db)
    _resolution(db, c.id, "director", "auto_agreement", applied=False)

    resp = client.post(f"/contents/{c.id}/resolutions/director/accept")
    assert resp.status_code == 200
    data = resp.json()
    assert data["applied"] is True

    res = db.query(FieldResolution).filter_by(content_id=c.id, field_name="director").first()
    assert res.applied_to_content is True


def test_accept_noop_if_already_applied(client, db):
    c = _content(db)
    _resolution(db, c.id, "director", "auto_agreement", applied=True)

    resp = client.post(f"/contents/{c.id}/resolutions/director/accept")
    assert resp.status_code == 200
    assert resp.json()["message"] == "already applied"


def test_accept_404_if_no_resolution(client, db):
    c = _content(db)
    resp = client.post(f"/contents/{c.id}/resolutions/director/accept")
    assert resp.status_code == 404


# ── 2. pick ───────────────────────────────────────────────────────────────────

def test_pick_sets_manual_pick(client, db):
    c = _content(db)
    _resolution(db, c.id, "director", "pending")
    sug = _suggestion(db, c.id, "director", "봉준호")

    resp = client.post(
        f"/contents/{c.id}/resolutions/director/pick",
        json={"suggestion_id": sug.id},
    )
    assert resp.status_code == 200
    assert resp.json()["decision"] == "manual_pick"

    res = db.query(FieldResolution).filter_by(content_id=c.id, field_name="director").first()
    assert res.decision == "manual_pick"
    assert res.applied_to_content is True
    assert res.chosen_value_json == "봉준호"


def test_pick_marks_suggestion_applied(client, db):
    c = _content(db)
    _resolution(db, c.id, "director", "pending")
    sug = _suggestion(db, c.id, "director")

    client.post(f"/contents/{c.id}/resolutions/director/pick", json={"suggestion_id": sug.id})

    db.expire(sug)
    assert sug.status == "applied"


def test_pick_invalid_suggestion_404(client, db):
    c = _content(db)
    _resolution(db, c.id, "director", "pending")
    resp = client.post(f"/contents/{c.id}/resolutions/director/pick", json={"suggestion_id": 9999})
    assert resp.status_code == 404


# ── 3. merge union ────────────────────────────────────────────────────────────

def test_merge_union(client, db):
    c = _content(db)
    sug1 = _suggestion(db, c.id, "synopsis", "줄거리 A" * 10, "tmdb")
    sug2 = _suggestion(db, c.id, "synopsis", "줄거리 B" * 10, "kmdb")

    resp = client.post(
        f"/contents/{c.id}/resolutions/synopsis/merge",
        json={"suggestion_ids": [sug1.id, sug2.id], "method": "union"},
    )
    assert resp.status_code == 200
    assert resp.json()["decision"] == "manual_merge"

    res = db.query(FieldResolution).filter_by(content_id=c.id, field_name="synopsis").first()
    assert res.decision == "manual_merge"
    assert res.merge_method == "union"
    assert res.applied_to_content is True


# ── 4. merge llm_merge + external_sync_log ───────────────────────────────────

def test_merge_llm_creates_sync_log(client, db):
    c = _content(db)
    sug1 = _suggestion(db, c.id, "synopsis", "A" * 50, "tmdb")
    sug2 = _suggestion(db, c.id, "synopsis", "B" * 50, "kmdb")

    with patch("api.meta_core.intelligence.router.llm_merge_synopses", return_value="merged text") as mock_llm:
        resp = client.post(
            f"/contents/{c.id}/resolutions/synopsis/merge",
            json={"suggestion_ids": [sug1.id, sug2.id], "method": "llm_merge"},
        )

    assert resp.status_code == 200
    # llm_merge_synopses 가 호출됐는지 확인
    mock_llm.assert_called_once()


def test_llm_merge_synopses_logs_sync_record(db):
    """llm_merge_synopses 직접 호출 → external_sync_log 행 생성."""
    from api.meta_core.aggregator import llm_merge_synopses

    with patch("asyncio.run", return_value="merged text"):
        result = llm_merge_synopses(["A" * 50, "B" * 50], db)

    assert result == "merged text"
    log = db.query(ExternalSyncLog).filter_by(source=TmdbSyncSource.llm_merge).first()
    assert log is not None
    assert log.items_fetched == 2


# ── 5. reject ─────────────────────────────────────────────────────────────────

def test_reject_sets_rejected(client, db):
    c = _content(db)
    _resolution(db, c.id, "director", "auto_agreement", applied=True)

    resp = client.post(f"/contents/{c.id}/resolutions/director/reject")
    assert resp.status_code == 200
    assert resp.json()["applied"] is False

    res = db.query(FieldResolution).filter_by(content_id=c.id, field_name="director").first()
    assert res.decision == "rejected"
    assert res.applied_to_content is False


def test_reject_creates_resolution_if_none(client, db):
    c = _content(db)
    resp = client.post(f"/contents/{c.id}/resolutions/synopsis/reject")
    assert resp.status_code == 200
    res = db.query(FieldResolution).filter_by(content_id=c.id, field_name="synopsis").first()
    assert res is not None
    assert res.decision == "rejected"


# ── 6. bulk-accept ────────────────────────────────────────────────────────────

def test_bulk_accept_multiple_fields(client, db):
    c = _content(db)
    _resolution(db, c.id, "director", "auto_agreement", applied=False)
    _resolution(db, c.id, "primary_genre", "auto_agreement", applied=False)

    resp = client.post(
        f"/contents/{c.id}/resolutions/bulk-accept",
        json={"fields": ["director", "primary_genre"]},
    )
    assert resp.status_code == 200
    results = resp.json()
    assert all(r["applied"] for r in results)
    assert {r["field_name"] for r in results} == {"director", "primary_genre"}


def test_bulk_accept_missing_field_reports_not_found(client, db):
    c = _content(db)
    _resolution(db, c.id, "director", "auto_agreement", applied=False)

    resp = client.post(
        f"/contents/{c.id}/resolutions/bulk-accept",
        json={"fields": ["director", "nonexistent"]},
    )
    assert resp.status_code == 200
    results = {r["field_name"]: r for r in resp.json()}
    assert results["director"]["applied"] is True
    assert results["nonexistent"]["decision"] == "not_found"
