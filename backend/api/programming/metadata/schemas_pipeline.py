"""ADR-006 pipeline board API 스키마."""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class ChannelStats(BaseModel):
    count: int
    last_at: Optional[datetime] = None
    status: str  # "ok" | "stale"


class StageSourceProgress(BaseModel):
    source: str        # "tmdb" | "kobis" | "dam" | "brave" | "serpapi" | "gemini" | "ollama"
    result: str        # "ok" | "hit" | "miss" | "error" | "pending"
    latency_ms: Optional[int] = None


class StageContentItem(BaseModel):
    id: int
    title: str
    entered_at: Optional[datetime] = None
    seconds_in_stage: Optional[int] = None
    sources: list[StageSourceProgress] = []  # S4/S6 sub-source tree


class StageCount(BaseModel):
    count: int
    total_published: Optional[int] = None  # S9만 사용
    top_contents: list[StageContentItem] = []  # 최대 5건, 최초 ENTERED 시각 오름차순
    avg_seconds: Optional[int] = None  # 해당 stage 대기 콘텐츠 평균 체류시간
    error_count: int = 0  # 최근 1h FAILED 이벤트 수


class GateInfo(BaseModel):
    mode: str    # "manual" | "auto"
    pending: int


class AlertInfo(BaseModel):
    failed_queue: int
    rejected_archive: int
    enrichment_blocked: int


class BoardResponse(BaseModel):
    channels_24h: dict[str, ChannelStats]
    stages: dict[str, StageCount]
    gates: dict[str, GateInfo]
    alerts: AlertInfo


class GateAdvanceRequest(BaseModel):
    content_ids: list[int] = []   # 비우면 gate 대기 전체 처리
    simulate: bool = False
    if_match: Optional[int] = None  # 클라이언트 마지막 인지 event_id; 충돌 시 409


class GateAdvanceResponse(BaseModel):
    advanced: int
    skipped: int
    failed: int
    next_stage: str
    events: list[dict]


class GateModeRequest(BaseModel):
    mode: str  # "manual" | "auto"


class StageEventOut(BaseModel):
    id: int
    content_id: int
    stage: str
    event_type: str
    source: Optional[str] = None
    started_at: datetime
    actor: str
    latency_ms: Optional[int] = None
    error_text: Optional[str] = None

    class Config:
        from_attributes = True


class PaginatedStageEvents(BaseModel):
    items: list[StageEventOut]
    next_cursor: Optional[int] = None  # 다음 페이지 since= 값
    total: int
