"""
Step 3 검증 — ServiceCategory CRUD + 아이템 관리 API (노드 어댑터 기반)

service_categories/service_category_items 테이블 제거 후
ProgrammingNode/Link 어댑터로 동일 계약 유지 확인.
"""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from shared.database import get_db
from api.distribution.schemas import (
    ServiceCategoryCreate, ServiceCategoryUpdate,
    ServiceCategoryItemCreate, ReorderRequest, ReorderItem,
)
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
    obj = Content(title="테스트 영화", content_type="movie", status="raw")
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@pytest.fixture
def content2(db):
    obj = Content(title="두번째 영화", content_type="movie", status="raw")
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@pytest.fixture
def category(db):
    return service.create_category(db, ServiceCategoryCreate(
        name="TOP10", category_type="top10", platform="ott_watcha", position=0,
    ))


@pytest.fixture
def item(db, category, content):
    return service.add_item(db, category.id, ServiceCategoryItemCreate(
        content_id=content.id, rank=1,
    ))


# ── service 계층 ───────────────────────────────────────────────────────────────

def test_create_category(db):
    data = ServiceCategoryCreate(name="신작 추천", category_type="recommendation", platform="iptv_genie", position=0)
    result = service.create_category(db, data)
    assert result.id is not None
    assert result.name == "신작 추천"
    assert result.platform == "iptv_genie"


def test_get_category_or_404_found(db, category):
    result = service.get_category_or_404(db, category.id)
    assert result.id == category.id


def test_get_category_or_404_not_found(db):
    with pytest.raises(HTTPException) as exc:
        service.get_category_or_404(db, 99999)
    assert exc.value.status_code == 404


def test_get_category_with_items(db, category, item):
    result = service.get_category_with_items(db, category.id)
    assert result.id == category.id
    assert len(result.items) == 1
    assert result.items[0].content_title == "테스트 영화"


def test_update_category(db, category):
    data = ServiceCategoryUpdate(name="Updated TOP10", is_active=False)
    result = service.update_category(db, category.id, data)
    assert result.name == "Updated TOP10"
    assert result.is_active is False


def test_delete_category(db, category):
    result = service.delete_category(db, category.id)
    assert result["deleted"] is True
    assert service.get_categories(db) == []


def test_add_item(db, category, content):
    data = ServiceCategoryItemCreate(content_id=content.id, rank=1, score=0.9)
    result = service.add_item(db, category.id, data)
    assert result.rank == 1
    assert result.content_title == "테스트 영화"


def test_add_item_duplicate_409(db, category, content, item):
    data = ServiceCategoryItemCreate(content_id=content.id, rank=2)
    with pytest.raises(HTTPException) as exc:
        service.add_item(db, category.id, data)
    assert exc.value.status_code == 409


def test_remove_item(db, category, item):
    result = service.remove_item(db, category.id, item.id)
    assert result["deleted"] is True
    assert service.get_category_with_items(db, category.id).items == []


def test_remove_item_wrong_category(db, category, item):
    with pytest.raises(HTTPException) as exc:
        service.remove_item(db, 99999, item.id)
    assert exc.value.status_code == 404


def test_reorder_items(db, category, content, content2):
    item1 = service.add_item(db, category.id, ServiceCategoryItemCreate(content_id=content.id, rank=1))
    item2 = service.add_item(db, category.id, ServiceCategoryItemCreate(content_id=content2.id, rank=2))

    data = ReorderRequest(items=[
        ReorderItem(id=item1.id, rank=2),
        ReorderItem(id=item2.id, rank=1),
    ])
    result = service.reorder_items(db, category.id, data)
    assert result["updated"] == 2

    detail = service.get_category_with_items(db, category.id)
    ranks = {i.content_id: i.rank for i in detail.items}
    assert ranks[content.id] == 2
    assert ranks[content2.id] == 1


# ── API 계층 ────────────────────────────────────────────────────────────────────

def test_api_create_category_201(client):
    r = client.post("/api/distribution/categories", json={
        "name": "장르 편성", "category_type": "genre", "platform": "ott_netflix", "position": 0,
    })
    assert r.status_code == 201
    assert r.json()["name"] == "장르 편성"


def test_api_get_category_200(client, category):
    r = client.get(f"/api/distribution/categories/{category.id}")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "TOP10"
    assert "items" in data


def test_api_get_category_404(client):
    r = client.get("/api/distribution/categories/99999")
    assert r.status_code == 404


def test_api_update_category_200(client, category):
    r = client.put(f"/api/distribution/categories/{category.id}", json={"name": "NEW TOP10"})
    assert r.status_code == 200
    assert r.json()["name"] == "NEW TOP10"


def test_api_delete_category_200(client, category):
    r = client.delete(f"/api/distribution/categories/{category.id}")
    assert r.status_code == 200
    assert r.json()["deleted"] is True


def test_api_add_item_201(client, category, content):
    r = client.post(f"/api/distribution/categories/{category.id}/items", json={
        "content_id": content.id, "rank": 1,
    })
    assert r.status_code == 201
    assert r.json()["rank"] == 1


def test_api_add_item_duplicate_409(client, category, content, item):
    r = client.post(f"/api/distribution/categories/{category.id}/items", json={
        "content_id": content.id, "rank": 2,
    })
    assert r.status_code == 409


def test_api_remove_item_200(client, category, item):
    r = client.delete(f"/api/distribution/categories/{category.id}/items/{item.id}")
    assert r.status_code == 200
    assert r.json()["deleted"] is True


def test_api_reorder_items_200(client, category, item):
    r = client.post(f"/api/distribution/categories/{category.id}/items/reorder", json={
        "items": [{"id": item.id, "rank": 5}],
    })
    assert r.status_code == 200
    assert r.json()["updated"] == 1
