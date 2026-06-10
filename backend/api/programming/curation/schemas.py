from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel

from .models import BannerPlanStatus, Device, SlotCode, SlotType, TimeBand


# ── HomeSlot ──────────────────────────────────────────────────────────────────

class SlotCreate(BaseModel):
    slot_code: SlotCode
    slot_type: SlotType
    device: Device = Device.all
    time_band: TimeBand = TimeBand.all
    position: int = 0
    node_set_id: Optional[int] = None


class SlotUpdate(BaseModel):
    node_set_id: Optional[int] = None
    position: Optional[int] = None
    is_active: Optional[bool] = None


class SlotOut(BaseModel):
    id: int
    slot_code: SlotCode
    slot_type: SlotType
    device: Device
    time_band: TimeBand
    position: int
    node_set_id: Optional[int] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SlotResolveOut(BaseModel):
    slots: list[SlotOut]


# ── CurationBannerPlan ────────────────────────────────────────────────────────

class BannerPlanCreate(BaseModel):
    week_start: date


class BannerPlanApprove(BaseModel):
    reviewer: str


class BannerPlanOut(BaseModel):
    id: int
    week_start: date
    status: BannerPlanStatus
    node_set_id: Optional[int] = None
    ctr_prediction: Optional[float] = None
    reviewer: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
