"""ADR-006 timeline v2 스키마 — 9-stage pipeline 응답."""

from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel


class StageSourceOut(BaseModel):
    """파이프라인 stage별 source(provider) 처리 결과."""
    source: str        # "tmdb" | "kobis" | "dam" | "email_poll" | "brave" | "serpapi" | "gemini" | "ollama" | "user" | "system"
    result: str        # "ok" | "hit" | "miss" | "error" | "skipped"
    latency_ms: Optional[int] = None
    detail: Optional[dict] = None


class StageOut(BaseModel):
    """ADR-006 9-stage 파이프라인 stage별 상태."""
    stage: str             # "s1_intake" | ... | "s9_publish"
    status: str            # "done" | "active" | "pending"
    at: Optional[datetime] = None      # ENTERED 이벤트의 started_at
    duration_ms: Optional[int] = None  # ENTERED→COMPLETED 누적 latency
    sources: List[StageSourceOut] = []


class ContentTimelineV2(BaseModel):
    """GET /api/contents/{id}/timeline v2 응답 (v1 호환 + ADR-006 확장)."""
    # v1 호환 필드 (기존 필드 그대로)
    content_id: int
    title: str
    content_type: str
    current_status: str
    stages: List[Any]            # 6-stage 기존 배열 보존

    # v2 추가 필드
    current_stage: Optional[str] = None
    intake_channel: Optional[str] = None
    pipeline_stages: List[StageOut]  # 9-stage ADR-006 배열

    class Config:
        from_attributes = True
