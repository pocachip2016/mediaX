"""
카테고리 세트 CRUD API 테스트 (FastAPI TestClient + in-memory SQLite)

검증:
  - POST /sets — draft → 새 세트 스냅샷, draft 유지
  - GET /sets — category_count 정확
  - PATCH /sets/{id} — 이름/설명 변경
  - DELETE /sets/{id} — 세트 + 소속 카테고리 cascade 제거
  - POST /sets/{id}/load — draft 교체 + parent 관계 보존
  - POST /sets/clear-draft — draft 비움, 세트 무영향
  - draft 필터 회귀: commit 후 GET /categories/tree 노드 수 불변
"""
import pytest
from fastapi.testclient import TestClient

from shared.database import get_db

BASE = "/api/programming/catalog"


@pytest.fixture
def client(db):
    from main import app
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _make_draft(client, names=("영화", "드라마")):
    """루트 카테고리 여러 개 생성하여 draft 구성."""
    ids = []
    for name in names:
        r = client.post(f"{BASE}/categories", json={"name": name})
        assert r.status_code == 201
        ids.append(r.json()["id"])
    return ids


# ── commit ────────────────────────────────────────────────────────────────────

def test_commit_creates_set(client):
    _make_draft(client, ("영화", "드라마"))
    r = client.post(f"{BASE}/sets", json={"name": "테스트세트"})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "테스트세트"
    assert data["category_count"] == 2


def test_commit_preserves_draft(client):
    """commit 후 draft(작업 트리)는 그대로 남아있어야 한다."""
    _make_draft(client, ("영화",))
    client.post(f"{BASE}/sets", json={"name": "세트A"})
    # draft 트리 노드 수 불변
    tree = client.get(f"{BASE}/categories/tree").json()
    assert len(tree) == 1
    assert tree[0]["name"] == "영화"


def test_commit_draft_filter_regression(client):
    """commit 후 GET /categories/tree에 세트 카테고리가 섞이지 않아야 한다."""
    _make_draft(client, ("영화", "드라마", "애니"))
    client.post(f"{BASE}/sets", json={"name": "세트A"})
    client.post(f"{BASE}/sets", json={"name": "세트B"})
    tree = client.get(f"{BASE}/categories/tree").json()
    # draft 3개만 보여야 함 (세트 카테고리 6개가 섞이면 9가 됨)
    assert len(tree) == 3


def test_commit_with_children(client):
    """중첩 트리도 올바르게 스냅샷된다."""
    r_root = client.post(f"{BASE}/categories", json={"name": "영화"})
    root_id = r_root.json()["id"]
    client.post(f"{BASE}/categories", json={"name": "액션", "parent_id": root_id})
    client.post(f"{BASE}/categories", json={"name": "로맨스", "parent_id": root_id})

    r = client.post(f"{BASE}/sets", json={"name": "중첩세트"})
    assert r.status_code == 201
    assert r.json()["category_count"] == 3  # 루트1 + 자식2


# ── list ──────────────────────────────────────────────────────────────────────

def test_list_sets_category_count(client):
    _make_draft(client, ("영화", "드라마"))
    client.post(f"{BASE}/sets", json={"name": "A"})
    _make_draft(client, ("애니",))
    client.post(f"{BASE}/sets", json={"name": "B"})
    r = client.get(f"{BASE}/sets")
    assert r.status_code == 200
    sets = r.json()
    assert len(sets) == 2
    counts = {s["name"]: s["category_count"] for s in sets}
    assert counts["A"] == 2
    assert counts["B"] == 3  # A=2 + 추가 1


def test_list_sets_empty(client):
    r = client.get(f"{BASE}/sets")
    assert r.status_code == 200
    assert r.json() == []


# ── update ────────────────────────────────────────────────────────────────────

def test_update_set_name(client):
    _make_draft(client, ("영화",))
    set_id = client.post(f"{BASE}/sets", json={"name": "구이름"}).json()["id"]
    r = client.patch(f"{BASE}/sets/{set_id}", json={"name": "신이름"})
    assert r.status_code == 200
    assert r.json()["name"] == "신이름"


def test_update_set_not_found(client):
    r = client.patch(f"{BASE}/sets/9999", json={"name": "X"})
    assert r.status_code == 404


# ── delete ────────────────────────────────────────────────────────────────────

def test_delete_set(client):
    _make_draft(client, ("영화",))
    set_id = client.post(f"{BASE}/sets", json={"name": "삭제세트"}).json()["id"]
    r = client.delete(f"{BASE}/sets/{set_id}")
    assert r.status_code == 204
    sets = client.get(f"{BASE}/sets").json()
    assert all(s["id"] != set_id for s in sets)


def test_delete_set_cascades_categories(client):
    """세트 삭제 시 소속 카테고리도 함께 제거된다."""
    _make_draft(client, ("영화", "드라마"))
    set_id = client.post(f"{BASE}/sets", json={"name": "삭제테스트"}).json()["id"]
    # 세트 카테고리 2개 있는지 확인
    assert client.get(f"{BASE}/sets").json()[0]["category_count"] == 2
    client.delete(f"{BASE}/sets/{set_id}")
    # draft는 여전히 존재
    tree = client.get(f"{BASE}/categories/tree").json()
    assert len(tree) == 2


def test_delete_set_not_found(client):
    r = client.delete(f"{BASE}/sets/9999")
    assert r.status_code == 404


# ── load ──────────────────────────────────────────────────────────────────────

def test_load_replaces_draft(client):
    """load 후 draft가 세트 트리로 교체된다."""
    _make_draft(client, ("영화", "드라마"))
    set_id = client.post(f"{BASE}/sets", json={"name": "세트A"}).json()["id"]

    # draft를 다르게 수정
    client.post(f"{BASE}/sets/clear-draft")
    client.post(f"{BASE}/categories", json={"name": "애니"})

    tree_before = client.get(f"{BASE}/categories/tree").json()
    assert len(tree_before) == 1 and tree_before[0]["name"] == "애니"

    # load
    r = client.post(f"{BASE}/sets/{set_id}/load")
    assert r.status_code == 200
    body = r.json()
    assert body["loaded"] == 2

    tree_after = client.get(f"{BASE}/categories/tree").json()
    names = {n["name"] for n in tree_after}
    assert names == {"영화", "드라마"}


def test_load_preserves_parent_relation(client):
    """load 후 parent-child 관계가 올바르게 복원된다."""
    root_id = client.post(f"{BASE}/categories", json={"name": "영화"}).json()["id"]
    client.post(f"{BASE}/categories", json={"name": "액션", "parent_id": root_id})
    set_id = client.post(f"{BASE}/sets", json={"name": "트리세트"}).json()["id"]

    client.post(f"{BASE}/sets/clear-draft")
    client.post(f"{BASE}/sets/{set_id}/load")

    tree = client.get(f"{BASE}/categories/tree").json()
    assert len(tree) == 1
    assert len(tree[0]["children"]) == 1
    assert tree[0]["children"][0]["name"] == "액션"


def test_load_not_found(client):
    r = client.post(f"{BASE}/sets/9999/load")
    assert r.status_code == 404


def test_load_replace_mode_explicit(client):
    """mode=replace 명시 시 기존 동작과 동일하게 draft 교체."""
    _make_draft(client, ("영화", "드라마"))
    set_id = client.post(f"{BASE}/sets", json={"name": "세트A"}).json()["id"]
    client.post(f"{BASE}/sets/clear-draft")
    client.post(f"{BASE}/categories", json={"name": "애니"})

    r = client.post(f"{BASE}/sets/{set_id}/load", json={"mode": "replace"})
    assert r.status_code == 200
    names = {n["name"] for n in client.get(f"{BASE}/categories/tree").json()}
    assert names == {"영화", "드라마"}


def test_load_merge_mode_keeps_existing(client):
    """mode=merge 시 draft를 비우지 않고 세트 트리를 병합한다."""
    _make_draft(client, ("영화", "드라마"))
    set_id = client.post(f"{BASE}/sets", json={"name": "세트A"}).json()["id"]
    client.post(f"{BASE}/sets/clear-draft")
    client.post(f"{BASE}/categories", json={"name": "애니"})

    r = client.post(f"{BASE}/sets/{set_id}/load", json={"mode": "merge"})
    assert r.status_code == 200
    body = r.json()
    assert body["cleared"] == 0
    assert body["loaded"] == 2  # 영화, 드라마 신규 추가
    names = {n["name"] for n in client.get(f"{BASE}/categories/tree").json()}
    assert names == {"애니", "영화", "드라마"}


def test_load_merge_dedup_merge_policy(client):
    """merge 모드 + dup_policy=merge: 동일 경로는 기존 유지, 신규만 추가."""
    root_id = client.post(f"{BASE}/categories", json={"name": "영화"}).json()["id"]
    client.post(f"{BASE}/categories", json={"name": "액션", "parent_id": root_id})
    set_id = client.post(f"{BASE}/sets", json={"name": "세트A"}).json()["id"]
    # draft에 영화(중복) + 코미디 자식 남기고 clear 후 재구성
    client.post(f"{BASE}/sets/clear-draft")
    root2 = client.post(f"{BASE}/categories", json={"name": "영화"}).json()["id"]
    client.post(f"{BASE}/categories", json={"name": "코미디", "parent_id": root2})

    r = client.post(
        f"{BASE}/sets/{set_id}/load",
        json={"mode": "merge", "dup_policy": "merge"},
    )
    assert r.status_code == 200
    tree = client.get(f"{BASE}/categories/tree").json()
    assert len(tree) == 1  # 영화 루트 하나로 병합
    child_names = {c["name"] for c in tree[0]["children"]}
    assert child_names == {"코미디", "액션"}  # 둘 다 보존


# ── clear-draft ───────────────────────────────────────────────────────────────

def test_clear_draft(client):
    _make_draft(client, ("영화", "드라마"))
    client.post(f"{BASE}/sets", json={"name": "보관세트"})

    r = client.post(f"{BASE}/sets/clear-draft")
    assert r.status_code == 200
    assert r.json()["cleared"] >= 2

    # draft 비워짐
    tree = client.get(f"{BASE}/categories/tree").json()
    assert tree == []

    # 세트는 무영향
    sets = client.get(f"{BASE}/sets").json()
    assert len(sets) == 1
    assert sets[0]["category_count"] == 2


def test_clear_draft_empty(client):
    """draft가 비어있어도 에러 없이 0 반환."""
    r = client.post(f"{BASE}/sets/clear-draft")
    assert r.status_code == 200
    assert r.json()["cleared"] == 0


# ── 전체 사이클 e2e ───────────────────────────────────────────────────────────

def test_e2e_full_cycle(client):
    """
    draft 생성 → commit(A) → draft 수정 → commit(B) →
    load(A) 교체 → clear-draft → sets 2건 유지 →
    delete(B) → 1건 + B 소속 카테고리 제거.
    """
    # 1. draft 트리 구성: 영화(루트) + 액션(자식)
    root_id = client.post(f"{BASE}/categories", json={"name": "영화"}).json()["id"]
    client.post(f"{BASE}/categories", json={"name": "액션", "parent_id": root_id})

    # 2. commit → 세트 A (카테고리 2개)
    set_a = client.post(f"{BASE}/sets", json={"name": "세트A"}).json()
    assert set_a["category_count"] == 2

    # 3. draft 수정: 드라마 추가
    client.post(f"{BASE}/categories", json={"name": "드라마"})

    # 4. commit → 세트 B (카테고리 3개)
    set_b = client.post(f"{BASE}/sets", json={"name": "세트B"}).json()
    assert set_b["category_count"] == 3

    # 5. draft는 여전히 3노드
    tree = client.get(f"{BASE}/categories/tree").json()
    assert len(tree) == 2  # 영화(액션 포함) + 드라마

    # 6. load(A) → draft가 A 트리로 교체
    r_load = client.post(f"{BASE}/sets/{set_a['id']}/load")
    assert r_load.status_code == 200
    body = r_load.json()
    assert body["loaded"] == 2

    tree_after_load = client.get(f"{BASE}/categories/tree").json()
    assert len(tree_after_load) == 1  # 영화 루트만
    assert tree_after_load[0]["name"] == "영화"
    assert len(tree_after_load[0]["children"]) == 1  # 액션 자식 복원

    # 7. clear-draft
    r_clear = client.post(f"{BASE}/sets/clear-draft")
    assert r_clear.status_code == 200
    assert r_clear.json()["cleared"] > 0

    tree_empty = client.get(f"{BASE}/categories/tree").json()
    assert tree_empty == []

    # 8. sets 2건 유지 (A, B)
    sets = client.get(f"{BASE}/sets").json()
    assert len(sets) == 2

    # 9. delete(B) → B 제거 + 소속 카테고리도 사라짐
    r_del = client.delete(f"{BASE}/sets/{set_b['id']}")
    assert r_del.status_code == 204

    sets_after = client.get(f"{BASE}/sets").json()
    assert len(sets_after) == 1
    assert sets_after[0]["id"] == set_a["id"]
    assert sets_after[0]["category_count"] == 2  # A 세트 카테고리 유지
