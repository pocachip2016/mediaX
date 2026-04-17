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


# ── Staging 검토 대기풀 ────────────────────────────────────

class ExternalSourceOut(BaseModel):
    id: int
    source_type: str
    external_id: Optional[str]
    matched_at: Optional[datetime]

    model_config = {"from_attributes": True}


class StagingItem(BaseModel):
    """운영자 검토 대기풀 항목 (AI 결과 + diff + 계층 포함)"""
    content: ContentOut
    metadata: Optional[MetadataOut] = None
    diff: dict[str, Any] = Field(default_factory=dict)   # cp vs ai 필드 비교
    external_sources: list[ExternalSourceOut] = Field(default_factory=list)
    children: list["StagingItem"] = Field(default_factory=list)  # 시리즈 계층

    model_config = {"from_attributes": True}


class BulkActionRequest(BaseModel):
    """벌크 승인/반려 요청"""
    content_ids: list[int]
    reviewer: str


class PaginatedStagingItems(BaseModel):
    items: list[StagingItem]
    total: int
    page: int
    size: int


# ── 파이프라인 현황 ────────────────────────────────────────

class PipelineStatus(BaseModel):
    waiting_count: int
    processing_count: int
    staging_count: int
    review_count: int
    approved_count: int
    rejected_count: int
    failed_enrichment_count: int    # 6시간 이상 processing 상태
    avg_quality_score: float
    last_email_poll: Optional[datetime] = None
    tasks_description: str = "Celery Beat 활성"


# ── 배치 업로드 ───────────────────────────────────────────

class BatchUploadRow(BaseModel):
    """배치 업로드 파일의 단일 행"""
    title: str
    production_year: Optional[int] = None
    content_type: ContentType = ContentType.movie
    cp_name: Optional[str] = None
    episode_count: Optional[int] = None
    cp_synopsis: Optional[str] = None
    parse_status: str = "ok"   # ok | warning | error
    parse_message: Optional[str] = None


class BatchUploadPreview(BaseModel):
    """파싱 미리보기 응답"""
    job_id: int
    rows: list[BatchUploadRow]
    total_count: int
    ok_count: int
    warning_count: int
    error_count: int


class BatchJobOut(BaseModel):
    id: int
    job_name: str
    cp_name: Optional[str]
    status: str
    file_name: Optional[str]
    total_count: int
    success_count: int
    failed_count: int
    created_by: Optional[str]
    created_at: datetime
    finished_at: Optional[datetime]

    model_config = {"from_attributes": True}


StagingItem.model_rebuild()
ContentDetail.model_rebuild()


# ── 글자메타 / 이미지메타 / 영상메타 ─────────────────────────

class TextMetaOut(BaseModel):
    """글자메타 뷰 — 콘텐츠 + 텍스트 필드 + 완료 여부 + 계층 정보"""
    id: int
    title: str
    content_type: ContentType
    cp_name: Optional[str]
    production_year: Optional[int]
    season_number: Optional[int]
    episode_number: Optional[int]
    parent_id: Optional[int]
    # 텍스트 메타 필드
    synopsis: Optional[str] = None          # final_synopsis 우선, 없으면 ai_synopsis
    genre_primary: Optional[str] = None
    genre_secondary: Optional[str] = None
    mood_tags: Optional[list[str]] = None
    rating_suggestion: Optional[str] = None
    # 완료 여부
    text_meta_completed: bool = False
    # 시리즈 계층 (children: 시즌 목록, 시즌의 children: 에피소드 목록)
    episode_completed_count: int = 0        # 시리즈/시즌용: 하위 완료 수
    episode_total_count: int = 0            # 시리즈/시즌용: 하위 전체 수
    children: list["TextMetaOut"] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class TextMetaUpdate(BaseModel):
    """글자메타 수정 요청"""
    synopsis: Optional[str] = None
    genre_primary: Optional[str] = None
    genre_secondary: Optional[str] = None
    mood_tags: Optional[list[str]] = None
    rating_suggestion: Optional[str] = None
    completed: bool = False


class TextMetaBulkCompleteRequest(BaseModel):
    """글자메타 일괄 완료 처리 요청"""
    content_ids: list[int]
    # 시리즈 id 포함 시 하위 season/episode 전체 포함 처리


class ImageTypeStats(BaseModel):
    """이미지 타입별 현황"""
    poster: int = 0
    thumbnail: int = 0
    stillcut: int = 0
    banner: int = 0
    logo: int = 0
    total_contents: int = 0


class ContentImageOut(BaseModel):
    """이미지 메타 단일 항목"""
    id: int
    content_id: int
    image_type: str         # poster/thumbnail/stillcut/banner/logo
    url: str
    width: Optional[int] = None
    height: Optional[int] = None
    alt_text: Optional[str] = None
    source: Optional[str] = None

    model_config = {"from_attributes": True}


class ImageMetaOut(BaseModel):
    """이미지메타 뷰 — 콘텐츠 + 이미지 목록 + 완료 여부"""
    id: int
    title: str
    content_type: ContentType
    cp_name: Optional[str]
    production_year: Optional[int]
    images: list[ContentImageOut] = Field(default_factory=list)
    has_poster: bool = False
    has_thumbnail: bool = False
    has_stillcut: bool = False
    has_banner: bool = False
    has_logo: bool = False
    image_meta_completed: bool = False

    model_config = {"from_attributes": True}


class VideoMetaOut(BaseModel):
    """영상메타 뷰 — 콘텐츠 + 영상 기술 필드 + 완료 여부"""
    id: int
    title: str
    content_type: ContentType
    cp_name: Optional[str]
    production_year: Optional[int]
    # 영상 기술 메타
    video_resolution: Optional[str] = None
    video_format: Optional[str] = None
    codec_video: Optional[str] = None
    codec_audio: Optional[str] = None
    video_bitrate_kbps: Optional[int] = None
    video_duration_seconds: Optional[int] = None
    subtitle_languages: Optional[list[str]] = None
    drm_type: Optional[str] = None
    preview_clip_url: Optional[str] = None
    # 완료 여부
    video_meta_completed: bool = False

    model_config = {"from_attributes": True}


class VideoMetaUpdate(BaseModel):
    """영상메타 수정 요청"""
    video_resolution: Optional[str] = None
    video_format: Optional[str] = None
    codec_video: Optional[str] = None
    codec_audio: Optional[str] = None
    video_bitrate_kbps: Optional[int] = None
    video_duration_seconds: Optional[int] = None
    subtitle_languages: Optional[list[str]] = None
    drm_type: Optional[str] = None
    preview_clip_url: Optional[str] = None
    completed: bool = False


class VideoBulkCompleteRequest(BaseModel):
    content_ids: list[int]


class ImageBulkCompleteRequest(BaseModel):
    content_ids: list[int]


class ServiceReadinessStats(BaseModel):
    """서비스 준비 현황 통계"""
    total: int
    text_completed: int
    image_completed: int
    video_completed: int
    all_completed: int     # 세 가지 모두 완료 = 서비스 준비 완료
    # 비율 (소수점 1자리, 0~100)
    text_rate: float = 0.0
    image_rate: float = 0.0
    video_rate: float = 0.0
    all_rate: float = 0.0


class TextMetaSuggestion(BaseModel):
    """글자메타 AI 제안 — TMDB/KOBIS/LLM 소스"""
    source: str              # "tmdb" | "kobis" | "ai"
    synopsis: Optional[str] = None
    genre_primary: Optional[str] = None
    genre_secondary: Optional[str] = None
    mood_tags: Optional[list[str]] = None
    rating_suggestion: Optional[str] = None


class ImageSuggestion(BaseModel):
    """이미지 단건 제안"""
    source: str              # "tmdb"
    image_type: str          # poster/thumbnail/stillcut/banner/logo
    url: str
    width: Optional[int] = None
    height: Optional[int] = None


class ImageMetaSuggestions(BaseModel):
    """이미지메타 TMDB 제안 목록"""
    content_id: int
    suggestions: list[ImageSuggestion] = []


# ── TMDB 동기화 결과 ──────────────────────────────────────

class TmdbSyncedItem(BaseModel):
    content_id: int
    title: str
    original_title: Optional[str]
    content_type: str
    status: str
    production_year: Optional[int]
    cp_name: Optional[str]
    tmdb_id: str
    poster_url: Optional[str]
    match_confidence: Optional[float]
    matched_at: Optional[datetime]
    quality_score: Optional[float]


class PaginatedTmdbItems(BaseModel):
    items: list[TmdbSyncedItem]
    total: int
    page: int
    size: int


TextMetaOut.model_rebuild()
