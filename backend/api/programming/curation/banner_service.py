"""배너 주간 편성안 워크플로우 서비스 — ADR-013-02."""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from api.programming.scheduling.models import (
    LinkStatus,
    ProgrammingLink,
    ProgrammingNode,
    ProgrammingNodeSet,
)
from api.programming.scheduling.node_service import publish_node_set

from .models import BannerPlanStatus, CurationBannerPlan, Device, SlotCode, SlotType
from .slot_service import create_slot, list_slots, bind_node_set


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── CTR 예측 스텁 ──────────────────────────────────────────────────────────────

def predict_ctr(db: Session, node_set_id: int) -> float:
    """배너 편성안 CTR 예측. MVP: active 링크 평균 confidence × 0.8 휴리스틱.
    Phase 2: 학습 모델 교체 (curation_performance 실측 학습)."""
    links = (
        db.query(ProgrammingLink)
        .join(ProgrammingNode, ProgrammingLink.parent_node_id == ProgrammingNode.id)
        .filter(
            ProgrammingNode.set_id == node_set_id,
            ProgrammingLink.status == LinkStatus.active,
            ProgrammingLink.confidence.isnot(None),
        )
        .all()
    )
    if not links:
        return 0.0
    avg_conf = sum(lk.confidence for lk in links) / len(links)
    return round(avg_conf * 0.8, 4)


# ── Plan 생성 ─────────────────────────────────────────────────────────────────

def create_plan(db: Session, week_start: date) -> CurationBannerPlan:
    """배너용 auto_enabled 노드 수집 → NodeSet 생성 → CTR 예측 → draft 편성안 반환."""
    # 동일 week_start 중복 방지 (멱등)
    existing = (
        db.query(CurationBannerPlan)
        .filter(CurationBannerPlan.week_start == week_start)
        .first()
    )
    if existing:
        return existing

    # auto_enabled 노드 묶는 새 NodeSet 생성
    label = f"배너편성안-{week_start.isoformat()}"
    node_set = ProgrammingNodeSet(name=label, status="draft")
    db.add(node_set)
    db.flush()

    # auto_enabled 노드를 세트에 편입 (set_id 바인딩)
    auto_nodes = (
        db.query(ProgrammingNode)
        .filter(ProgrammingNode.auto_enabled == True)  # noqa: E712
        .all()
    )
    for node in auto_nodes:
        node.set_id = node_set.id
    db.flush()

    ctr = predict_ctr(db, node_set.id)

    plan = CurationBannerPlan(
        week_start=week_start,
        status=BannerPlanStatus.draft,
        node_set_id=node_set.id,
        ctr_prediction=ctr,
    )
    db.add(plan)
    db.flush()
    return plan


# ── 상태 전이 (멱등) ──────────────────────────────────────────────────────────

def get_plan(db: Session, plan_id: int) -> CurationBannerPlan | None:
    return db.query(CurationBannerPlan).filter(CurationBannerPlan.id == plan_id).first()


def submit_plan(db: Session, plan_id: int) -> CurationBannerPlan:
    """draft → review (멱등: 이미 review 이상이면 현 상태 그대로 반환)."""
    plan = _get_or_raise(db, plan_id)
    if plan.status == BannerPlanStatus.draft:
        plan.status = BannerPlanStatus.review
        db.flush()
    return plan


def approve_plan(db: Session, plan_id: int, reviewer: str) -> CurationBannerPlan:
    """review → approved (멱등)."""
    plan = _get_or_raise(db, plan_id)
    if plan.status == BannerPlanStatus.review:
        plan.status = BannerPlanStatus.approved
        plan.reviewer = reviewer
        plan.reviewed_at = _utcnow()
        db.flush()
    return plan


def publish_plan(db: Session, plan_id: int) -> CurationBannerPlan:
    """approved → published.

    1. node_set 을 published 상태로 전환.
    2. plan.published_at 기록.
    3. 홈 슬롯 A 에 node_set 바인딩 (없으면 신규 생성).
    """
    plan = _get_or_raise(db, plan_id)
    if plan.status == BannerPlanStatus.published:
        return plan
    if plan.status != BannerPlanStatus.approved:
        raise ValueError(f"plan {plan_id} must be approved before publishing (current: {plan.status})")

    if plan.node_set_id:
        publish_node_set(db, plan.node_set_id)

    plan.status = BannerPlanStatus.published
    plan.published_at = _utcnow()
    db.flush()

    # 슬롯 A 바인딩
    if plan.node_set_id:
        _bind_banner_slot(db, plan.node_set_id)

    return plan


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _get_or_raise(db: Session, plan_id: int) -> CurationBannerPlan:
    plan = db.query(CurationBannerPlan).filter(CurationBannerPlan.id == plan_id).first()
    if plan is None:
        raise ValueError(f"banner plan {plan_id} not found")
    return plan


def _bind_banner_slot(db: Session, node_set_id: int) -> None:
    """슬롯 A(banner)에 node_set 바인딩. 슬롯이 없으면 신규 생성."""
    slots = [s for s in list_slots(db) if s.slot_code == SlotCode.A and s.slot_type == SlotType.banner]
    if slots:
        bind_node_set(db, slots[0].id, node_set_id)
    else:
        create_slot(db, SlotCode.A, SlotType.banner, Device.all, node_set_id=node_set_id)
