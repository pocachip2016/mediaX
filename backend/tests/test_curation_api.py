"""test_curation_api.py — 큐레이션 라우터 API 테스트 (FastAPI TestClient + SQLite).

main.py 전체 로딩 시 redis 미설치로 실패하므로, 큐레이션 라우터만 포함하는 미니 앱 사용.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shared.database import get_db
from api.programming.curation.router import router as curation_router

BASE = "/curation"


@pytest.fixture
def client(db):
    app = FastAPI()
    app.include_router(curation_router, prefix="/curation")
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c


# ── 슬롯 CRUD ─────────────────────────────────────────────────────────────────

def test_create_and_list_slots(client):
    r = client.post(f"{BASE}/slots", json={"slot_code": "A", "slot_type": "banner"})
    assert r.status_code == 201
    data = r.json()
    assert data["slot_code"] == "A"
    assert data["slot_type"] == "banner"
    assert data["is_active"] is True

    r2 = client.get(f"{BASE}/slots")
    assert r2.status_code == 200
    assert len(r2.json()) == 1


def test_get_slot_404(client):
    r = client.get(f"{BASE}/slots/99999")
    assert r.status_code == 404


def test_update_slot_active(client):
    slot_id = client.post(f"{BASE}/slots", json={"slot_code": "B", "slot_type": "theme"}).json()["id"]
    r = client.patch(f"{BASE}/slots/{slot_id}", json={"is_active": False})
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_delete_slot(client):
    slot_id = client.post(f"{BASE}/slots", json={"slot_code": "C", "slot_type": "genre"}).json()["id"]
    r = client.delete(f"{BASE}/slots/{slot_id}")
    assert r.status_code == 204
    assert client.get(f"{BASE}/slots/{slot_id}").status_code == 404


def test_resolve_slots(client):
    client.post(f"{BASE}/slots", json={"slot_code": "A", "slot_type": "banner", "device": "all", "time_band": "all"})
    client.post(f"{BASE}/slots", json={"slot_code": "A", "slot_type": "banner", "device": "tv", "time_band": "evening"})
    r = client.get(f"{BASE}/slots/resolve?device=tv&time_band=evening")
    assert r.status_code == 200
    slots = r.json()["slots"]
    assert len(slots) == 1
    assert slots[0]["device"] == "tv"


# ── 배너 편성안 ───────────────────────────────────────────────────────────────

def test_create_banner_plan(client):
    r = client.post(f"{BASE}/banner/plans", json={"week_start": "2026-06-09"})
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "draft"
    assert data["week_start"] == "2026-06-09"


def test_create_banner_plan_idempotent(client):
    r1 = client.post(f"{BASE}/banner/plans", json={"week_start": "2026-06-09"})
    r2 = client.post(f"{BASE}/banner/plans", json={"week_start": "2026-06-09"})
    assert r1.json()["id"] == r2.json()["id"]


def test_get_banner_plan_404(client):
    r = client.get(f"{BASE}/banner/plans/99999")
    assert r.status_code == 404


def test_banner_plan_full_workflow(client):
    plan_id = client.post(f"{BASE}/banner/plans", json={"week_start": "2026-06-16"}).json()["id"]

    r = client.post(f"{BASE}/banner/plans/{plan_id}/submit")
    assert r.status_code == 200
    assert r.json()["status"] == "review"

    r = client.post(f"{BASE}/banner/plans/{plan_id}/approve", json={"reviewer": "홍길동"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "approved"
    assert data["reviewer"] == "홍길동"

    r = client.post(f"{BASE}/banner/plans/{plan_id}/publish")
    assert r.status_code == 200
    assert r.json()["status"] == "published"


def test_publish_without_approve_returns_400(client):
    plan_id = client.post(f"{BASE}/banner/plans", json={"week_start": "2026-06-23"}).json()["id"]
    r = client.post(f"{BASE}/banner/plans/{plan_id}/publish")
    assert r.status_code == 400


def test_list_banner_plans(client):
    client.post(f"{BASE}/banner/plans", json={"week_start": "2026-06-09"})
    client.post(f"{BASE}/banner/plans", json={"week_start": "2026-06-16"})
    r = client.get(f"{BASE}/banner/plans")
    assert r.status_code == 200
    assert len(r.json()) == 2
