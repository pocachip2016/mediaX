from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class DistributionChannelOut(BaseModel):
    id: int
    content_id: int
    channel: str
    channel_type: str
    external_id: Optional[str] = None
    available_from: Optional[date] = None
    available_until: Optional[date] = None
    is_exclusive: bool
    popularity_rank: Optional[int] = None
    popularity_score: Optional[float] = None
    synced_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ServiceCategoryOut(BaseModel):
    id: int
    name: str
    category_type: str
    platform: str
    position: int
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DeviceVariantOut(BaseModel):
    id: int
    content_id: int
    device_type: str
    resolution: Optional[str] = None
    format: Optional[str] = None
    bitrate_kbps: Optional[int] = None
    drm_type: Optional[str] = None
    is_available: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SyncStatusOut(BaseModel):
    channel: str
    total_rows: int
    last_synced_at: Optional[datetime] = None
