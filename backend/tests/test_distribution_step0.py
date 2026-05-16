"""
Step 0 검증 — distribution 모듈 기본 CRUD + API 라우터
"""
import pytest
from fastapi.testclient import TestClient

from shared.database import get_db
from api.distribution.models import ContentDistribution, ServiceCategory, DeviceVariant
from api.distribution import service
from api.programming.metadata.models import Content


@pytest.fixture
def client(db):
    from main import app

    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def content(db):
    obj = Content(title="테스트 콘텐츠", content_type="movie", status="waiting")
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ── service layer ──────────────────────────────────────────────────────────────

def test_get_channels_empty(db, content):
    result = service.get_channels_for_content(db, content.id)
    assert result == []


def test_get_channels_returns_data(db, content):
    db.add(ContentDistribution(
        content_id=content.id,
        channel="ott_watcha",
        channel_type="ott",
        popularity_rank=1,
    ))
    db.commit()
    result = service.get_channels_for_content(db, content.id)
    assert len(result) == 1
    assert result[0].channel == "ott_watcha"


def test_get_categories_empty(db):
    result = service.get_categories(db)
    assert result == []


def test_get_categories_filter_platform(db):
    db.add(ServiceCategory(name="지니TV 추천", category_type="recommendation", platform="iptv_genie"))
    db.add(ServiceCategory(name="Watcha TOP10", category_type="ranking", platform="ott_watcha"))
    db.commit()
    result = service.get_categories(db, platform="iptv_genie")
    assert len(result) == 1
    assert result[0].platform == "iptv_genie"


def test_get_devices_empty(db, content):
    result = service.get_devices_for_content(db, content.id)
    assert result == []


# ── API layer ──────────────────────────────────────────────────────────────────

def test_api_channels_200(client, content):
    r = client.get(f"/api/distribution/contents/{content.id}/channels")
    assert r.status_code == 200
    assert r.json() == []


def test_api_categories_200(client):
    r = client.get("/api/distribution/categories")
    assert r.status_code == 200
    assert r.json() == []


def test_api_devices_200(client, content):
    r = client.get(f"/api/distribution/contents/{content.id}/devices")
    assert r.status_code == 200
    assert r.json() == []
