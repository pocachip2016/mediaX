"""
카탈로그 API 테스트 (FastAPI TestClient + in-memory SQLite)

검증 케이스:
  - GET /categories/tree — 빈 트리, 중첩 트리
  - POST /categories — 루트/자식 생성
  - PATCH /categories/{id} — rename + is_active
  - POST /categories/{id}/move — 정상 이동, 사이클 409
  - DELETE /categories/{id} — 비어있으면 204, 자식있으면 409
  - POST /contents/{id}/categories — 매핑 happy-path
"""
import pytest
from fastapi.testclient import TestClient

from shared.database import get_db
from api.programming.metadata.models import Content, ContentType, ContentStatus


@pytest.fixture
def client(db):
    from main import app
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def content(db):
    c = Content(title="테스트콘텐츠", content_type=ContentType.movie, status=ContentStatus.raw, cp_name="TEST")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


BASE = "/api/programming/catalog"


# ── 트리 조회 ─────────────────────────────────────────────────────────────────

def test_get_tree_empty(client):
    res = client.get(f"{BASE}/categories/tree")
    assert res.status_code == 200
    assert res.json() == []


def test_get_tree_nested(client):
    r1 = client.post(f"{BASE}/categories", json={"name": "영화"})
    assert r1.status_code == 201
    root_id = r1.json()["id"]

    r2 = client.post(f"{BASE}/categories", json={"name": "액션", "parent_id": root_id})
    assert r2.status_code == 201

    res = client.get(f"{BASE}/categories/tree")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["name"] == "영화"
    assert len(data[0]["children"]) == 1
    assert data[0]["children"][0]["name"] == "액션"


# ── 생성 ─────────────────────────────────────────────────────────────────────

def test_create_root_category(client):
    res = client.post(f"{BASE}/categories", json={"name": "영화"})
    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "영화"
    assert body["depth"] == 0
    assert body["parent_id"] is None


def test_create_child_category(client):
    root = client.post(f"{BASE}/categories", json={"name": "영화"}).json()
    res = client.post(f"{BASE}/categories", json={"name": "액션", "parent_id": root["id"]})
    assert res.status_code == 201
    body = res.json()
    assert body["depth"] == 1
    assert body["parent_id"] == root["id"]


def test_create_with_nonexistent_parent_404(client):
    res = client.post(f"{BASE}/categories", json={"name": "액션", "parent_id": 9999})
    assert res.status_code == 404


# ── 일괄(Bulk) 생성 ──────────────────────────────────────────────────────────

def test_bulk_create_nested(client):
    payload = {
        "nodes": [
            {"name": "영화", "children": [{"name": "액션"}, {"name": "코미디"}]},
            {"name": "시리즈", "children": [
                {"name": "드라마", "children": [{"name": "미니시리즈"}]},
            ]},
        ]
    }
    res = client.post(f"{BASE}/categories/bulk", json=payload)
    assert res.status_code == 201
    body = res.json()
    assert body["created"] == 6
    assert body["skipped"] == 0

    tree = body["tree"]
    names = {n["name"] for n in tree}
    assert names == {"영화", "시리즈"}
    movie = next(n for n in tree if n["name"] == "영화")
    assert {c["name"] for c in movie["children"]} == {"액션", "코미디"}
    series = next(n for n in tree if n["name"] == "시리즈")
    drama = series["children"][0]
    assert drama["name"] == "드라마"
    assert drama["children"][0]["name"] == "미니시리즈"
    assert drama["children"][0]["depth"] == 2


def test_bulk_create_skips_duplicates(client):
    client.post(f"{BASE}/categories", json={"name": "영화"})
    payload = {
        "nodes": [
            {"name": "영화", "children": [{"name": "액션"}]},  # 영화 중복 → skip, 액션 신규
            {"name": "키즈"},
        ]
    }
    res = client.post(f"{BASE}/categories/bulk", json=payload)
    assert res.status_code == 201
    body = res.json()
    assert body["created"] == 2  # 액션 + 키즈
    assert body["skipped"] == 1  # 영화

    # 액션이 기존 "영화" 밑에 생성됐는지 확인
    movie = next(n for n in body["tree"] if n["name"] == "영화")
    assert {c["name"] for c in movie["children"]} == {"액션"}


def test_bulk_create_under_parent(client):
    root = client.post(f"{BASE}/categories", json={"name": "영화"}).json()
    payload = {
        "parent_id": root["id"],
        "nodes": [{"name": "액션"}, {"name": "코미디"}],
    }
    res = client.post(f"{BASE}/categories/bulk", json=payload)
    assert res.status_code == 201
    body = res.json()
    assert body["created"] == 2
    # tree는 parent 서브트리(영화) 1개 루트
    assert len(body["tree"]) == 1
    assert body["tree"][0]["name"] == "영화"
    assert {c["name"] for c in body["tree"][0]["children"]} == {"액션", "코미디"}


def test_bulk_create_nonexistent_parent_404(client):
    res = client.post(f"{BASE}/categories/bulk", json={"parent_id": 9999, "nodes": [{"name": "x"}]})
    assert res.status_code == 404


# ── 수정 ─────────────────────────────────────────────────────────────────────

def test_patch_rename(client):
    root = client.post(f"{BASE}/categories", json={"name": "영화"}).json()
    res = client.patch(f"{BASE}/categories/{root['id']}", json={"name": "드라마"})
    assert res.status_code == 200
    assert res.json()["name"] == "드라마"


def test_patch_deactivate(client):
    root = client.post(f"{BASE}/categories", json={"name": "영화"}).json()
    res = client.patch(f"{BASE}/categories/{root['id']}", json={"is_active": False})
    assert res.status_code == 200
    assert res.json()["is_active"] is False


# ── 이동 ─────────────────────────────────────────────────────────────────────

def test_move_category(client):
    src = client.post(f"{BASE}/categories", json={"name": "소스"}).json()
    dst = client.post(f"{BASE}/categories", json={"name": "타겟"}).json()

    res = client.post(f"{BASE}/categories/{src['id']}/move", json={"new_parent_id": dst["id"]})
    assert res.status_code == 200
    body = res.json()
    assert body["parent_id"] == dst["id"]
    assert body["depth"] == 1


def test_move_into_descendant_returns_409(client):
    root = client.post(f"{BASE}/categories", json={"name": "루트"}).json()
    child = client.post(f"{BASE}/categories", json={"name": "자식", "parent_id": root["id"]}).json()

    res = client.post(f"{BASE}/categories/{root['id']}/move", json={"new_parent_id": child["id"]})
    assert res.status_code == 409


# ── 삭제 ─────────────────────────────────────────────────────────────────────

def test_delete_empty_category(client):
    root = client.post(f"{BASE}/categories", json={"name": "영화"}).json()
    res = client.delete(f"{BASE}/categories/{root['id']}")
    assert res.status_code == 204


def test_delete_with_children_returns_409(client):
    root = client.post(f"{BASE}/categories", json={"name": "영화"}).json()
    client.post(f"{BASE}/categories", json={"name": "액션", "parent_id": root["id"]})
    res = client.delete(f"{BASE}/categories/{root['id']}")
    assert res.status_code == 409


def test_delete_nonexistent_returns_404(client):
    res = client.delete(f"{BASE}/categories/9999")
    assert res.status_code == 404


# ── 콘텐츠 매핑 ───────────────────────────────────────────────────────────────

def test_map_content_happy_path(client, content):
    cat = client.post(f"{BASE}/categories", json={"name": "영화"}).json()
    res = client.post(
        f"{BASE}/contents/{content.id}/categories",
        json={"category_ids": [cat["id"]]},
    )
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 1
    assert rows[0]["category_id"] == cat["id"]
    assert rows[0]["content_id"] == content.id


def test_map_content_idempotent(client, content):
    cat = client.post(f"{BASE}/categories", json={"name": "영화"}).json()
    client.post(f"{BASE}/contents/{content.id}/categories", json={"category_ids": [cat["id"]]})
    res = client.post(f"{BASE}/contents/{content.id}/categories", json={"category_ids": [cat["id"]]})
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_get_category_contents(client, content):
    cat = client.post(f"{BASE}/categories", json={"name": "영화"}).json()
    client.post(f"{BASE}/contents/{content.id}/categories", json={"category_ids": [cat["id"]]})
    res = client.get(f"{BASE}/categories/{cat['id']}/contents")
    assert res.status_code == 200
    assert len(res.json()) == 1
