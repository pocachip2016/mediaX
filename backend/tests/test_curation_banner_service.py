"""test_curation_banner_service.py — CurationBannerPlan 워크플로우 검증."""
import pytest
from datetime import date

from api.programming.curation import banner_service as svc
from api.programming.curation.models import BannerPlanStatus, SlotCode
from api.programming.scheduling.models import (
    LinkStatus, NodeKind, ProgrammingLink, ProgrammingNode, ProgrammingNodeSet,
)

WEEK = date(2026, 6, 9)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def auto_node(db):
    ns = ProgrammingNodeSet(name="배너세트", status="draft")
    db.add(ns)
    db.flush()
    node = ProgrammingNode(kind=NodeKind.rule, name="트렌드노드", auto_enabled=True, set_id=ns.id)
    db.add(node)
    db.flush()
    return node


@pytest.fixture
def auto_node_with_links(db, auto_node):
    from api.programming.metadata.models import Content
    contents = []
    for i in range(3):
        c = Content(title=f"영화{i}", content_type="movie", status="raw")
        db.add(c)
        db.flush()
        link = ProgrammingLink(
            parent_node_id=auto_node.id,
            child_type="content",
            child_content_id=c.id,
            source="ai",
            status=LinkStatus.active,
            confidence=0.8 + i * 0.05,
        )
        db.add(link)
        contents.append(c)
    db.flush()
    return auto_node


# ── create_plan ───────────────────────────────────────────────────────────────

def test_create_plan_creates_draft(db):
    plan = svc.create_plan(db, WEEK)
    db.commit()
    assert plan.status == BannerPlanStatus.draft
    assert plan.week_start == WEEK
    assert plan.node_set_id is not None


def test_create_plan_idempotent(db):
    p1 = svc.create_plan(db, WEEK)
    db.commit()
    p2 = svc.create_plan(db, WEEK)
    db.commit()
    assert p1.id == p2.id


def test_create_plan_collects_auto_nodes(db, auto_node):
    plan = svc.create_plan(db, WEEK)
    db.commit()
    node = db.query(ProgrammingNode).filter(ProgrammingNode.id == auto_node.id).first()
    assert node.set_id == plan.node_set_id


def test_create_plan_ctr_with_links(db, auto_node_with_links):
    plan = svc.create_plan(db, WEEK)
    db.commit()
    assert plan.ctr_prediction is not None
    assert 0.0 < plan.ctr_prediction < 1.0


def test_create_plan_ctr_zero_without_links(db):
    plan = svc.create_plan(db, WEEK)
    db.commit()
    assert plan.ctr_prediction == 0.0


# ── 상태 전이 ─────────────────────────────────────────────────────────────────

def test_submit_plan(db):
    plan = svc.create_plan(db, WEEK)
    db.commit()
    plan = svc.submit_plan(db, plan.id)
    db.commit()
    assert plan.status == BannerPlanStatus.review


def test_submit_idempotent(db):
    plan = svc.create_plan(db, WEEK)
    db.commit()
    svc.submit_plan(db, plan.id)
    plan2 = svc.submit_plan(db, plan.id)
    assert plan2.status == BannerPlanStatus.review


def test_approve_plan(db):
    plan = svc.create_plan(db, WEEK)
    db.commit()
    svc.submit_plan(db, plan.id)
    plan = svc.approve_plan(db, plan.id, reviewer="홍길동")
    db.commit()
    assert plan.status == BannerPlanStatus.approved
    assert plan.reviewer == "홍길동"
    assert plan.reviewed_at is not None


def test_approve_idempotent(db):
    plan = svc.create_plan(db, WEEK)
    db.commit()
    svc.submit_plan(db, plan.id)
    svc.approve_plan(db, plan.id, reviewer="홍길동")
    plan2 = svc.approve_plan(db, plan.id, reviewer="김철수")
    assert plan2.reviewer == "홍길동"  # 첫 승인자 유지


def test_publish_plan(db):
    plan = svc.create_plan(db, WEEK)
    db.commit()
    svc.submit_plan(db, plan.id)
    svc.approve_plan(db, plan.id, reviewer="홍길동")
    plan = svc.publish_plan(db, plan.id)
    db.commit()
    assert plan.status == BannerPlanStatus.published
    assert plan.published_at is not None


def test_publish_binds_slot_a(db):
    plan = svc.create_plan(db, WEEK)
    db.commit()
    svc.submit_plan(db, plan.id)
    svc.approve_plan(db, plan.id, reviewer="운영자")
    svc.publish_plan(db, plan.id)
    db.commit()

    from api.programming.curation.models import HomeSlot
    slot = db.query(HomeSlot).filter(HomeSlot.slot_code == SlotCode.A).first()
    assert slot is not None
    assert slot.node_set_id == plan.node_set_id


def test_publish_requires_approved_state(db):
    plan = svc.create_plan(db, WEEK)
    db.commit()
    with pytest.raises(ValueError, match="approved"):
        svc.publish_plan(db, plan.id)


def test_publish_idempotent(db):
    plan = svc.create_plan(db, WEEK)
    db.commit()
    svc.submit_plan(db, plan.id)
    svc.approve_plan(db, plan.id, reviewer="운영자")
    svc.publish_plan(db, plan.id)
    plan2 = svc.publish_plan(db, plan.id)
    assert plan2.status == BannerPlanStatus.published


def test_get_plan_not_found(db):
    assert svc.get_plan(db, 99999) is None
