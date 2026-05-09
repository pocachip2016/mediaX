"""
Intelligence API Pydantic 스키마 — 검수 UI 전용

Dam public_api/schemas.py 와 별도 네임스페이스.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


# ── FieldGap (step4 GapReport 직렬화) ────────────────────────────────────────

class FieldGapOut(BaseModel):
    field_name: str
    reason: str
    recommended_sources: list[str]
    priority: int


class GapReportOut(BaseModel):
    content_id: int
    title: str
    content_type: str
    missing_fields: list[FieldGapOut]
    is_clean: bool
    min_priority: int


# ── FieldSuggestion ───────────────────────────────────────────────────────────

class FieldSuggestionOut(BaseModel):
    id: int
    field_name: str
    value_json: Any
    source_type: str
    confidence: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── FieldResolution ───────────────────────────────────────────────────────────

class FieldResolutionOut(BaseModel):
    id: int
    content_id: int
    field_name: str
    decision: str
    chosen_value_json: Any
    chosen_suggestion_ids: list[int] | None
    agreement_count: int
    agreeing_sources_json: list[str] | None
    applied_to_content: bool
    decided_by: str | None
    decided_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class ResolutionsByStatusOut(BaseModel):
    auto: list[FieldResolutionOut]
    pending: list[FieldResolutionOut]


class FieldResolutionDetailOut(BaseModel):
    resolution: FieldResolutionOut | None
    suggestions: list[FieldSuggestionOut]


# ── MatchEdge ─────────────────────────────────────────────────────────────────

class MatchEdgeOut(BaseModel):
    id: int
    candidate_id: int
    content_id: int
    score: float
    reasons_json: list[str]
    sub_scores_json: dict | None
    decided: bool
    decided_at: datetime | None
    decided_by: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class MatchEdgesOut(BaseModel):
    decided: list[MatchEdgeOut]
    undecided: list[MatchEdgeOut]


# ── 검수 큐 (queue/resolutions) ───────────────────────────────────────────────

class ResolutionQueueItem(BaseModel):
    content_id: int
    content_title: str
    field_name: str
    resolution: FieldResolutionOut


class ResolutionQueueOut(BaseModel):
    items: list[ResolutionQueueItem]
    total: int
    page: int
    page_size: int


# ── 쓰기 요청 스키마 (step9) ──────────────────────────────────────────────────

class PickRequest(BaseModel):
    suggestion_id: int


class MergeRequest(BaseModel):
    suggestion_ids: list[int]
    method: str = "union"   # "union" | "llm_merge"


class BulkAcceptRequest(BaseModel):
    fields: list[str]


class ActionResultOut(BaseModel):
    field_name: str
    decision: str
    applied: bool
    message: str = ""
