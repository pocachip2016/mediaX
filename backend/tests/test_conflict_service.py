"""자동편성 충돌 탐지 conflict_service 단위 테스트 — ADR-012 P5/Step 8."""
from datetime import date

import pytest

from api.programming.scheduling.conflict_service import detect_conflicts
from api.programming.scheduling.models import (
    ChildType,
    LinkStatus,
    ProgrammingLink,
    ProgrammingNode,
    ProgrammingNodeSet,
)
from api.programming.metadata.models.content import Content, ContentType


@pytest.fixture
def node_set(db):
    ns = ProgrammingNodeSet(name="충돌 테스트 세트", status="draft")
    db.add(ns)
    db.flush()
    return ns


def _make_node(db, set_id, name):
    node = ProgrammingNode(set_id=set_id, kind="rule", name=name)
    db.add(node)
    db.flush()
    return node


def _make_content(db, title):
    c = Content(title=title, content_type=ContentType.movie)
    db.add(c)
    db.flush()
    return c


def _link(db, node_id, content_id, ws=None, we=None, status=LinkStatus.active):
    lnk = ProgrammingLink(
        parent_node_id=node_id,
        child_content_id=content_id,
        child_type=ChildType.content,
        window_start=ws,
        window_end=we,
        status=status,
    )
    db.add(lnk)
    db.flush()
    return lnk


# ── 충돌 없음 ──────────────────────────────────────────────────────────────────

def test_no_conflict_single_link(db, node_set):
    n1 = _make_node(db, node_set.id, "노드1")
    c = _make_content(db, "영화A")
    _link(db, n1.id, c.id, date(2026, 7, 1), date(2026, 7, 10))

    report = detect_conflicts(db, node_set.id)
    assert report["conflict_count"] == 0
    assert report["blocking_count"] == 0


def test_no_conflict_different_contents(db, node_set):
    n1 = _make_node(db, node_set.id, "노드1")
    n2 = _make_node(db, node_set.id, "노드2")
    ca = _make_content(db, "영화A")
    cb = _make_content(db, "영화B")
    _link(db, n1.id, ca.id, date(2026, 7, 1), date(2026, 7, 10))
    _link(db, n2.id, cb.id, date(2026, 7, 5), date(2026, 7, 15))

    report = detect_conflicts(db, node_set.id)
    assert report["conflict_count"] == 0


# ── 케이스 1: window 겹침 (blocking) ──────────────────────────────────────────

def test_window_overlap_conflict(db, node_set):
    """동일 content_id 가 겹치는 window 로 2개 노드에 active → window_overlap(차단)."""
    n1 = _make_node(db, node_set.id, "노드1")
    n2 = _make_node(db, node_set.id, "노드2")
    c = _make_content(db, "겹침영화")
    _link(db, n1.id, c.id, date(2026, 7, 1), date(2026, 7, 10))
    _link(db, n2.id, c.id, date(2026, 7, 5), date(2026, 7, 15))  # 7/5~7/10 겹침

    report = detect_conflicts(db, node_set.id)
    assert report["window_overlap_count"] == 1
    assert report["blocking_count"] == 1
    assert report["duplicate_content_count"] == 0
    assert report["conflicts"][0]["type"] == "window_overlap"
    assert report["conflicts"][0]["content_id"] == c.id


# ── 케이스 2: 중복 편성 dedup (non-blocking) ──────────────────────────────────

def test_duplicate_content_non_overlapping(db, node_set):
    """동일 content_id 가 겹치지 않는 window 로 2회 active → duplicate_content(권고)."""
    n1 = _make_node(db, node_set.id, "노드1")
    n2 = _make_node(db, node_set.id, "노드2")
    c = _make_content(db, "중복영화")
    _link(db, n1.id, c.id, date(2026, 7, 1), date(2026, 7, 10))
    _link(db, n2.id, c.id, date(2026, 8, 1), date(2026, 8, 10))  # 분리

    report = detect_conflicts(db, node_set.id)
    assert report["duplicate_content_count"] == 1
    assert report["window_overlap_count"] == 0
    assert report["blocking_count"] == 0  # 차단 아님
    assert report["conflicts"][0]["type"] == "duplicate_content"


# ── suggested 링크는 충돌 대상 아님 ──────────────────────────────────────────

def test_suggested_links_ignored(db, node_set):
    """active 가 아닌 suggested 링크는 충돌 검사 제외."""
    n1 = _make_node(db, node_set.id, "노드1")
    n2 = _make_node(db, node_set.id, "노드2")
    c = _make_content(db, "제안영화")
    _link(db, n1.id, c.id, date(2026, 7, 1), date(2026, 7, 10), status=LinkStatus.active)
    _link(db, n2.id, c.id, date(2026, 7, 5), date(2026, 7, 15), status=LinkStatus.suggested)

    report = detect_conflicts(db, node_set.id)
    assert report["conflict_count"] == 0  # active 1건뿐


# ── 상시 노출(window None)은 모든 window 와 겹침 ─────────────────────────────

def test_null_window_overlaps_everything(db, node_set):
    """window 없는 active 링크(상시 노출)는 동일 content 의 다른 window 와 겹침으로 판정."""
    n1 = _make_node(db, node_set.id, "노드1")
    n2 = _make_node(db, node_set.id, "노드2")
    c = _make_content(db, "상시영화")
    _link(db, n1.id, c.id, None, None)  # 상시
    _link(db, n2.id, c.id, date(2026, 7, 5), date(2026, 7, 15))

    report = detect_conflicts(db, node_set.id)
    assert report["window_overlap_count"] == 1
    assert report["blocking_count"] == 1
