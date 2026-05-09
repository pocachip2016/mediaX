"""
Resolution API 엔드포인트 테스트 — FastAPI TestClient

테스트 대상 경로 (prefix /api/meta-core):
  GET /contents/{id}/gap
  GET /contents/{id}/resolutions
  GET /contents/{id}/resolutions/{field}
  GET /contents/{id}/match-edges
  GET /queue/resolutions
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shared.database import get_db
from api.meta_core.intelligence.router import router

import api.programming.metadata.models  # noqa: F401
import api.meta_core.models             # noqa: F401
from api.programming.metadata.models.content import Content, ContentType, ContentStatus
from api.meta_core.models.intelligence import FieldResolution, FieldSuggestion, MatchEdge, MetadataCandidate


# ── 테스트 전용 미니앱 ────────────────────────────────────────────────────────

def _make_test_app(db):
    test_app = FastAPI()
    test_app.include_router(router)

    def _override():
        yield db

    test_app.dependency_overrides[get_db] = _override
    return test_app


@pytest.fixture
def client(db):
    from sqlalchemy import text
    db.execute(text("SELECT 1"))  # 커넥션 초기화 — SQLite in-memory 테이블 가시성 보장
    with TestClient(_make_test_app(db)) as c:
        yield c


# ── 시드 데이터 헬퍼 ──────────────────────────────────────────────────────────

def _content(db) -> Content:
    c = Content(title="기생충", content_type=ContentType.movie, status=ContentStatus.staging)
    db.add(c)
    db.flush()
    return c


def _resolution(db, content_id, field_name, decision="pending") -> FieldResolution:
    r = FieldResolution(
        content_id=content_id,
        field_name=field_name,
        decision=decision,
        chosen_value_json="봉준호" if decision != "pending" else None,
        chosen_suggestion_ids=[],
        agreement_count=2 if decision != "pending" else 0,
        agreeing_sources_json=["tmdb", "kmdb"],
        applied_to_content=(decision == "auto_agreement"),
        decided_by="system" if decision != "pending" else None,
    )
    db.add(r)
    db.flush()
    return r


def _suggestion(db, content_id, field_name, source_type="tmdb") -> FieldSuggestion:
    s = FieldSuggestion(
        content_id=content_id,
        field_name=field_name,
        value_json="봉준호",
        source_type=source_type,
        confidence=0.9,
        status="pending",
    )
    db.add(s)
    db.flush()
    return s


# ── GET /contents/{id}/gap ────────────────────────────────────────────────────

def test_get_gap_empty_content(client, db):
    c = _content(db)
    resp = client.get(f"/contents/{c.id}/gap")
    assert resp.status_code == 200
    data = resp.json()
    assert data["content_id"] == c.id
    assert data["is_clean"] is False
    assert len(data["missing_fields"]) > 0


def test_get_gap_not_found(client, db):
    resp = client.get("/contents/99999/gap")
    assert resp.status_code == 404


# ── GET /contents/{id}/resolutions ───────────────────────────────────────────

def test_get_resolutions_empty(client, db):
    c = _content(db)
    resp = client.get(f"/contents/{c.id}/resolutions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["auto"] == []
    assert data["pending"] == []


def test_get_resolutions_grouped(client, db):
    c = _content(db)
    _resolution(db, c.id, "director", "auto_agreement")
    _resolution(db, c.id, "synopsis", "pending")

    resp = client.get(f"/contents/{c.id}/resolutions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["auto"]) == 1
    assert data["auto"][0]["field_name"] == "director"
    assert len(data["pending"]) == 1
    assert data["pending"][0]["field_name"] == "synopsis"


def test_get_resolutions_content_not_found(client, db):
    resp = client.get("/contents/99999/resolutions")
    assert resp.status_code == 404


# ── GET /contents/{id}/resolutions/{field} ───────────────────────────────────

def test_get_resolution_field_with_suggestions(client, db):
    c = _content(db)
    _resolution(db, c.id, "director", "auto_agreement")
    _suggestion(db, c.id, "director", "tmdb")
    _suggestion(db, c.id, "director", "kmdb")

    resp = client.get(f"/contents/{c.id}/resolutions/director")
    assert resp.status_code == 200
    data = resp.json()
    assert data["resolution"]["field_name"] == "director"
    assert len(data["suggestions"]) == 2


def test_get_resolution_field_no_resolution(client, db):
    c = _content(db)
    _suggestion(db, c.id, "synopsis", "tmdb")

    resp = client.get(f"/contents/{c.id}/resolutions/synopsis")
    assert resp.status_code == 200
    data = resp.json()
    assert data["resolution"] is None
    assert len(data["suggestions"]) == 1


# ── GET /contents/{id}/match-edges ───────────────────────────────────────────

def _candidate(db) -> MetadataCandidate:
    cand = MetadataCandidate(
        source_type="tmdb",
        source_external_id="496243",
        raw_payload={"id": 496243},
        title_norm="기생충",
    )
    db.add(cand)
    db.flush()
    return cand


def test_get_match_edges_empty(client, db):
    c = _content(db)
    resp = client.get(f"/contents/{c.id}/match-edges")
    assert resp.status_code == 200
    data = resp.json()
    assert data["decided"] == []
    assert data["undecided"] == []


def test_get_match_edges_split(client, db):
    c = _content(db)
    cand1 = _candidate(db)
    cand2 = MetadataCandidate(
        source_type="kmdb", source_external_id="K|00001",
        raw_payload={}, title_norm="기생충",
    )
    db.add(cand2)
    db.flush()

    # unique constraint (candidate_id, content_id) — 두 후보를 각각 사용
    db.add(MatchEdge(
        candidate_id=cand1.id, content_id=c.id,
        score=0.95, reasons_json=["title_exact"], decided=True,
    ))
    db.add(MatchEdge(
        candidate_id=cand2.id, content_id=c.id,
        score=0.75, reasons_json=[], decided=False,
    ))
    db.flush()

    resp = client.get(f"/contents/{c.id}/match-edges")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["decided"]) == 1
    assert len(data["undecided"]) == 1
    assert data["decided"][0]["score"] == pytest.approx(0.95)


# ── GET /queue/resolutions ────────────────────────────────────────────────────

def test_queue_resolutions_default_pending(client, db):
    c = _content(db)
    _resolution(db, c.id, "synopsis", "pending")

    resp = client.get("/queue/resolutions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert all(item["resolution"]["decision"] == "pending" for item in data["items"])


def test_queue_resolutions_pagination(client, db):
    c = _content(db)
    for i in range(5):
        r = FieldResolution(
            content_id=c.id,
            field_name=f"field_{i}",
            decision="pending",
            chosen_suggestion_ids=[],
            agreement_count=0,
            agreeing_sources_json=[],
            applied_to_content=False,
        )
        db.add(r)
    db.flush()

    resp = client.get("/queue/resolutions?page=1&page_size=3")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) <= 3
    assert data["page"] == 1
    assert data["page_size"] == 3


def test_queue_resolutions_filter_auto(client, db):
    c = _content(db)
    _resolution(db, c.id, "director", "auto_agreement")
    _resolution(db, c.id, "synopsis", "pending")

    resp = client.get("/queue/resolutions?decision=auto_agreement")
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["resolution"]["decision"] == "auto_agreement" for item in data["items"])
