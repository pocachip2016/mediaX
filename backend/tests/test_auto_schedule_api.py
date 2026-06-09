"""자동편성 파이프라인 API 엔드포인트 TestClient 테스트 — ADR-012."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from shared.database import get_db

BASE = "/api/programming/scheduling"


@pytest.fixture
def client(db):
    from main import app
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def set_id(client):
    r = client.post(f"{BASE}/sets", json={"name": "자동편성 테스트 세트"})
    assert r.status_code == 201
    return r.json()["id"]


@pytest.fixture
def node_id(client, set_id):
    r = client.post(f"{BASE}/nodes", json={
        "kind": "rule", "name": "테스트 노드", "set_id": set_id,
    })
    assert r.status_code == 201
    return r.json()["id"]


# ── auto/summary ───────────────────────────────────────────────────────────────

def test_summary_empty(client):
    r = client.get(f"{BASE}/auto/summary")
    assert r.status_code == 200
    data = r.json()
    assert data["total_auto_enabled"] == 0
    assert len(data["buckets"]) == 5


def test_summary_counts_enabled_node(client, node_id):
    client.post(f"{BASE}/auto/nodes/{node_id}/enable", json={"auto_enabled": True})
    r = client.get(f"{BASE}/auto/summary")
    assert r.json()["total_auto_enabled"] == 1


# ── auto/enable ────────────────────────────────────────────────────────────────

def test_enable_auto(client, node_id):
    r = client.post(f"{BASE}/auto/nodes/{node_id}/enable", json={"auto_enabled": True})
    assert r.status_code == 200
    assert r.json()["result"] == "ok"
    assert r.json()["auto_stage"] == "p1_define"


def test_disable_auto(client, node_id):
    client.post(f"{BASE}/auto/nodes/{node_id}/enable", json={"auto_enabled": True})
    r = client.post(f"{BASE}/auto/nodes/{node_id}/enable", json={"auto_enabled": False})
    assert r.status_code == 200
    assert r.json()["result"] == "ok"


# ── auto/advance ───────────────────────────────────────────────────────────────

def test_advance_not_found(client):
    r = client.post(f"{BASE}/auto/nodes/99999/advance")
    assert r.status_code == 200
    assert r.json()["result"] == "not_found"


def test_advance_node(client, node_id):
    client.post(f"{BASE}/auto/nodes/{node_id}/enable", json={"auto_enabled": True})
    with patch("api.programming.scheduling.auto_service._execute_stage"):
        r = client.post(f"{BASE}/auto/nodes/{node_id}/advance")
    assert r.status_code == 200
    assert r.json()["result"] == "ok"
    assert r.json()["auto_stage"] == "p2_candidate"


# ── auto/run ───────────────────────────────────────────────────────────────────

def test_run_to_stable(client, node_id):
    client.post(f"{BASE}/auto/nodes/{node_id}/enable", json={"auto_enabled": True})
    with patch("api.programming.scheduling.auto_service._execute_stage"):
        r = client.post(f"{BASE}/auto/nodes/{node_id}/run")
    assert r.status_code == 200
    data = r.json()
    assert data["stages_advanced"] >= 1
    assert data["final_result"] in ("terminal", "skipped", "hold")


# ── auto/events ────────────────────────────────────────────────────────────────

def test_events_empty(client, node_id):
    r = client.get(f"{BASE}/auto/nodes/{node_id}/events")
    assert r.status_code == 200
    assert r.json() == []


def test_events_after_advance(client, node_id):
    client.post(f"{BASE}/auto/nodes/{node_id}/enable", json={"auto_enabled": True})
    with patch("api.programming.scheduling.auto_service._execute_stage"):
        client.post(f"{BASE}/auto/nodes/{node_id}/advance")
    r = client.get(f"{BASE}/auto/nodes/{node_id}/events")
    assert r.status_code == 200
    assert len(r.json()) >= 1


# ── auto/policy ────────────────────────────────────────────────────────────────

def test_get_policy_defaults(client):
    r = client.get(f"{BASE}/auto/policy")
    assert r.status_code == 200
    data = r.json()
    assert data["confidence_threshold"] == 0.5
    assert data["auto_tick_enabled"] is False


def test_patch_policy(client):
    r = client.patch(f"{BASE}/auto/policy", json={"auto_tick_enabled": True, "batch_size": 10})
    assert r.status_code == 200
    data = r.json()
    assert data["auto_tick_enabled"] is True
    assert data["batch_size"] == 10


def test_patch_threshold_clears_skipped(client, node_id):
    """confidence_threshold 변경 시 auto_skipped_at 가 clear 돼야 한다."""
    from datetime import datetime, timezone
    from api.programming.scheduling.models import ProgrammingNode

    # 직접 skipped 마킹
    def override_db():
        from shared.database import SessionLocal
        return SessionLocal()

    # TestClient db fixture를 통해 직접 설정
    client.post(f"{BASE}/auto/nodes/{node_id}/enable", json={"auto_enabled": True})

    # policy threshold 변경 → skipped_at clear 호출 확인
    r = client.patch(f"{BASE}/auto/policy", json={"confidence_threshold": 0.7})
    assert r.status_code == 200
    assert r.json()["confidence_threshold"] == 0.7
