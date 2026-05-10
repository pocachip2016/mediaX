"""SEED 검수 UI 용 Pydantic 스키마."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SeedListItem(BaseModel):
    id: int
    source_type: str
    external_id: str
    title: str
    original_title: str | None
    content_type: str | None
    production_year: int | None
    poster_url: str | None
    status: str
    locked_by: str | None
    discovered_at: datetime | None

    model_config = {"from_attributes": True}


class SeedListResponse(BaseModel):
    items: list[SeedListItem]
    total: int
    page: int
    page_size: int


class SeedDetail(BaseModel):
    id: int
    source_type: str
    external_id: str
    title: str
    original_title: str | None
    content_type: str | None
    production_year: int | None
    poster_url: str | None
    synopsis: str | None
    status: str
    locked_by: str | None
    locked_at: datetime | None
    alt_external_ids: dict | None
    promoted_to_content_id: int | None
    raw_payload: dict | None
    discovered_at: datetime | None

    model_config = {"from_attributes": True}


class SeedAcceptRequest(BaseModel):
    actor: str
    override_dup: bool = False


class SeedRejectRequest(BaseModel):
    actor: str
    reason: str


class SeedEditRequest(BaseModel):
    actor: str
    title: str | None = None
    production_year: int | None = None
    synopsis: str | None = None
    poster_url: str | None = None


class SeedBulkPromoteRequest(BaseModel):
    seed_ids: list[int] = Field(..., max_length=50)
    actor: str
    override_dup: bool = False


class SeedBulkPromoteResult(BaseModel):
    seed_id: int
    success: bool
    content_id: int | None = None
    error: str | None = None


class SeedStatsOut(BaseModel):
    by_status: dict[str, int]
    by_source: dict[str, int]
    recent_7days: list[dict[str, Any]]


class SeedActionOut(BaseModel):
    seed_id: int
    action: str
    success: bool
    message: str = ""
