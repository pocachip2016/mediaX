"""test_facet_batch.py — facet 배치 라우터 API 테스트 (FastAPI TestClient + SQLite).

main.py 전체 로딩 시 redis 미설치로 실패하므로, facet 라우터만 포함하는 미니 앱 사용.
"""
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shared.database import get_db
from api.programming.metadata.router_facets import router as facets_router
from api.programming.metadata.models.external import FacetBatchRun, FacetEvent, FacetPolicy

BASE = ""


@pytest.fixture
def client(db):
    app = FastAPI()
    app.include_router(facets_router, prefix="")
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c


# ── GET /batch ─────────────────────────────────────────────────────────────────

def test_list_batch_runs_empty(client):
    r = client.get("/batch")
    assert r.status_code == 200
    assert r.json() == []


def test_list_batch_runs_returns_runs(client, db):
    run = FacetBatchRun(status="done", trigger="manual", total_count=5, success_count=4, failed_count=1)
    db.add(run)
    db.commit()

    r = client.get("/batch")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["status"] == "done"
    assert data[0]["success_count"] == 4


# ── GET /batch/{run_id} ────────────────────────────────────────────────────────

def test_get_batch_run_ok(client, db):
    run = FacetBatchRun(status="running", trigger="beat", total_count=10, success_count=3, failed_count=1)
    db.add(run)
    db.commit()
    db.refresh(run)

    r = client.get(f"/batch/{run.id}")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "running"
    # ETA: 잔여 6건 × 120s = 720
    assert data["eta_seconds"] == 720


def test_get_batch_run_404(client):
    r = client.get("/batch/99999")
    assert r.status_code == 404


# ── POST /batch ─────────────────────────────────────────────────────────────────

def test_trigger_batch_queued(client, db):
    with patch("workers.tasks.facet_tasks.dispatch_facet_batch") as mock_task:
        mock_task.return_value = {"run_id": 1}
        r = client.post("/batch", json={})
    assert r.status_code == 202
    assert r.json()["queued"] is True
    mock_task.assert_called_once_with(limit=None, tmdb_ids=None, force=False, trigger="manual")


def test_trigger_batch_409_when_running(client, db):
    run = FacetBatchRun(status="running", trigger="manual", total_count=3)
    db.add(run)
    db.commit()

    with patch("workers.tasks.facet_tasks.dispatch_facet_batch"):
        r = client.post("/batch", json={})
    assert r.status_code == 409


# ── GET /coverage ─────────────────────────────────────────────────────────────

def test_coverage_empty(client):
    r = client.get("/coverage")
    assert r.status_code == 200
    data = r.json()
    assert data["movies_total"] == 0
    assert data["with_final_facet"] == 0
    assert data["stale"] == 0
    assert data["pending"] == 0


# ── GET /events ────────────────────────────────────────────────────────────────

def test_events_empty(client):
    r = client.get("/events?since=0")
    assert r.status_code == 200
    data = r.json()
    assert data["items"] == []
    assert data["next_cursor"] == 0


def test_events_since_cursor(client, db):
    run = FacetBatchRun(status="running", trigger="manual", total_count=2)
    db.add(run)
    db.commit()
    db.refresh(run)

    e1 = FacetEvent(run_id=run.id, event_type="batch_started", message="시작")
    e2 = FacetEvent(run_id=run.id, event_type="item_success", message="완료")
    db.add_all([e1, e2])
    db.commit()
    db.refresh(e1)
    db.refresh(e2)

    # since=0 → 둘 다 반환
    r = client.get("/events?since=0")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 2
    assert items[0]["event_type"] == "batch_started"

    # since=e1.id → e2만 반환
    r2 = client.get(f"/events?since={e1.id}")
    assert r2.status_code == 200
    items2 = r2.json()["items"]
    assert len(items2) == 1
    assert items2[0]["event_type"] == "item_success"


def test_events_filter_by_run_id(client, db):
    run1 = FacetBatchRun(status="done", trigger="manual", total_count=1)
    run2 = FacetBatchRun(status="done", trigger="beat", total_count=1)
    db.add_all([run1, run2])
    db.commit()
    db.refresh(run1)
    db.refresh(run2)

    db.add(FacetEvent(run_id=run1.id, event_type="batch_started", message="run1"))
    db.add(FacetEvent(run_id=run2.id, event_type="batch_started", message="run2"))
    db.commit()

    r = client.get(f"/events?since=0&run_id={run1.id}")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["message"] == "run1"


# ── GET/PATCH /policy ─────────────────────────────────────────────────────────

def test_policy_default_false(client):
    r = client.get("/policy")
    assert r.status_code == 200
    assert r.json()["log_enabled"] is False


def test_policy_toggle_roundtrip(client):
    # ON
    r = client.patch("/policy", json={"log_enabled": True})
    assert r.status_code == 200
    assert r.json()["log_enabled"] is True

    # 재조회
    r2 = client.get("/policy")
    assert r2.json()["log_enabled"] is True

    # OFF
    r3 = client.patch("/policy", json={"log_enabled": False})
    assert r3.json()["log_enabled"] is False


# ── GET /daily ─────────────────────────────────────────────────────────────────

def test_daily_empty(client):
    r = client.get("/daily?days=7")
    assert r.status_code == 200
    assert r.json() == []


def test_daily_aggregates(client, db):
    from datetime import datetime, timezone
    run = FacetBatchRun(
        status="done", trigger="manual",
        total_count=10, success_count=8, failed_count=2,
        created_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()

    r = client.get("/daily?days=1")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["runs"] == 1
    assert data[0]["success"] == 8
    assert data[0]["failed"] == 2
