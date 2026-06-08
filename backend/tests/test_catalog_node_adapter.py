"""catalog-node-adapter Steps 1-3 — read/write-path + set-service 단위 테스트."""
import pytest

from api.programming.scheduling.models import (
    ChildType,
    LinkSource,
    LinkStatus,
    NodeKind,
    ProgrammingLink,
    ProgrammingNode,
    ProgrammingNodeSet,
)
from api.programming.scheduling.node_service import list_node_tree, list_node_tree_by_set
from api.programming.catalog import set_service


def _mk_node(db, name, kind=NodeKind.container, set_id=None):
    node = ProgrammingNode(kind=kind, name=name, set_id=set_id, is_active=True, is_draft=False)
    db.add(node)
    db.flush()
    return node


def _mk_link(db, parent_id, child_id, sort_order=0):
    lnk = ProgrammingLink(
        parent_node_id=parent_id,
        child_type=ChildType.node,
        child_node_id=child_id,
        sort_order=sort_order,
        status=LinkStatus.active,
        source="manual",
    )
    db.add(lnk)
    db.flush()
    return lnk


def _mk_content_link(db, parent_id, content_id, sort_order=0):
    lnk = ProgrammingLink(
        parent_node_id=parent_id,
        child_type=ChildType.content,
        child_content_id=content_id,
        sort_order=sort_order,
        status=LinkStatus.active,
        source="manual",
    )
    db.add(lnk)
    db.flush()
    return lnk


def test_list_node_tree_returns_nested_structure(db):
    """부모-자식 노드 링크가 중첩 트리로 직렬화됨."""
    root = _mk_node(db, "드라마")
    child = _mk_node(db, "로맨스")
    _mk_link(db, root.id, child.id, sort_order=0)

    result = list_node_tree(db)
    assert len(result) == 1
    r = result[0]
    assert r["id"] == root.id
    assert r["name"] == "드라마"
    assert r["depth"] == 0
    assert r["parent_id"] is None
    assert len(r["children"]) == 1

    c = r["children"][0]
    assert c["id"] == child.id
    assert c["name"] == "로맨스"
    assert c["depth"] == 1
    assert c["parent_id"] == root.id


def test_list_node_tree_root_filter(db):
    """root_id 지정 시 해당 노드 기준 서브트리만 반환."""
    root = _mk_node(db, "전체")
    sub = _mk_node(db, "드라마")
    leaf = _mk_node(db, "로맨스")
    _mk_link(db, root.id, sub.id, sort_order=0)
    _mk_link(db, sub.id, leaf.id, sort_order=0)

    result = list_node_tree(db, root_id=sub.id)
    assert len(result) == 1
    assert result[0]["id"] == sub.id
    assert result[0]["depth"] == 0
    assert len(result[0]["children"]) == 1
    assert result[0]["children"][0]["id"] == leaf.id


def test_list_node_tree_include_counts(db):
    """include_counts=True 시 content_count 포함."""
    node = _mk_node(db, "액션")
    _mk_content_link(db, node.id, content_id=101)
    _mk_content_link(db, node.id, content_id=102)

    result = list_node_tree(db, include_counts=True)
    assert len(result) == 1
    assert result[0]["content_count"] == 2


def test_list_node_tree_by_set(db):
    """set_id 필터 동작: 해당 세트 소속 노드만, 세트외 노드 제외."""
    ns = ProgrammingNodeSet(name="테스트 세트", status="draft")
    db.add(ns)
    db.flush()

    a = _mk_node(db, "세트내_A", set_id=ns.id)
    b = _mk_node(db, "세트내_B", set_id=ns.id)
    _mk_node(db, "세트외_C")  # set_id=None — 결과에 없어야 함
    _mk_link(db, a.id, b.id, sort_order=0)

    result = list_node_tree_by_set(db, ns.id)
    all_ids = {n["id"] for n in result}
    # 루트(a)만 최상위; b는 a의 자식
    assert len(result) == 1
    assert result[0]["id"] == a.id
    assert result[0]["children"][0]["id"] == b.id


# ── Step 3: set-service-adapter ───────────────────────────────────────────────

def _mk_draft_node(db, name, parent_id=None, sort_order=0):
    """draft(set_id=None) 카테고리 노드 생성 + 부모 링크 선택적 추가."""
    node = ProgrammingNode(kind=NodeKind.container, name=name, set_id=None, is_active=True, is_draft=False)
    db.add(node)
    db.flush()
    if parent_id is not None:
        lnk = ProgrammingLink(
            parent_node_id=parent_id,
            child_type=ChildType.node,
            child_node_id=node.id,
            sort_order=sort_order,
            status=LinkStatus.active,
            source=LinkSource.manual,
        )
        db.add(lnk)
        db.flush()
    return node


def _mk_set_node(db, name, set_id, parent_id=None, sort_order=0):
    node = ProgrammingNode(kind=NodeKind.container, name=name, set_id=set_id, is_active=True, is_draft=False)
    db.add(node)
    db.flush()
    if parent_id is not None:
        lnk = ProgrammingLink(
            parent_node_id=parent_id,
            child_type=ChildType.node,
            child_node_id=node.id,
            sort_order=sort_order,
            status=LinkStatus.active,
            source=LinkSource.manual,
        )
        db.add(lnk)
        db.flush()
    return node


def test_list_sets_empty(db):
    """세트 없으면 빈 목록."""
    assert set_service.list_sets(db) == []


def test_list_sets_with_nodes(db):
    """세트 목록 — category_count 포함."""
    ns = ProgrammingNodeSet(name="세트A")
    db.add(ns)
    db.flush()
    _mk_set_node(db, "드라마", set_id=ns.id)
    _mk_set_node(db, "로맨스", set_id=ns.id)

    result = set_service.list_sets(db)
    assert len(result) == 1
    assert result[0]["name"] == "세트A"
    assert result[0]["category_count"] == 2


def test_commit_draft_copies_nodes(db):
    """commit_draft: draft 트리를 새 세트로 복사."""
    root = _mk_draft_node(db, "드라마")
    child = _mk_draft_node(db, "로맨스", parent_id=root.id)

    info = set_service.commit_draft(db, name="테스트세트")
    assert info["category_count"] == 2
    assert info["_loaded"] == 2

    # 원본 draft 유지 확인
    draft_count = db.query(ProgrammingNode).filter(
        ProgrammingNode.set_id.is_(None), ProgrammingNode.kind == NodeKind.container
    ).count()
    assert draft_count == 2


def test_commit_draft_preserves_tree_structure(db):
    """commit_draft: 부모-자식 링크 구조가 새 세트에 그대로 복사됨."""
    root = _mk_draft_node(db, "전체")
    child = _mk_draft_node(db, "드라마", parent_id=root.id, sort_order=1)
    _mk_draft_node(db, "예능", parent_id=root.id, sort_order=2)

    info = set_service.commit_draft(db, name="구조세트")
    new_set_id = info["id"]

    from api.programming.catalog.service import list_tree_by_set
    tree = list_tree_by_set(db, set_id=new_set_id)
    assert len(tree) == 1
    assert tree[0]["name"] == "전체"
    assert len(tree[0]["children"]) == 2


def test_clear_draft_removes_nodes_and_links(db):
    """clear_draft: draft 노드 + 관련 링크 전부 삭제."""
    root = _mk_draft_node(db, "A")
    child = _mk_draft_node(db, "B", parent_id=root.id)

    cleared = set_service.clear_draft(db)
    assert cleared == 2

    remaining = db.query(ProgrammingNode).filter(
        ProgrammingNode.set_id.is_(None), ProgrammingNode.kind == NodeKind.container
    ).count()
    assert remaining == 0

    link_count = db.query(ProgrammingLink).count()
    assert link_count == 0


def test_clear_draft_ignores_set_nodes(db):
    """clear_draft: 세트 소속 노드(set_id≠None)는 건드리지 않음."""
    ns = ProgrammingNodeSet(name="보존세트")
    db.add(ns)
    db.flush()
    _mk_set_node(db, "세트노드", set_id=ns.id)
    _mk_draft_node(db, "드래프트")

    set_service.clear_draft(db)

    set_count = db.query(ProgrammingNode).filter(ProgrammingNode.set_id == ns.id).count()
    assert set_count == 1


def test_load_set_replace(db):
    """load_set(replace): draft를 세트 트리로 대체."""
    ns = ProgrammingNodeSet(name="원본세트")
    db.add(ns)
    db.flush()
    _mk_set_node(db, "드라마", set_id=ns.id)
    _mk_draft_node(db, "기존드래프트")

    cleared, loaded = set_service.load_set(db, set_id=ns.id, mode="replace")
    assert cleared == 1
    assert loaded == 1

    draft = db.query(ProgrammingNode).filter(
        ProgrammingNode.set_id.is_(None), ProgrammingNode.kind == NodeKind.container
    ).all()
    assert len(draft) == 1
    assert draft[0].name == "드라마"


def test_update_set(db):
    """update_set: name/description 변경."""
    ns = ProgrammingNodeSet(name="구이름")
    db.add(ns)
    db.flush()

    result = set_service.update_set(db, ns.id, name="새이름", description="설명")
    assert result["name"] == "새이름"
    assert result["description"] == "설명"


def test_delete_set(db):
    """delete_set: 세트 레코드 삭제."""
    ns = ProgrammingNodeSet(name="삭제세트")
    db.add(ns)
    db.flush()

    set_service.delete_set(db, ns.id)
    assert db.query(ProgrammingNodeSet).filter(ProgrammingNodeSet.id == ns.id).first() is None


def test_delete_set_not_found(db):
    """delete_set: 없는 ID는 ValueError."""
    with pytest.raises(ValueError):
        set_service.delete_set(db, 9999)


def test_preview_load_set_counts(db):
    """preview_load_set: draft와 세트 비교 — dup/new 카운트."""
    ns = ProgrammingNodeSet(name="미리보기세트")
    db.add(ns)
    db.flush()
    _mk_set_node(db, "드라마", set_id=ns.id)
    _mk_set_node(db, "예능", set_id=ns.id)
    _mk_draft_node(db, "드라마")  # 중복 1건

    result = set_service.preview_load_set(db, set_id=ns.id)
    assert result["dup_count"] == 1
    assert result["new_count"] == 1


def test_copy_tree_empty_src(db):
    """_copy_tree: 소스 노드 없으면 0 반환."""
    loaded = set_service._copy_tree(db, src_set_id=None, dst_set_id=None)
    assert loaded == 0
