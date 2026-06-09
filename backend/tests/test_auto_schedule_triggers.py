"""자동편성 트리거 단위 테스트 — ADR-012 Step 5."""
from unittest.mock import MagicMock, patch, call

import pytest

from api.programming.scheduling.models import AutoStage, ProgrammingNode, ScheduleAutoPolicy


# ── auto_schedule_tick ────────────────────────────────────────────────────────

def test_tick_disabled_when_flag_off(db):
    """auto_tick_enabled=False 이면 즉시 종료, dispatch 없음."""
    from workers.tasks.scheduling_auto import auto_schedule_tick

    # policy 생성 (auto_tick_enabled=False 기본값)
    from api.programming.scheduling.auto_service import get_policy
    policy = get_policy(db)
    assert policy.auto_tick_enabled is False

    with patch("workers.tasks.scheduling_auto.SessionLocal", return_value=db), \
         patch("workers.tasks.scheduling_auto.process_schedule_bucket") as mock_dispatch:
        # SessionLocal() as db 패턴을 위해 context manager 모킹
        db_cm = MagicMock()
        db_cm.__enter__ = MagicMock(return_value=db)
        db_cm.__exit__ = MagicMock(return_value=False)
        with patch("workers.tasks.scheduling_auto.SessionLocal", return_value=db_cm):
            result = auto_schedule_tick()

    assert result.get("skipped") == "tick_disabled"
    mock_dispatch.apply_async.assert_not_called()


def test_tick_dispatches_when_enabled(db):
    """auto_tick_enabled=True + auto_enabled 노드 존재 시 dispatch 발행."""
    from workers.tasks.scheduling_auto import auto_schedule_tick
    from api.programming.scheduling.auto_service import get_policy
    from api.programming.scheduling.models import ProgrammingNodeSet

    # NodeSet + Node 생성
    ns = ProgrammingNodeSet(name="test-set")
    db.add(ns)
    db.flush()
    node = ProgrammingNode(kind="rule", name="테스트 노드", set_id=ns.id)
    node.auto_enabled = True
    node.auto_stage = None  # bucket 1
    db.add(node)
    db.flush()

    policy = get_policy(db)
    policy.auto_tick_enabled = True
    db.commit()

    db_cm = MagicMock()
    db_cm.__enter__ = MagicMock(return_value=db)
    db_cm.__exit__ = MagicMock(return_value=False)

    with patch("workers.tasks.scheduling_auto.SessionLocal", return_value=db_cm), \
         patch("workers.tasks.scheduling_auto.process_schedule_bucket") as mock_bucket:
        mock_bucket.apply_async = MagicMock()
        result = auto_schedule_tick()

    # bucket 1 에 노드 있으므로 최소 1회 dispatch
    assert "dispatched" in result
    assert mock_bucket.apply_async.called


# ── process_schedule_bucket ───────────────────────────────────────────────────

def test_process_bucket_skips_when_disabled(db):
    """tick_disabled 시 process_schedule_bucket 은 즉시 반환."""
    from workers.tasks.scheduling_auto import process_schedule_bucket
    from api.programming.scheduling.auto_service import get_policy

    policy = get_policy(db)
    assert policy.auto_tick_enabled is False

    db_cm = MagicMock()
    db_cm.__enter__ = MagicMock(return_value=db)
    db_cm.__exit__ = MagicMock(return_value=False)

    with patch("workers.tasks.scheduling_auto.SessionLocal", return_value=db_cm):
        result = process_schedule_bucket(bucket=1)

    assert result.get("skipped") == "tick_disabled"


def test_process_bucket_advances_node(db):
    """auto_tick_enabled=True 시 bucket 1 노드를 advance_one 처리."""
    from workers.tasks.scheduling_auto import process_schedule_bucket
    from api.programming.scheduling.auto_service import get_policy
    from api.programming.scheduling.models import ProgrammingNodeSet

    ns = ProgrammingNodeSet(name="trigger-test")
    db.add(ns)
    db.flush()
    node = ProgrammingNode(kind="rule", name="트리거 노드", set_id=ns.id)
    node.auto_enabled = True
    node.auto_stage = None
    db.add(node)
    db.flush()

    policy = get_policy(db)
    policy.auto_tick_enabled = True
    db.commit()

    db_cm = MagicMock()
    db_cm.__enter__ = MagicMock(return_value=db)
    db_cm.__exit__ = MagicMock(return_value=False)

    with patch("workers.tasks.scheduling_auto.SessionLocal", return_value=db_cm), \
         patch("api.programming.scheduling.auto_service._execute_stage"):
        result = process_schedule_bucket(bucket=1)

    assert result["claimed"] >= 1
    assert result["ok"] >= 1


# ── rematch_scheduling_nodes (이벤트 훅) ──────────────────────────────────────

def test_rematch_only_targets_auto_enabled_p2_p3(db):
    """rematch 는 auto_enabled=True + p2/p3 노드만 처리."""
    from workers.tasks.scheduling_auto import rematch_scheduling_nodes
    from api.programming.scheduling.auto_service import get_policy
    from api.programming.scheduling.models import ProgrammingNodeSet

    ns = ProgrammingNodeSet(name="rematch-set")
    db.add(ns)
    db.flush()

    # p2 auto_enabled 노드 (대상)
    node_p2 = ProgrammingNode(kind="rule", name="p2 노드", set_id=ns.id)
    node_p2.auto_enabled = True
    node_p2.auto_stage = AutoStage.P2_CANDIDATE
    node_p2.rule_query = {"genre": "action"}

    # p6 노드 (대상 아님)
    node_p6 = ProgrammingNode(kind="manual", name="p6 노드", set_id=ns.id)
    node_p6.auto_enabled = True
    node_p6.auto_stage = AutoStage.P6_PUBLISH

    # auto_enabled=False 노드 (대상 아님)
    node_off = ProgrammingNode(kind="rule", name="비활성 노드", set_id=ns.id)
    node_off.auto_enabled = False
    node_off.auto_stage = AutoStage.P2_CANDIDATE
    node_off.rule_query = {"genre": "drama"}

    db.add_all([node_p2, node_p6, node_off])
    db.commit()

    db_cm = MagicMock()
    db_cm.__enter__ = MagicMock(return_value=db)
    db_cm.__exit__ = MagicMock(return_value=False)

    with patch("workers.tasks.scheduling_auto.SessionLocal", return_value=db_cm), \
         patch("api.programming.scheduling.suggest_service.suggest_links", return_value=MagicMock(saved=[], skipped_count=0)) as mock_suggest:
        result = rematch_scheduling_nodes(content_id=999)

    # p2 auto_enabled 노드 1건만 처리
    assert result["matched"] == 1
