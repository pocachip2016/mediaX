"""scheduling 라우터 API 테스트 (FastAPI TestClient + in-memory SQLite)."""
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


# ── NodeSet ────────────────────────────────────────────────────────────────────

def test_create_and_list_set(client):
    r = client.post(f"{BASE}/sets", json={"name": "여름 편성", "description": "2026 여름"})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "여름 편성"
    assert data["status"] == "draft"

    r2 = client.get(f"{BASE}/sets")
    assert r2.status_code == 200
    assert len(r2.json()) == 1


def test_publish_set(client):
    set_id = client.post(f"{BASE}/sets", json={"name": "봄"}).json()["id"]
    r = client.post(f"{BASE}/sets/{set_id}/publish")
    assert r.status_code == 200
    assert r.json()["status"] == "published"


def test_delete_set(client):
    set_id = client.post(f"{BASE}/sets", json={"name": "삭제"}).json()["id"]
    r = client.delete(f"{BASE}/sets/{set_id}")
    assert r.status_code == 204
    assert client.get(f"{BASE}/sets").json() == []


# ── Node CRUD ──────────────────────────────────────────────────────────────────

def test_create_and_get_node(client):
    r = client.post(f"{BASE}/nodes", json={"kind": "manual", "name": "특집"})
    assert r.status_code == 201
    node_id = r.json()["id"]

    r2 = client.get(f"{BASE}/nodes/{node_id}")
    assert r2.status_code == 200
    assert r2.json()["name"] == "특집"


def test_list_nodes_filter_kind(client):
    client.post(f"{BASE}/nodes", json={"kind": "manual", "name": "A"})
    client.post(f"{BASE}/nodes", json={"kind": "rule", "name": "B"})
    r = client.get(f"{BASE}/nodes?kind=manual")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_update_node(client):
    node_id = client.post(f"{BASE}/nodes", json={"kind": "manual", "name": "원래"}).json()["id"]
    r = client.patch(f"{BASE}/nodes/{node_id}", json={"name": "변경"})
    assert r.status_code == 200
    assert r.json()["name"] == "변경"


def test_delete_node(client):
    node_id = client.post(f"{BASE}/nodes", json={"kind": "manual", "name": "삭제"}).json()["id"]
    r = client.delete(f"{BASE}/nodes/{node_id}")
    assert r.status_code == 204
    assert client.get(f"{BASE}/nodes/{node_id}").status_code == 404


def test_get_node_404(client):
    assert client.get(f"{BASE}/nodes/9999").status_code == 404


# ── Node Tree ──────────────────────────────────────────────────────────────────

def test_get_node_tree_flat(client):
    parent_id = client.post(f"{BASE}/nodes", json={"kind": "container", "name": "Root"}).json()["id"]
    r = client.get(f"{BASE}/nodes/{parent_id}/tree")
    assert r.status_code == 200
    data = r.json()
    assert data["node"]["id"] == parent_id
    assert data["children"] == []
    assert data["content_ids"] == []


def test_get_node_tree_with_content_links(client):
    parent_id = client.post(f"{BASE}/nodes", json={"kind": "manual", "name": "P"}).json()["id"]
    client.post(f"{BASE}/nodes/{parent_id}/links", json={"child_content_id": 10})
    client.post(f"{BASE}/nodes/{parent_id}/links", json={"child_content_id": 20})
    r = client.get(f"{BASE}/nodes/{parent_id}/tree")
    assert r.status_code == 200
    assert set(r.json()["content_ids"]) == {10, 20}


def test_get_node_tree_nested_node(client):
    root_id = client.post(f"{BASE}/nodes", json={"kind": "container", "name": "Root"}).json()["id"]
    child_id = client.post(f"{BASE}/nodes", json={"kind": "manual", "name": "Child"}).json()["id"]
    client.post(f"{BASE}/nodes/{root_id}/links", json={"child_node_id": child_id})
    r = client.get(f"{BASE}/nodes/{root_id}/tree")
    assert r.status_code == 200
    assert len(r.json()["children"]) == 1
    assert r.json()["children"][0]["node"]["id"] == child_id


# ── Link CRUD ──────────────────────────────────────────────────────────────────

def test_add_and_list_links(client):
    node_id = client.post(f"{BASE}/nodes", json={"kind": "manual", "name": "N"}).json()["id"]
    r = client.post(f"{BASE}/nodes/{node_id}/links", json={"child_content_id": 5})
    assert r.status_code == 201
    assert r.json()["child_content_id"] == 5

    r2 = client.get(f"{BASE}/nodes/{node_id}/links")
    assert r2.status_code == 200
    assert len(r2.json()) == 1


def test_add_link_xor_error(client):
    node_id = client.post(f"{BASE}/nodes", json={"kind": "manual", "name": "N"}).json()["id"]
    r = client.post(f"{BASE}/nodes/{node_id}/links", json={})
    assert r.status_code == 400


def test_add_link_cycle_error(client):
    a = client.post(f"{BASE}/nodes", json={"kind": "container", "name": "A"}).json()["id"]
    b = client.post(f"{BASE}/nodes", json={"kind": "container", "name": "B"}).json()["id"]
    client.post(f"{BASE}/nodes/{a}/links", json={"child_node_id": b})
    r = client.post(f"{BASE}/nodes/{b}/links", json={"child_node_id": a})
    assert r.status_code == 400


def test_add_links_batch(client):
    node_id = client.post(f"{BASE}/nodes", json={"kind": "manual", "name": "N"}).json()["id"]
    r = client.post(f"{BASE}/nodes/{node_id}/links/batch", json={
        "children": [
            {"child_content_id": 1},
            {"child_content_id": 2},
            {"child_content_id": 1},  # 중복 — 건너뜀
        ]
    })
    assert r.status_code == 201
    assert len(r.json()) == 2


def test_reorder_links(client):
    node_id = client.post(f"{BASE}/nodes", json={"kind": "manual", "name": "N"}).json()["id"]
    l1 = client.post(f"{BASE}/nodes/{node_id}/links", json={"child_content_id": 1}).json()["id"]
    l2 = client.post(f"{BASE}/nodes/{node_id}/links", json={"child_content_id": 2}).json()["id"]
    l3 = client.post(f"{BASE}/nodes/{node_id}/links", json={"child_content_id": 3}).json()["id"]
    r = client.post(f"{BASE}/nodes/{node_id}/links/reorder", json={"ordered_link_ids": [l3, l1, l2]})
    assert r.status_code == 204
    links = client.get(f"{BASE}/nodes/{node_id}/links").json()
    order_map = {lnk["id"]: lnk["sort_order"] for lnk in links}
    assert order_map[l3] == 0
    assert order_map[l1] == 1
    assert order_map[l2] == 2


def test_update_link(client):
    node_id = client.post(f"{BASE}/nodes", json={"kind": "manual", "name": "N"}).json()["id"]
    link_id = client.post(f"{BASE}/nodes/{node_id}/links", json={"child_content_id": 9}).json()["id"]
    r = client.patch(f"{BASE}/links/{link_id}", json={"is_pinned": True, "copy_override": {"title": "핀"}})
    assert r.status_code == 200
    assert r.json()["is_pinned"] is True
    assert r.json()["copy_override"] == {"title": "핀"}


def test_move_link(client):
    p1 = client.post(f"{BASE}/nodes", json={"kind": "manual", "name": "P1"}).json()["id"]
    p2 = client.post(f"{BASE}/nodes", json={"kind": "manual", "name": "P2"}).json()["id"]
    link_id = client.post(f"{BASE}/nodes/{p1}/links", json={"child_content_id": 99}).json()["id"]
    r = client.post(f"{BASE}/links/{link_id}/move", json={"new_parent_node_id": p2})
    assert r.status_code == 200
    assert r.json()["parent_node_id"] == p2


def test_delete_link(client):
    node_id = client.post(f"{BASE}/nodes", json={"kind": "manual", "name": "N"}).json()["id"]
    link_id = client.post(f"{BASE}/nodes/{node_id}/links", json={"child_content_id": 1}).json()["id"]
    r = client.delete(f"{BASE}/links/{link_id}")
    assert r.status_code == 204
    assert client.get(f"{BASE}/nodes/{node_id}/links").json() == []


# ── Backref ────────────────────────────────────────────────────────────────────

def test_content_backref(client):
    p1 = client.post(f"{BASE}/nodes", json={"kind": "manual", "name": "P1"}).json()["id"]
    p2 = client.post(f"{BASE}/nodes", json={"kind": "manual", "name": "P2"}).json()["id"]
    client.post(f"{BASE}/nodes/{p1}/links", json={"child_content_id": 77})
    client.post(f"{BASE}/nodes/{p2}/links", json={"child_content_id": 77})
    r = client.get(f"{BASE}/backref/content/77")
    assert r.status_code == 200
    assert len(r.json()) == 2
    parent_ids = {ref["parent_node_id"] for ref in r.json()}
    assert parent_ids == {p1, p2}


def test_node_backref(client):
    parent = client.post(f"{BASE}/nodes", json={"kind": "container", "name": "P"}).json()["id"]
    child = client.post(f"{BASE}/nodes", json={"kind": "manual", "name": "C"}).json()["id"]
    client.post(f"{BASE}/nodes/{parent}/links", json={"child_node_id": child})
    r = client.get(f"{BASE}/backref/node/{child}")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["parent_node_id"] == parent
