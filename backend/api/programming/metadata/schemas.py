"""
1.1 메타데이터 — Pydantic 요청/응답 스키마
"""

from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

from api.programming.metadata.models import ContentType, ContentStatus, MetaSource


# ── Content ──────────────────────────────────────────────

class ContentCreate(BaseModel):
    title: str
    content_type: ContentType = ContentType.movie
    cp_name: Optional[str] = None
    production_year: Optional[int] = None
    runtime_minutes: Optional[int] = None
    country: Optional[str] = None
    parent_id: Optional[int] = None
    season_number: Optional[int] = None
    episode_number: Optional[int] = None


class ContentOut(BaseModel):
    id: int
    title: str
    original_title: Optional[str]
    content_type: ContentType
    status: ContentStatus
    cp_name: Optional[str]
    production_year: Optional[int]
    runtime_minutes: Optional[int]
    created_at: datetime
    quality_score: Optional[float] = None

    model_config = {"from_attributes": True}


class ContentDetail(ContentOut):
    metadata_record: Optional[MetadataOut] = None


# ── Metadata ──────────────────────────────────────────────

class MetadataOut(BaseModel):
    id: int
    content_id: int
    cp_synopsis: Optional[str]
    cp_genre: Optional[str]
    cp_tags: Optional[list[str]]
    ai_synopsis: Optional[str]
    ai_genre_primary: Optional[str]
    ai_genre_secondary: Optional[str]
    ai_mood_tags: Optional[list[str]]
    ai_rating_suggestion: Optional[str]
    final_synopsis: Optional[str]
    final_genre: Optional[str]
    final_tags: Optional[list[str]]
    quality_score: float
    score_breakdown: Optional[dict[str, Any]]
    ai_processed_at: Optional[datetime]
    reviewed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class MetadataReviewAction(BaseModel):
    """검수 큐 — 담당자 액션"""
    action: str = Field(..., pattern="^(approve|reject|modify)$")
    reviewer: str
    final_synopsis: Optional[str] = None
    final_genre: Optional[str] = None
    final_tags: Optional[list[str]] = None
    reject_reason: Optional[str] = None


# ── AI 처리 요청/응답 ──────────────────────────────────────

class AIGenerateRequest(BaseModel):
    """실시간 메타 생성 요청 (화면 3)"""
    title: str
    production_year: Optional[int] = None
    cp_name: Optional[str] = None
    cp_synopsis: Optional[str] = None


class AIGenerateResponse(BaseModel):
    synopsis: str
    genre_primary: str
    genre_secondary: Optional[str]
    mood_tags: list[str]
    rating_suggestion: str
    quality_score: float
    kobis_match: Optional[dict[str, Any]] = None
    tmdb_match: Optional[dict[str, Any]] = None


# ── Dashboard 통계 ─────────────────────────────────────────

class DashboardStats(BaseModel):
    total_today: int
    auto_registered: int
    review_pending: int
    rejected: int
    avg_quality_score: float
    score_distribution: dict[str, int]   # {"90+": n, "70-89": n, "~70": n}
    cp_stats: list[dict[str, Any]]


# ── CP 이메일 ──────────────────────────────────────────────

class CpEmailLogOut(BaseModel):
    id: int
    subject: Optional[str]
    sender: Optional[str]
    cp_name: Optional[str]
    received_at: Optional[datetime]
    extracted_titles: Optional[list[str]]
    extracted_year: Optional[int]
    extraction_confidence: Optional[float]
    processed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Pagination ─────────────────────────────────────────────

class PaginatedContents(BaseModel):
    items: list[ContentOut]
    total: int
    page: int
    size: int


ContentDetail.model_rebuild()
