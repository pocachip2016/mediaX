"""자동편성 파이프라인 auto_service 단위 테스트 — ADR-012."""

from unittest.mock import MagicMock, patch

import pytest

from api.programming.scheduling.auto_service import (
    AdvanceResult,
    RunResult,
    _release_claim,
    advance_one,
    claim_bucket,
    get_policy,
    node_bucket,
    recompute_schedule_score,
    run_to_stable,
)
from api.programming.scheduling.models import (
    AutoStage,
    LinkSource,
    LinkStatus,
    ChildType,
    ProgrammingLink,
    ProgrammingNode,
    ProgrammingNodeSet,
    ScheduleAutoPolicy,
)


# ── 픽스처 ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def node_set(db):
    ns = ProgrammingNodeSet(name="테스트 편성안", description="", status="draft")
    db.add(ns)
    db.flush()
    return ns


@pytest.fixture
def auto_node(db, node_set):
    node = ProgrammingNode(
        set_id=node_set.id,
        kind="rule",
        name="자동 테스트 노드",
        slug="auto-test-node",
        auto_enabled=True,
    )
    db.add(node)
    db.flush()
    return node


@pytest.fixture
def policy(db):
    p = ScheduleAutoPolicy(
        id=1,
        confidence_threshold=0.5,
        auto_tick_enabled=False,
        batch_size=20,
        visibility_timeout=300,
    )
    db.add(p)
    db.flush()
    return p


# ── 기본 / 정책 ────────────────────────────────────────────────────────────────

def test_get_policy_creates_if_missing(db):
    p = get_policy(db)
    assert p.id == 1
    assert p.confidence_threshold == 0.5

def test_node_bucket_none_stage(auto_node):
    assert node_bucket(auto_node) == 1  # None → bucket 1

def test_node_bucket_p3(auto_node):
    auto_node.auto_stage = AutoStage.P3_MATCH
    assert node_bucket(auto_node) == 2


# ── claim_bucket ──────────────────────────────────────────────────────────────

def test_claim_bucket_returns_auto_enabled_only(db, node_set, policy):
    n_on  = ProgrammingNode(set_id=node_set.id, kind="rule", name="on",  slug="on",  auto_enabled=True)
    n_off = ProgrammingNode(set_id=node_set.id, kind="rule", name="off", slug="off", auto_enabled=False)
    db.add_all([n_on, n_off])
    db.flush()

    claimed = claim_bucket(db, 1, batch_size=10, visibility_timeout=300)
    ids = {n.id for n in claimed}
    assert n_on.id in ids
    assert n_off.id not in ids

def test_claim_bucket_excludes_held(db, node_set, policy):
    n = ProgrammingNode(set_id=node_set.id, kind="rule", name="held", slug="held",
                        auto_enabled=True, auto_hold=True)
    db.add(n)
    db.flush()

    claimed = claim_bucket(db, 1, batch_size=10, visibility_timeout=300)
    assert n.id not in {c.id for c in claimed}


# ── advance_one ───────────────────────────────────────────────────────────────

def test_advance_one_not_found(db):
    result = advance_one(db, 99999, actor="test")
    assert result["result"] == "not_found"

def test_advance_one_hold_blocks_auto(db, auto_node, policy):
    auto_node.auto_hold = True
    db.flush()
    result = advance_one(db, auto_node.id, actor="auto")
    assert result["result"] == "hold"

def test_advance_one_hold_cleared_by_user(db, auto_node, policy):
    """운영자(actor=user)는 hold를 해제하고 진행할 수 있어야 함."""
    auto_node.auto_hold = True
    db.flush()
    with patch("api.programming.scheduling.auto_service._execute_stage"):
        result = advance_one(db, auto_node.id, actor="user")
    assert result["result"] == "ok"
    assert auto_node.auto_hold is False

def test_advance_one_p1_to_p2(db, auto_node, policy):
    """P1_DEFINE(bucket1)에서 advance → P2_CANDIDATE."""
    auto_node.auto_stage = AutoStage.P1_DEFINE
    db.flush()
    with patch("api.programming.scheduling.auto_service._execute_stage"):
        result = advance_one(db, auto_node.id, actor="test")
    assert result["result"] == "ok"
    assert auto_node.auto_stage == AutoStage.P2_CANDIDATE

def test_advance_one_terminal(db, auto_node, policy):
    """P6_PUBLISH(bucket5=terminal)에서 advance → terminal."""
    auto_node.auto_stage = AutoStage.P6_PUBLISH
    db.flush()
    result = advance_one(db, auto_node.id, actor="test")
    assert result["result"] == "terminal"


# ── P4 threshold 자동확정 / 잔류 ──────────────────────────────────────────────

def test_p4_autoconfirm_confirms_above_threshold(db, auto_node, policy, node_set):
    """confidence ≥ threshold suggested 링크는 active 로 전환돼야 한다."""
    from api.programming.scheduling.auto_service import _exec_p4_autoconfirm

    # content mock
    from api.programming.metadata.models import Content, ContentType
    c = Content(title="테스트", content_type=ContentType.movie)
    db.add(c)
    db.flush()

    lnk = ProgrammingLink(
        parent_node_id=auto_node.id,
        child_content_id=c.id,
        child_type=ChildType.content,
        source=LinkSource.ai,
        confidence=0.8,  # ≥ 0.5 threshold
        status=LinkStatus.suggested,
    )
    db.add(lnk)
    db.flush()

    _exec_p4_autoconfirm(db, auto_node, actor="test")
    db.refresh(lnk)
    assert lnk.status == LinkStatus.active
    assert auto_node.auto_skipped_at is None  # 잔류 없음


def test_p4_autoconfirm_marks_skipped_for_residual(db, auto_node, policy):
    """confidence < threshold 링크가 있으면 auto_skipped_at 마킹되고 advance에서 'skipped' 반환."""
    from api.programming.scheduling.auto_service import _exec_p4_autoconfirm
    from api.programming.metadata.models import Content, ContentType

    c = Content(title="저신뢰", content_type=ContentType.movie)
    db.add(c)
    db.flush()

    lnk = ProgrammingLink(
        parent_node_id=auto_node.id,
        child_content_id=c.id,
        child_type=ChildType.content,
        source=LinkSource.ai,
        confidence=0.2,  # < 0.5 threshold
        status=LinkStatus.suggested,
    )
    db.add(lnk)
    db.flush()

    _exec_p4_autoconfirm(db, auto_node, actor="test")
    assert auto_node.auto_skipped_at is not None
    assert lnk.status == LinkStatus.suggested  # 미확정 유지


# ── run_to_stable ─────────────────────────────────────────────────────────────

def test_run_to_stable_advances_until_terminal(db, auto_node, policy):
    """run_to_stable은 terminal에 도달할 때까지 반복 advance해야 한다."""
    # _execute_stage를 mock해 side-effect 없이 단계 전이만 테스트
    with patch("api.programming.scheduling.auto_service._execute_stage"):
        result = run_to_stable(db, auto_node.id, actor="test")
    # P1→P2→P4→P5→P6→terminal = 최대 5 advance
    assert result["stages_advanced"] >= 1
    assert result["final_result"] in ("terminal", "skipped", "hold")


# ── recompute_schedule_score ──────────────────────────────────────────────────

def test_schedule_score_empty_node(db, auto_node):
    score = recompute_schedule_score(db, auto_node)
    assert score == 0.0

def test_schedule_score_with_rule_and_window(db, auto_node):
    from datetime import date
    auto_node.rule_query = {"genre": "ACT"}
    auto_node.window_start = date(2026, 7, 1)
    auto_node.window_end   = date(2026, 7, 31)
    db.flush()
    score = recompute_schedule_score(db, auto_node)
    assert score == 50.0  # rule_query 30 + window 20

def test_schedule_score_with_active_links(db, auto_node, node_set):
    from api.programming.metadata.models import Content, ContentType
    from datetime import date

    auto_node.headline_copy = "여름 특집"
    auto_node.window_start  = date(2026, 7, 1)
    auto_node.window_end    = date(2026, 7, 31)
    db.flush()

    # active 링크 5개
    for i in range(5):
        c = Content(title=f"영화{i}", content_type=ContentType.movie)
        db.add(c)
        db.flush()
        lnk = ProgrammingLink(
            parent_node_id=auto_node.id,
            child_content_id=c.id,
            child_type=ChildType.content,
            source=LinkSource.manual,
            status=LinkStatus.active,
        )
        db.add(lnk)
    db.flush()

    score = recompute_schedule_score(db, auto_node)
    assert score == 70.0  # headline 30 + window 20 + 5links 20
