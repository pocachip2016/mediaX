from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from shared.database import get_db
from . import slot_service, banner_service
from .models import Device, HomeSlot, TimeBand
from .schemas import (
    BannerPlanApprove,
    BannerPlanCreate,
    BannerPlanOut,
    SlotCreate,
    SlotOut,
    SlotResolveOut,
    SlotUpdate,
)

router = APIRouter()


# ── 홈 슬롯 ───────────────────────────────────────────────────────────────────

@router.get("/slots", response_model=list[SlotOut])
def list_slots(active_only: bool = Query(True), db: Session = Depends(get_db)):
    return slot_service.list_slots(db, active_only=active_only)


@router.post("/slots", response_model=SlotOut, status_code=201)
def create_slot(data: SlotCreate, db: Session = Depends(get_db)):
    slot = slot_service.create_slot(
        db,
        slot_code=data.slot_code,
        slot_type=data.slot_type,
        device=data.device,
        time_band=data.time_band,
        position=data.position,
        node_set_id=data.node_set_id,
    )
    db.commit()
    db.refresh(slot)
    return slot


@router.get("/slots/resolve", response_model=SlotResolveOut)
def resolve_slots(
    device: Device = Query(Device.all),
    time_band: TimeBand = Query(TimeBand.all),
    db: Session = Depends(get_db),
):
    slots = slot_service.resolve_slots(db, device=device, time_band=time_band)
    return {"slots": slots}


@router.get("/slots/{slot_id}", response_model=SlotOut)
def get_slot(slot_id: int, db: Session = Depends(get_db)):
    slot = slot_service.get_slot(db, slot_id)
    if slot is None:
        raise HTTPException(status_code=404, detail=f"slot {slot_id} not found")
    return slot


@router.patch("/slots/{slot_id}", response_model=SlotOut)
def update_slot(slot_id: int, data: SlotUpdate, db: Session = Depends(get_db)):
    try:
        slot = slot_service.get_slot(db, slot_id)
        if slot is None:
            raise HTTPException(status_code=404, detail=f"slot {slot_id} not found")
        if data.node_set_id is not None:
            slot.node_set_id = data.node_set_id
        if data.position is not None:
            slot.position = data.position
        if data.is_active is not None:
            slot.is_active = data.is_active
        db.commit()
        db.refresh(slot)
        return slot
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/slots/{slot_id}", status_code=204)
def delete_slot(slot_id: int, db: Session = Depends(get_db)):
    try:
        slot_service.delete_slot(db, slot_id)
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── 배너 편성안 ───────────────────────────────────────────────────────────────

@router.get("/banner/plans", response_model=list[BannerPlanOut])
def list_banner_plans(db: Session = Depends(get_db)):
    from .models import CurationBannerPlan
    return db.query(CurationBannerPlan).order_by(CurationBannerPlan.week_start.desc()).all()


@router.post("/banner/plans", response_model=BannerPlanOut, status_code=201)
def create_banner_plan(data: BannerPlanCreate, db: Session = Depends(get_db)):
    plan = banner_service.create_plan(db, week_start=data.week_start)
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/banner/plans/{plan_id}", response_model=BannerPlanOut)
def get_banner_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = banner_service.get_plan(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"banner plan {plan_id} not found")
    return plan


@router.post("/banner/plans/{plan_id}/submit", response_model=BannerPlanOut)
def submit_banner_plan(plan_id: int, db: Session = Depends(get_db)):
    try:
        plan = banner_service.submit_plan(db, plan_id)
        db.commit()
        db.refresh(plan)
        return plan
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/banner/plans/{plan_id}/approve", response_model=BannerPlanOut)
def approve_banner_plan(plan_id: int, data: BannerPlanApprove, db: Session = Depends(get_db)):
    try:
        plan = banner_service.approve_plan(db, plan_id, reviewer=data.reviewer)
        db.commit()
        db.refresh(plan)
        return plan
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/banner/plans/{plan_id}/publish", response_model=BannerPlanOut)
def publish_banner_plan(plan_id: int, db: Session = Depends(get_db)):
    try:
        plan = banner_service.publish_plan(db, plan_id)
        db.commit()
        db.refresh(plan)
        return plan
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
