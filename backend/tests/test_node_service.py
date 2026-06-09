"""node_service 단위 테스트 — SQLite in-memory."""
import pytest

from api.programming.scheduling.models import NodeKind, ProgrammingLink, LinkStatus
from api.programming.scheduling.node_service import (
    compute_members,
    create_node,
    create_node_set,
    delete_node,
    delete_node_set,
    get_node,
    get_node_set,
    list_node_sets,
    list_nodes,
    publish_node_set,
    update_node,
    would_create_cycle,
)


# ── NodeSet CRUD ───────────────────────────────────────────────────────────────

def test_create_and_get_node_set(db):
    ns = create_node_set(db, name="여름 편성", description="2026 여름")
    assert ns.id is not None
    assert ns.status == "draft"
    fetched = get_node_set(db, ns.id)
    assert fetched.name == "여름 편성"


def test_publish_node_set(db):
    ns = create_node_set(db, name="봄 편성")
    published = publish_node_set(db, ns.id)
    assert published.status == "published"
    assert published.published_at is not None


def test_list_node_sets_filter_status(db):
    create_node_set(db, name="A")
    ns2 = create_node_set(db, name="B")
    publish_node_set(db, ns2.id)
    drafts = list_node_sets(db, status="draft")
    pubs = list_node_sets(db, status="published")
    assert len(drafts) == 1 and drafts[0].name == "A"
    assert len(pubs) == 1 and pubs[0].name == "B"


def test_delete_node_set(db):
    ns = create_node_set(db, name="삭제할 편성")
    delete_node_set(db, ns.id)
    assert get_node_set(db, ns.id) is None


# ── Node CRUD ──────────────────────────────────────────────────────────────────

def test_create_container_node(db):
    node = create_node(db, NodeKind.container, "홈 Top")
    assert node.id is not None
    assert node.kind == NodeKind.container
    assert node.is_active is True
    assert node.is_draft is False


def test_create_rule_node(db):
    node = create_node(
        db, NodeKind.rule, "액션 자동",
        rule_query={"genre": "action"},
    )
    assert node.rule_query == {"genre": "action"}


def test_update_node(db):
    node = create_node(db, NodeKind.manual, "특집")
    updated = update_node(db, node.id, name="설 특집", is_draft=True)
    assert updated.name == "설 특집"
    assert updated.is_draft is True


def test_update_node_unknown_field_raises(db):
    node = create_node(db, NodeKind.manual, "테스트")
    with pytest.raises(ValueError, match="not updatable"):
        update_node(db, node.id, kind=NodeKind.rule)


def test_list_nodes_filter(db):
    create_node(db, NodeKind.container, "A")
    create_node(db, NodeKind.rule, "B")
    create_node(db, NodeKind.manual, "C")
    assert len(list_nodes(db, kind=NodeKind.container)) == 1
    assert len(list_nodes(db, kind=NodeKind.rule)) == 1
    assert len(list_nodes(db)) == 3


def test_delete_node(db):
    node = create_node(db, NodeKind.manual, "삭제")
    delete_node(db, node.id)
    assert get_node(db, node.id) is None


# ── 사이클 가드 ────────────────────────────────────────────────────────────────

def _add_node_link(db, parent_id: int, child_id: int):
    lnk = ProgrammingLink(
        parent_node_id=parent_id,
        child_type="node",
        child_node_id=child_id,
        sort_order=0,
        source="manual",
        status=LinkStatus.active,
    )
    db.add(lnk)
    db.flush()
    return lnk


def test_no_cycle_simple(db):
    a = create_node(db, NodeKind.container, "A")
    b = create_node(db, NodeKind.container, "B")
    assert not would_create_cycle(db, a.id, b.id)


def test_self_loop_detected(db):
    a = create_node(db, NodeKind.container, "A")
    assert would_create_cycle(db, a.id, a.id)


def test_direct_cycle_detected(db):
    a = create_node(db, NodeKind.container, "A")
    b = create_node(db, NodeKind.container, "B")
    _add_node_link(db, a.id, b.id)
    # B → A 추가하면 A→B→A 사이클
    assert would_create_cycle(db, b.id, a.id)


def test_transitive_cycle_detected(db):
    a = create_node(db, NodeKind.container, "A")
    b = create_node(db, NodeKind.container, "B")
    c = create_node(db, NodeKind.container, "C")
    _add_node_link(db, a.id, b.id)
    _add_node_link(db, b.id, c.id)
    # C → A 추가하면 A→B→C→A 사이클
    assert would_create_cycle(db, c.id, a.id)


def test_no_cycle_fork(db):
    root = create_node(db, NodeKind.container, "Root")
    left = create_node(db, NodeKind.container, "Left")
    right = create_node(db, NodeKind.container, "Right")
    _add_node_link(db, root.id, left.id)
    _add_node_link(db, root.id, right.id)
    # left → right는 사이클 아님
    assert not would_create_cycle(db, left.id, right.id)


# ── read-time 멤버 산출 ────────────────────────────────────────────────────────

def _add_content_link(db, parent_id: int, content_id: int, sort_order: int = 0,
                      is_pinned: bool = False, status=LinkStatus.active):
    lnk = ProgrammingLink(
        parent_node_id=parent_id,
        child_type="content",
        child_content_id=content_id,
        sort_order=sort_order,
        is_pinned=is_pinned,
        source="manual",
        status=status,
    )
    db.add(lnk)
    db.flush()
    return lnk


def test_compute_members_basic(db):
    node = create_node(db, NodeKind.manual, "특집")
    _add_content_link(db, node.id, 1, sort_order=2)
    _add_content_link(db, node.id, 2, sort_order=1)
    members = compute_members(db, node)
    assert [m.content_id for m in members] == [2, 1]


def test_compute_members_pinned_first(db):
    node = create_node(db, NodeKind.manual, "특집")
    _add_content_link(db, node.id, 1, sort_order=0)
    _add_content_link(db, node.id, 2, sort_order=99, is_pinned=True)
    members = compute_members(db, node)
    assert members[0].content_id == 2  # pinned 우선
    assert members[0].is_pinned is True


def test_compute_members_excludes_suggested(db):
    node = create_node(db, NodeKind.manual, "특집")
    _add_content_link(db, node.id, 1)
    _add_content_link(db, node.id, 2, status=LinkStatus.suggested)
    _add_content_link(db, node.id, 3, status=LinkStatus.rejected)
    members = compute_members(db, node)
    assert len(members) == 1
    assert members[0].content_id == 1


def test_compute_members_pinned_link_has_source_manual(db):
    node = create_node(db, NodeKind.manual, "특집")
    _add_content_link(db, node.id, 10, sort_order=0, is_pinned=True)
    members = compute_members(db, node)
    assert len(members) == 1
    assert members[0].source == "manual"
    assert members[0].is_pinned is True
