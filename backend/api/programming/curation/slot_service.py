"""홈 슬롯 CRUD + resolve(device, time_band) — ADR-013."""
from sqlalchemy.orm import Session

from .models import Device, HomeSlot, SlotCode, SlotType, TimeBand


# ── CRUD ───────────────────────────────────────────────────────────────────────

def create_slot(
    db: Session,
    slot_code: SlotCode,
    slot_type: SlotType,
    device: Device = Device.all,
    time_band: TimeBand = TimeBand.all,
    position: int = 0,
    node_set_id: int | None = None,
) -> HomeSlot:
    slot = HomeSlot(
        slot_code=slot_code,
        slot_type=slot_type,
        device=device,
        time_band=time_band,
        position=position,
        node_set_id=node_set_id,
    )
    db.add(slot)
    db.flush()
    return slot


def get_slot(db: Session, slot_id: int) -> HomeSlot | None:
    return db.query(HomeSlot).filter(HomeSlot.id == slot_id).first()


def list_slots(db: Session, active_only: bool = True) -> list[HomeSlot]:
    q = db.query(HomeSlot)
    if active_only:
        q = q.filter(HomeSlot.is_active == True)  # noqa: E712
    return q.order_by(HomeSlot.slot_code, HomeSlot.position).all()


def update_slot(
    db: Session,
    slot_id: int,
    *,
    node_set_id: int | None = ...,  # type: ignore[assignment]
    position: int | None = None,
    is_active: bool | None = None,
) -> HomeSlot:
    slot = db.query(HomeSlot).filter(HomeSlot.id == slot_id).first()
    if slot is None:
        raise ValueError(f"slot {slot_id} not found")
    if node_set_id is not ...:  # type: ignore[comparison-overlap]
        slot.node_set_id = node_set_id
    if position is not None:
        slot.position = position
    if is_active is not None:
        slot.is_active = is_active
    db.flush()
    return slot


def bind_node_set(db: Session, slot_id: int, node_set_id: int | None) -> HomeSlot:
    return update_slot(db, slot_id, node_set_id=node_set_id)


def delete_slot(db: Session, slot_id: int) -> None:
    slot = db.query(HomeSlot).filter(HomeSlot.id == slot_id).first()
    if slot is None:
        raise ValueError(f"slot {slot_id} not found")
    db.delete(slot)
    db.flush()


# ── Resolve ────────────────────────────────────────────────────────────────────

def resolve_slots(db: Session, device: Device, time_band: TimeBand) -> list[HomeSlot]:
    """홈 화면 조립: 요청 device/time_band 에 맞는 슬롯 목록 반환.

    우선순위: 구체값(tv/evening) > all.
    동일 slot_code 에 구체값과 all 이 공존하면 구체값 채택.
    """
    candidates = (
        db.query(HomeSlot)
        .filter(
            HomeSlot.is_active == True,  # noqa: E712
            HomeSlot.device.in_([device, Device.all]),
            HomeSlot.time_band.in_([time_band, TimeBand.all]),
        )
        .order_by(HomeSlot.slot_code, HomeSlot.position)
        .all()
    )

    # slot_code 별로 구체값 우선 선택
    best: dict[SlotCode, list[HomeSlot]] = {}
    for slot in candidates:
        code = slot.slot_code
        existing = best.get(code, [])
        if not existing:
            best[code] = [slot]
            continue
        existing_is_generic = (
            existing[0].device == Device.all and existing[0].time_band == TimeBand.all
        )
        incoming_is_specific = (
            slot.device != Device.all or slot.time_band != TimeBand.all
        )
        if existing_is_generic and incoming_is_specific:
            best[code] = [slot]
        elif not existing_is_generic and not incoming_is_specific:
            existing.append(slot)
        elif not incoming_is_specific:
            existing.append(slot)

    result = []
    for code in SlotCode:
        result.extend(best.get(code, []))
    return result
