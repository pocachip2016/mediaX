"""
SEED 검수 API 단위 테스트 (seed_router)

FastAPI TestClient + SQLite in-memory DB.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.database import Base, get_db
import api.meta_core.models  # noqa
import api.programming.metadata.models  # noqa

from api.meta_core.intelligence.seed_router import router
from api.meta_core.models.seed import ContentSeed
from api.programming.metadata.models.content import Content


# ── App / DB fixture ──────────────────────────────────────────────────────────

@pytest.fixture
def client():
    # StaticPool — 모든 연결이 동일 in-memory DB 공유 (TestClient + 직접 session)
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    app = FastAPI()
    app.include_router(router)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app), Session()


def _seed(db, title="기생충", year=2019, source_type="tmdb", external_id="496243",
          status="candidate", locked_by=None, locked_at=None) -> ContentSeed:
    s = ContentSeed(
        source_type=source_type, external_id=external_id, title=title,
        content_type="movie", production_year=year, status=status,
        locked_by=locked_by, locked_at=locked_at, raw_payload={},
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


# ── GET /seeds ────────────────────────────────────────────────────────────────

def test_list_seeds_empty(client):
    tc, db = client
    resp = tc.get("/seeds")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_list_seeds_filter_status(client):
    tc, db = client
    _seed(db, status="candidate")
    _seed(db, status="accepted", external_id="999")
    resp = tc.get("/seeds?status=candidate")
    assert resp.json()["total"] == 1


def test_list_seeds_filter_source(client):
    tc, db = client
    _seed(db, source_type="tmdb")
    _seed(db, source_type="kobis", external_id="K001")
    resp = tc.get("/seeds?source_type=kobis")
    assert resp.json()["total"] == 1


def test_list_seeds_pagination(client):
    tc, db = client
    for i in range(5):
        _seed(db, external_id=str(i))
    resp = tc.get("/seeds?page=1&page_size=3")
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 3


# ── GET /seeds/{id} ───────────────────────────────────────────────────────────

def test_get_seed_detail(client):
    tc, db = client
    seed = _seed(db)
    resp = tc.get(f"/seeds/{seed.id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "기생충"


def test_get_seed_not_found(client):
    tc, db = client
    resp = tc.get("/seeds/9999")
    assert resp.status_code == 404


# ── POST /seeds/{id}/lock & unlock ───────────────────────────────────────────

def test_lock_unlock_flow(client):
    tc, db = client
    seed = _seed(db)

    resp = tc.post(f"/seeds/{seed.id}/lock?actor=alice")
    assert resp.status_code == 200
    db.refresh(seed)
    assert seed.status == "under_review"
    assert seed.locked_by == "alice"

    resp = tc.post(f"/seeds/{seed.id}/unlock?actor=alice")
    assert resp.status_code == 200
    db.refresh(seed)
    assert seed.locked_by is None
    assert seed.status == "candidate"


def test_lock_by_other_user_blocked(client):
    tc, db = client
    locked_at = datetime.now(tz=timezone.utc) - timedelta(minutes=5)
    seed = _seed(db, locked_by="alice", locked_at=locked_at)
    resp = tc.post(f"/seeds/{seed.id}/lock?actor=bob")
    assert resp.status_code == 423


# ── POST /seeds/{id}/accept ───────────────────────────────────────────────────

def test_accept_creates_content(client):
    tc, db = client
    seed = _seed(db)
    with patch("api.meta_core.discovery.promote._enqueue_aggregate"):
        resp = tc.post(f"/seeds/{seed.id}/accept", json={"actor": "admin"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "content_id=" in data["message"]


# ── POST /seeds/{id}/reject ───────────────────────────────────────────────────

def test_reject_seed(client):
    tc, db = client
    seed = _seed(db)
    resp = tc.post(f"/seeds/{seed.id}/reject",
                   json={"actor": "admin", "reason": "중복 콘텐츠"})
    assert resp.status_code == 200
    db.refresh(seed)
    assert seed.status == "rejected"
    assert seed.raw_payload["_reject_reason"] == "중복 콘텐츠"


def test_reject_already_accepted(client):
    tc, db = client
    seed = _seed(db, status="accepted")
    resp = tc.post(f"/seeds/{seed.id}/reject", json={"actor": "admin", "reason": "x"})
    assert resp.status_code == 400


# ── POST /seeds/{id}/edit ─────────────────────────────────────────────────────

def test_edit_seed(client):
    tc, db = client
    seed = _seed(db)
    resp = tc.post(f"/seeds/{seed.id}/edit",
                   json={"actor": "admin", "title": "기생충 (수정)", "production_year": 2020})
    assert resp.status_code == 200
    db.refresh(seed)
    assert seed.title == "기생충 (수정)"
    assert seed.production_year == 2020


# ── POST /seeds/bulk-promote ──────────────────────────────────────────────────

def test_bulk_promote_success(client):
    tc, db = client
    # 다른 제목으로 dedup 충돌 방지
    s1 = _seed(db, title="기생충", year=2019, external_id="A")
    s2 = _seed(db, title="올드보이", year=2003, external_id="B")
    with patch("api.meta_core.discovery.promote._enqueue_aggregate"):
        resp = tc.post("/seeds/bulk-promote",
                       json={"seed_ids": [s1.id, s2.id], "actor": "admin"})
    assert resp.status_code == 200
    results = resp.json()
    assert all(r["success"] for r in results)


def test_bulk_promote_partial_failure(client):
    tc, db = client
    s1 = _seed(db, external_id="C")
    with patch("api.meta_core.discovery.promote._enqueue_aggregate"):
        resp = tc.post("/seeds/bulk-promote",
                       json={"seed_ids": [s1.id, 9999], "actor": "admin"})
    results = resp.json()
    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]
    assert len(successes) == 1
    assert len(failures) == 1


def test_bulk_promote_max_exceeded(client):
    tc, db = client
    resp = tc.post("/seeds/bulk-promote",
                   json={"seed_ids": list(range(51)), "actor": "admin"})
    assert resp.status_code == 422  # Pydantic max_length validation
