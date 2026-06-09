"""link_service 단위 테스트 — SQLite in-memory."""
from datetime import date

import pytest

from api.programming.scheduling.models import (
    LinkSource,
    LinkStatus,
    NodeKind,
    ProgrammingLink,
)
from api.programming.scheduling.link_service import (
    Backref,
    add_link,
    add_links_batch,
    check_window_within_node,
    get_backrefs,
    move_link,
    remove_link,
    reorder_links,
    update_link,
)
from api.programming.scheduling.node_service import (
    compute_members,
    create_node,
)


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def _node(db, name="노드", kind=NodeKind.manual):
    return create_node(db, kind, name)


# ── add_link ──────────────────────────────────────────────────────────────────

def test_add_link_content(db):
    parent = _node(db)
    lnk = add_link(db, parent.id, child_content_id=10)
    assert lnk.id is not None
    assert lnk.child_content_id == 10
    assert lnk.child_type.value == "content"


def test_add_link_node(db):
    parent = _node(db, "부모")
    child = _node(db, "자식")
    lnk = add_link(db, parent.id, child_node_id=child.id)
    assert lnk.child_node_id == child.id
    assert lnk.child_type.value == "node"


def test_add_link_child_xor_both_raises(db):
    parent = _node(db)
    child = _node(db)
    with pytest.raises(ValueError, match="정확히 하나"):
        add_link(db, parent.id, child_node_id=child.id, child_content_id=1)


def test_add_link_child_xor_none_raises(db):
    parent = _node(db)
    with pytest.raises(ValueError, match="정확히 하나"):
        add_link(db, parent.id)


def test_add_link_duplicate_raises(db):
    parent = _node(db)
    add_link(db, parent.id, child_content_id=5)
    with pytest.raises(ValueError, match="이미 동일한"):
        add_link(db, parent.id, child_content_id=5)


def test_add_link_sort_order_auto_append(db):
    parent = _node(db)
    l1 = add_link(db, parent.id, child_content_id=1)
    l2 = add_link(db, parent.id, child_content_id=2)
    l3 = add_link(db, parent.id, child_content_id=3)
    assert l1.sort_order == 0
    assert l2.sort_order == 1
    assert l3.sort_order == 2


def test_add_link_explicit_sort_order(db):
    parent = _node(db)
    lnk = add_link(db, parent.id, child_content_id=7, sort_order=99)
    assert lnk.sort_order == 99


def test_add_link_multi_parent_allowed(db):
    parent1 = _node(db, "P1")
    parent2 = _node(db, "P2")
    add_link(db, parent1.id, child_content_id=42)
    lnk2 = add_link(db, parent2.id, child_content_id=42)
    assert lnk2.child_content_id == 42


# ── 사이클 가드 ────────────────────────────────────────────────────────────────

def test_add_link_node_self_loop_raises(db):
    n = _node(db)
    with pytest.raises(ValueError, match="사이클"):
        add_link(db, n.id, child_node_id=n.id)


def test_add_link_node_direct_cycle_raises(db):
    a = _node(db, "A")
    b = _node(db, "B")
    add_link(db, a.id, child_node_id=b.id)
    with pytest.raises(ValueError, match="사이클"):
        add_link(db, b.id, child_node_id=a.id)


def test_add_link_node_transitive_cycle_raises(db):
    a = _node(db, "A")
    b = _node(db, "B")
    c = _node(db, "C")
    add_link(db, a.id, child_node_id=b.id)
    add_link(db, b.id, child_node_id=c.id)
    with pytest.raises(ValueError, match="사이클"):
        add_link(db, c.id, child_node_id=a.id)


# ── add_links_batch ────────────────────────────────────────────────────────────

def test_add_links_batch_multi(db):
    parent = _node(db)
    added = add_links_batch(db, parent.id, [
        {"child_content_id": 1},
        {"child_content_id": 2},
        {"child_content_id": 3},
    ])
    assert len(added) == 3


def test_add_links_batch_idempotent_skip_duplicate(db):
    parent = _node(db)
    add_link(db, parent.id, child_content_id=10)
    added = add_links_batch(db, parent.id, [
        {"child_content_id": 10},  # 중복 → 건너뜀
        {"child_content_id": 20},  # 신규
    ])
    assert len(added) == 1
    assert added[0].child_content_id == 20


# ── reorder_links ──────────────────────────────────────────────────────────────

def test_reorder_links(db):
    parent = _node(db)
    l1 = add_link(db, parent.id, child_content_id=1)
    l2 = add_link(db, parent.id, child_content_id=2)
    l3 = add_link(db, parent.id, child_content_id=3)
    reorder_links(db, parent.id, [l3.id, l1.id, l2.id])
    db.expire_all()
    orders = {lnk.id: lnk.sort_order for lnk in db.query(ProgrammingLink).filter(
        ProgrammingLink.parent_node_id == parent.id
    ).all()}
    assert orders[l3.id] == 0
    assert orders[l1.id] == 1
    assert orders[l2.id] == 2


def test_reorder_links_wrong_parent_raises(db):
    p1 = _node(db, "P1")
    p2 = _node(db, "P2")
    l1 = add_link(db, p1.id, child_content_id=1)
    l2 = add_link(db, p2.id, child_content_id=2)
    with pytest.raises(ValueError, match="속하지 않습니다"):
        reorder_links(db, p1.id, [l1.id, l2.id])


# ── move_link ──────────────────────────────────────────────────────────────────

def test_move_link(db):
    p1 = _node(db, "P1")
    p2 = _node(db, "P2")
    lnk = add_link(db, p1.id, child_content_id=99)
    moved = move_link(db, lnk.id, p2.id)
    assert moved.parent_node_id == p2.id


def test_move_link_cycle_raises(db):
    a = _node(db, "A")
    b = _node(db, "B")
    # a → b 링크
    add_link(db, a.id, child_node_id=b.id)
    # b → c 링크
    c = _node(db, "C")
    lnk_bc = add_link(db, b.id, child_node_id=c.id)
    # c → a 로 이동하면 사이클
    with pytest.raises(ValueError, match="사이클"):
        move_link(db, lnk_bc.id, c.id)


# ── update_link ────────────────────────────────────────────────────────────────

def test_update_link_fields(db):
    parent = _node(db)
    lnk = add_link(db, parent.id, child_content_id=1)
    updated = update_link(
        db, lnk.id,
        is_pinned=True,
        copy_override={"title": "특집"},
        status=LinkStatus.suggested,
    )
    assert updated.is_pinned is True
    assert updated.copy_override == {"title": "특집"}
    assert updated.status == LinkStatus.suggested


def test_update_link_disallowed_field_raises(db):
    parent = _node(db)
    lnk = add_link(db, parent.id, child_content_id=1)
    with pytest.raises(ValueError, match="not updatable"):
        update_link(db, lnk.id, child_content_id=99)


# ── remove_link ────────────────────────────────────────────────────────────────

def test_remove_link(db):
    parent = _node(db)
    lnk = add_link(db, parent.id, child_content_id=1)
    remove_link(db, lnk.id)
    assert db.query(ProgrammingLink).filter(ProgrammingLink.id == lnk.id).first() is None


def test_remove_link_not_found_raises(db):
    with pytest.raises(ValueError, match="not found"):
        remove_link(db, 9999)


# ── get_backrefs ──────────────────────────────────────────────────────────────

def test_get_backrefs_single_parent(db):
    parent = _node(db, "홈 Top")
    add_link(db, parent.id, child_content_id=7)
    refs = get_backrefs(db, child_content_id=7)
    assert len(refs) == 1
    assert isinstance(refs[0], Backref)
    assert refs[0].parent_node_id == parent.id
    assert refs[0].parent_node_name == "홈 Top"


def test_get_backrefs_multi_parent(db):
    p1 = _node(db, "P1")
    p2 = _node(db, "P2")
    add_link(db, p1.id, child_content_id=55)
    add_link(db, p2.id, child_content_id=55)
    refs = get_backrefs(db, child_content_id=55)
    assert len(refs) == 2
    parent_ids = {r.parent_node_id for r in refs}
    assert parent_ids == {p1.id, p2.id}


def test_get_backrefs_excludes_rejected_by_default(db):
    parent = _node(db)
    add_link(db, parent.id, child_content_id=1)
    add_link(db, parent.id, child_content_id=2, status=LinkStatus.rejected)
    refs = get_backrefs(db, child_content_id=2)
    assert len(refs) == 0


def test_get_backrefs_include_rejected(db):
    parent = _node(db)
    add_link(db, parent.id, child_content_id=2, status=LinkStatus.rejected)
    refs = get_backrefs(db, child_content_id=2, include_rejected=True)
    assert len(refs) == 1
    assert refs[0].status == "rejected"


def test_get_backrefs_xor_raises(db):
    with pytest.raises(ValueError, match="정확히 하나"):
        get_backrefs(db, child_content_id=1, child_node_id=2)


# ── check_window_within_node ──────────────────────────────────────────────────

def test_check_window_within_node_no_node_window(db):
    node = _node(db)
    result = check_window_within_node(
        node, date(2026, 1, 1), date(2026, 12, 31)
    )
    assert result is None


def test_check_window_within_node_within(db):
    node = _node(db)
    node.window_start = date(2026, 1, 1)
    node.window_end = date(2026, 12, 31)
    result = check_window_within_node(
        node, date(2026, 3, 1), date(2026, 6, 30)
    )
    assert result is None


def test_check_window_within_node_start_exceeds(db):
    node = _node(db)
    node.window_start = date(2026, 3, 1)
    node.window_end = date(2026, 12, 31)
    result = check_window_within_node(
        node, date(2026, 1, 1), date(2026, 6, 30)
    )
    assert result is not None
    assert "window_start" in result


def test_check_window_within_node_end_exceeds(db):
    node = _node(db)
    node.window_start = date(2026, 1, 1)
    node.window_end = date(2026, 6, 30)
    result = check_window_within_node(
        node, date(2026, 3, 1), date(2026, 12, 31)
    )
    assert result is not None
    assert "window_end" in result


# ── read-time 정합 (compute_members 회귀 가드) ─────────────────────────────────

def test_add_link_reflected_in_compute_members(db):
    parent = _node(db)
    add_link(db, parent.id, child_content_id=10, sort_order=0)
    add_link(db, parent.id, child_content_id=20, sort_order=1)
    members = compute_members(db, parent)
    assert [m.content_id for m in members] == [10, 20]


def test_remove_link_reflected_in_compute_members(db):
    parent = _node(db)
    lnk = add_link(db, parent.id, child_content_id=10)
    add_link(db, parent.id, child_content_id=20)
    remove_link(db, lnk.id)
    members = compute_members(db, parent)
    assert len(members) == 1
    assert members[0].content_id == 20
