from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel


class ServiceOut(BaseModel):
    id: int
    code: str
    name: str
    kind: str
    position: int
    is_active: bool

    model_config = {"from_attributes": True}


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
    headline_copy: Optional[str] = None
    sub_copy: Optional[str] = None
    theme_features: Optional[dict[str, Any]] = None
    source_mode: str = "manual"
    reference_external_id: Optional[str] = None
    is_draft: bool = False
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


class ServiceCategoryCreate(BaseModel):
    name: str
    category_type: str
    platform: str
    position: int = 0
    is_active: bool = True
    headline_copy: Optional[str] = None
    sub_copy: Optional[str] = None
    theme_features: Optional[dict[str, Any]] = None
    source_mode: str = "manual"
    reference_external_id: Optional[str] = None
    is_draft: bool = False


class ServiceCategoryUpdate(BaseModel):
    name: Optional[str] = None
    category_type: Optional[str] = None
    platform: Optional[str] = None
    position: Optional[int] = None
    is_active: Optional[bool] = None
    headline_copy: Optional[str] = None
    sub_copy: Optional[str] = None
    theme_features: Optional[dict[str, Any]] = None
    source_mode: Optional[str] = None
    reference_external_id: Optional[str] = None
    is_draft: Optional[bool] = None


class ServiceCategoryItemCreate(BaseModel):
    content_id: int
    rank: int
    score: Optional[float] = None


class ServiceCategoryItemOut(BaseModel):
    id: int
    category_id: int
    content_id: int
    content_title: Optional[str] = None
    rank: int
    score: Optional[float] = None
    added_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ServiceCategoryWithItemsOut(ServiceCategoryOut):
    items: list[ServiceCategoryItemOut] = []


class ReorderItem(BaseModel):
    id: int
    rank: int


class ReorderRequest(BaseModel):
    items: list[ReorderItem]
