from datetime import date, timedelta

from sqlalchemy.orm import Session

from api.programming.catalog.models import HoldbackPolicy, HoldbackSchedule, Pricing, Quality, PurchaseType
from api.programming.catalog.pricing_service import set_price


def upsert_policy(
    db: Session,
    cp_name: str,
    window_no: int,
    name: str,
    offset_days_start: int,
    offset_days_end: int | None,
    price_rule: str,
    is_active: bool = True,
) -> HoldbackPolicy:
    """CP별 홀드백 윈도우 정책 upsert (cp_name + window_no 기준)."""
    policy = db.query(HoldbackPolicy).filter(
        HoldbackPolicy.cp_name == cp_name,
        HoldbackPolicy.window_no == window_no,
    ).first()
    if policy is None:
        policy = HoldbackPolicy(
            cp_name=cp_name,
            window_no=window_no,
            name=name,
            offset_days_start=offset_days_start,
            offset_days_end=offset_days_end,
            price_rule=price_rule,
            is_active=is_active,
        )
        db.add(policy)
    else:
        policy.name = name
        policy.offset_days_start = offset_days_start
        policy.offset_days_end = offset_days_end
        policy.price_rule = price_rule
        policy.is_active = is_active
    db.flush()
    return policy


def list_policies(db: Session, cp_name: str | None = None) -> list[HoldbackPolicy]:
    q = db.query(HoldbackPolicy)
    if cp_name is not None:
        q = q.filter(HoldbackPolicy.cp_name == cp_name)
    return q.order_by(HoldbackPolicy.cp_name, HoldbackPolicy.window_no).all()


def delete_policy(db: Session, policy_id: int) -> None:
    policy = db.query(HoldbackPolicy).filter(HoldbackPolicy.id == policy_id).first()
    if policy is None:
        raise ValueError(f"holdback_policy not found: id={policy_id}")
    db.delete(policy)
    db.flush()


def apply_policy_to_content(
    db: Session,
    content_id: int,
    base_date: date,
) -> list[HoldbackSchedule]:
    """콘텐츠 CP의 활성 정책으로 HoldbackSchedule 생성 (content_id+window_no upsert, 멱등)."""
    from api.programming.metadata.models import Content
    content = db.query(Content).filter(Content.id == content_id).first()
    if content is None:
        raise ValueError(f"content not found: id={content_id}")
    cp_name = content.cp_name or ""

    policies = db.query(HoldbackPolicy).filter(
        HoldbackPolicy.cp_name == cp_name,
        HoldbackPolicy.is_active.is_(True),
    ).order_by(HoldbackPolicy.window_no).all()

    results: list[HoldbackSchedule] = []
    for policy in policies:
        start = base_date + timedelta(days=policy.offset_days_start)
        end = (
            base_date + timedelta(days=policy.offset_days_end)
            if policy.offset_days_end is not None
            else None
        )
        schedule = db.query(HoldbackSchedule).filter(
            HoldbackSchedule.content_id == content_id,
            HoldbackSchedule.window_no == policy.window_no,
        ).first()
        if schedule is None:
            schedule = HoldbackSchedule(
                content_id=content_id,
                window_no=policy.window_no,
                start_date=start,
                end_date=end,
                source_policy_id=policy.id,
                status="scheduled",
            )
            db.add(schedule)
        else:
            schedule.start_date = start
            schedule.end_date = end
            schedule.source_policy_id = policy.id
            schedule.status = "scheduled"
        db.flush()
        results.append(schedule)
    return results


def list_schedules(db: Session, content_id: int) -> list[HoldbackSchedule]:
    return (
        db.query(HoldbackSchedule)
        .filter(HoldbackSchedule.content_id == content_id)
        .order_by(HoldbackSchedule.window_no)
        .all()
    )


def calendar(
    db: Session,
    start_date: date,
    end_date: date,
) -> list[HoldbackSchedule]:
    """날짜 범위와 겹치는 스케줄 반환."""
    return (
        db.query(HoldbackSchedule)
        .filter(
            HoldbackSchedule.start_date <= end_date,
            (HoldbackSchedule.end_date >= start_date) | (HoldbackSchedule.end_date.is_(None)),
        )
        .order_by(HoldbackSchedule.start_date, HoldbackSchedule.content_id)
        .all()
    )


def activate_window(
    db: Session,
    content_id: int,
    window_no: int,
    quality: Quality | str | None = None,
    purchase_type: PurchaseType | str | None = None,
    price: int | None = None,
    changed_by: str | None = None,
) -> HoldbackSchedule:
    """윈도우 활성 전환. price/quality/purchase_type 제공 시 Pricing에도 반영."""
    schedule = db.query(HoldbackSchedule).filter(
        HoldbackSchedule.content_id == content_id,
        HoldbackSchedule.window_no == window_no,
    ).first()
    if schedule is None:
        raise ValueError(
            f"holdback_schedule not found: content_id={content_id} window_no={window_no}"
        )
    schedule.status = "active"

    if price is not None and quality is not None and purchase_type is not None:
        pricing_row = set_price(
            db,
            content_id=content_id,
            quality=quality,
            purchase_type=purchase_type,
            price=price,
            changed_by=changed_by,
            reason=f"홀드백 윈도우 {window_no} 활성화",
        )
        schedule.price_id = pricing_row.id

    db.flush()
    return schedule
