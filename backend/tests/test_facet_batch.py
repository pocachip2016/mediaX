"""test_facet_batch.py — facet 배치 라우터 API 테스트 (FastAPI TestClient + SQLite).

main.py 전체 로딩 시 redis 미설치로 실패하므로, facet 라우터만 포함하는 미니 앱 사용.
"""
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shared.database import get_db
from api.programming.metadata.router_facets import router as facets_router
from api.programming.metadata.models.external import FacetBatchRun

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
        mock_task.delay.return_value = None
        r = client.post("/batch", json={})
    assert r.status_code == 202
    assert r.json()["queued"] is True
    mock_task.delay.assert_called_once_with(limit=None, content_ids=None, force=False, trigger="manual")


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
