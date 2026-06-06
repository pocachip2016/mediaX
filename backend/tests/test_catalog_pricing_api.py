"""
가격 정책 + 홀드백 API 테스트 (FastAPI TestClient + in-memory SQLite)

검증 케이스:
  - GET /contents/{id}/pricing — 빈 매트릭스
  - PUT /contents/{id}/pricing — 가격 설정 + 재설정(변경)
  - POST /pricing/bulk — 일괄 변경
  - GET /contents/{id}/price-changes — 변경 이력
  - DELETE /contents/{id}/pricing — 삭제 + 404
  - GET /holdback/policies — 전체/cp_name 필터
  - PUT /holdback/policies — upsert
  - DELETE /holdback/policies/{id} — 삭제 + 404
  - POST /contents/{id}/holdback/apply — 스케줄 생성
  - GET /contents/{id}/holdback — 스케줄 목록
  - POST /contents/{id}/holdback/{w}/activate — 활성화 + 404
  - GET /holdback/calendar — 날짜 범위 조회
"""
import pytest
from fastapi.testclient import TestClient

from shared.database import get_db
from api.programming.metadata.models import Content, ContentType, ContentStatus

BASE = "/api/programming/catalog"


@pytest.fixture
def client(db):
    from main import app
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def content(db):
    c = Content(title="테스트콘텐츠", content_type=ContentType.movie, status=ContentStatus.raw, cp_name="CP_TEST")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


# ── GET pricing ───────────────────────────────────────────────────────────────

def test_get_pricing_empty(client, content):
    res = client.get(f"{BASE}/contents/{content.id}/pricing")
    assert res.status_code == 200
    assert res.json() == {}


# ── PUT pricing ───────────────────────────────────────────────────────────────

def test_set_price(client, content):
    res = client.put(f"{BASE}/contents/{content.id}/pricing", json={
        "quality": "HD",
        "purchase_type": "single",
        "price": 2000,
    })
    assert res.status_code == 200
    body = res.json()
    assert body["price"] == 2000
    assert body["quality"] == "HD"
    assert body["purchase_type"] == "single"


def test_set_price_update(client, content):
    client.put(f"{BASE}/contents/{content.id}/pricing", json={
        "quality": "HD", "purchase_type": "single", "price": 2000,
    })
    res = client.put(f"{BASE}/contents/{content.id}/pricing", json={
        "quality": "HD", "purchase_type": "single", "price": 2500, "reason": "가격 인상",
    })
    assert res.status_code == 200
    assert res.json()["price"] == 2500


# ── POST bulk ────────────────────────────────────────────────────────────────

def test_bulk_pricing(client, db):
    c1 = Content(title="C1", content_type=ContentType.movie, status=ContentStatus.raw, cp_name="A")
    c2 = Content(title="C2", content_type=ContentType.movie, status=ContentStatus.raw, cp_name="A")
    db.add_all([c1, c2])
    db.commit()
    db.refresh(c1); db.refresh(c2)

    res = client.post(f"{BASE}/pricing/bulk", json={
        "items": [
            {"content_id": c1.id, "quality": "HD", "purchase_type": "single", "price": 1500},
            {"content_id": c2.id, "quality": "HD", "purchase_type": "single", "price": 1500},
        ],
        "changed_by": "admin",
    })
    assert res.status_code == 200
    assert len(res.json()) == 2


# ── GET price-changes ────────────────────────────────────────────────────────

def test_price_changes_log(client, content):
    client.put(f"{BASE}/contents/{content.id}/pricing", json={
        "quality": "HD", "purchase_type": "single", "price": 2000,
    })
    client.put(f"{BASE}/contents/{content.id}/pricing", json={
        "quality": "HD", "purchase_type": "single", "price": 2500,
    })
    res = client.get(f"{BASE}/contents/{content.id}/price-changes")
    assert res.status_code == 200
    logs = res.json()
    assert len(logs) == 2
    assert logs[0]["new_price"] == 2500


# ── DELETE pricing ───────────────────────────────────────────────────────────

def test_delete_price(client, content):
    client.put(f"{BASE}/contents/{content.id}/pricing", json={
        "quality": "HD", "purchase_type": "single", "price": 2000,
    })
    res = client.delete(f"{BASE}/contents/{content.id}/pricing?quality=HD&purchase_type=single")
    assert res.status_code == 204


def test_delete_price_404(client, content):
    res = client.delete(f"{BASE}/contents/{content.id}/pricing?quality=HD&purchase_type=single")
    assert res.status_code == 404


# ── holdback policies ────────────────────────────────────────────────────────

def test_upsert_holdback_policy(client):
    res = client.put(f"{BASE}/holdback/policies", json={
        "cp_name": "CP_TEST",
        "window_no": 1,
        "name": "프리미엄",
        "offset_days_start": 0,
        "offset_days_end": 90,
        "price_rule": "premium",
    })
    assert res.status_code == 200
    assert res.json()["cp_name"] == "CP_TEST"


def test_list_holdback_policies_filter(client):
    client.put(f"{BASE}/holdback/policies", json={
        "cp_name": "CP_A", "window_no": 1, "name": "W1",
        "offset_days_start": 0, "offset_days_end": 90, "price_rule": "premium",
    })
    client.put(f"{BASE}/holdback/policies", json={
        "cp_name": "CP_B", "window_no": 1, "name": "W1",
        "offset_days_start": 0, "offset_days_end": 90, "price_rule": "standard",
    })
    res = client.get(f"{BASE}/holdback/policies?cp_name=CP_A")
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_delete_holdback_policy(client):
    r = client.put(f"{BASE}/holdback/policies", json={
        "cp_name": "CP_DEL", "window_no": 1, "name": "W",
        "offset_days_start": 0, "price_rule": "premium",
    })
    pid = r.json()["id"]
    res = client.delete(f"{BASE}/holdback/policies/{pid}")
    assert res.status_code == 204


def test_delete_holdback_policy_404(client):
    res = client.delete(f"{BASE}/holdback/policies/9999")
    assert res.status_code == 404


# ── holdback apply / schedules ───────────────────────────────────────────────

def test_apply_holdback(client, content):
    client.put(f"{BASE}/holdback/policies", json={
        "cp_name": "CP_TEST", "window_no": 1, "name": "프리미엄",
        "offset_days_start": 0, "offset_days_end": 90, "price_rule": "premium",
    })
    res = client.post(f"{BASE}/contents/{content.id}/holdback/apply", json={"base_date": "2026-01-01"})
    assert res.status_code == 200
    schedules = res.json()
    assert len(schedules) == 1
    assert schedules[0]["start_date"] == "2026-01-01"


def test_list_holdback_schedules(client, content):
    client.put(f"{BASE}/holdback/policies", json={
        "cp_name": "CP_TEST", "window_no": 1, "name": "W1",
        "offset_days_start": 0, "offset_days_end": 90, "price_rule": "premium",
    })
    client.post(f"{BASE}/contents/{content.id}/holdback/apply", json={"base_date": "2026-01-01"})
    res = client.get(f"{BASE}/contents/{content.id}/holdback")
    assert res.status_code == 200
    assert len(res.json()) == 1


# ── activate ──────────────────────────────────────────────────────────────────

def test_activate_holdback_window(client, content):
    client.put(f"{BASE}/holdback/policies", json={
        "cp_name": "CP_TEST", "window_no": 1, "name": "W1",
        "offset_days_start": 0, "offset_days_end": 90, "price_rule": "premium",
    })
    client.post(f"{BASE}/contents/{content.id}/holdback/apply", json={"base_date": "2026-01-01"})
    res = client.post(f"{BASE}/contents/{content.id}/holdback/1/activate", json={
        "quality": "HD", "purchase_type": "single", "price": 3000,
    })
    assert res.status_code == 200
    assert res.json()["status"] == "active"


def test_activate_holdback_404(client, content):
    res = client.post(f"{BASE}/contents/{content.id}/holdback/99/activate", json={})
    assert res.status_code == 404


# ── calendar ──────────────────────────────────────────────────────────────────

def test_holdback_calendar(client, content):
    client.put(f"{BASE}/holdback/policies", json={
        "cp_name": "CP_TEST", "window_no": 1, "name": "W1",
        "offset_days_start": 0, "offset_days_end": 90, "price_rule": "premium",
    })
    client.post(f"{BASE}/contents/{content.id}/holdback/apply", json={"base_date": "2026-01-01"})
    res = client.get(f"{BASE}/holdback/calendar?start=2026-01-01&end=2026-03-31")
    assert res.status_code == 200
    assert len(res.json()) == 1
