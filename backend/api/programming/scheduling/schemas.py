from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel

from .models import AutoEventType, AutoStage, ChildType, LinkSource, LinkStatus, NodeKind


# ── NodeSet ────────────────────────────────────────────────────────────────────

class NodeSetCreate(BaseModel):
    name: str
    description: Optional[str] = None


class NodeSetOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    status: str
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Node ───────────────────────────────────────────────────────────────────────

class NodeCreate(BaseModel):
    kind: NodeKind
    name: str
    set_id: Optional[int] = None
    slug: Optional[str] = None
    headline_copy: Optional[str] = None
    sub_copy: Optional[str] = None
    theme_features: Optional[dict] = None
    rule_query: Optional[dict] = None
    rank_source: Optional[str] = None
    rank_limit: Optional[int] = None
    window_start: Optional[date] = None
    window_end: Optional[date] = None
    is_draft: bool = False


class NodeUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    headline_copy: Optional[str] = None
    sub_copy: Optional[str] = None
    theme_features: Optional[dict] = None
    rule_query: Optional[dict] = None
    rank_source: Optional[str] = None
    rank_limit: Optional[int] = None
    window_start: Optional[date] = None
    window_end: Optional[date] = None
    is_active: Optional[bool] = None
    is_draft: Optional[bool] = None
    set_id: Optional[int] = None


class NodeOut(BaseModel):
    id: int
    set_id: Optional[int] = None
    kind: NodeKind
    name: str
    slug: Optional[str] = None
    headline_copy: Optional[str] = None
    sub_copy: Optional[str] = None
    theme_features: Optional[Any] = None
    rule_query: Optional[Any] = None
    rank_source: Optional[str] = None
    rank_limit: Optional[int] = None
    window_start: Optional[date] = None
    window_end: Optional[date] = None
    is_active: bool
    is_draft: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Link ───────────────────────────────────────────────────────────────────────

class LinkCreate(BaseModel):
    child_node_id: Optional[int] = None
    child_content_id: Optional[int] = None
    sort_order: Optional[int] = None
    is_pinned: bool = False
    window_start: Optional[date] = None
    window_end: Optional[date] = None
    copy_override: Optional[dict] = None
    source: LinkSource = LinkSource.manual
    confidence: Optional[float] = None
    status: LinkStatus = LinkStatus.active


class LinkBatchItem(BaseModel):
    child_node_id: Optional[int] = None
    child_content_id: Optional[int] = None
    sort_order: Optional[int] = None
    is_pinned: bool = False
    window_start: Optional[date] = None
    window_end: Optional[date] = None
    copy_override: Optional[dict] = None
    source: LinkSource = LinkSource.manual
    confidence: Optional[float] = None
    status: LinkStatus = LinkStatus.active


class LinkBatchRequest(BaseModel):
    children: list[LinkBatchItem]


class LinkReorderRequest(BaseModel):
    ordered_link_ids: list[int]


class LinkMoveRequest(BaseModel):
    new_parent_node_id: int


class LinkUpdate(BaseModel):
    sort_order: Optional[int] = None
    is_pinned: Optional[bool] = None
    window_start: Optional[date] = None
    window_end: Optional[date] = None
    copy_override: Optional[dict] = None
    status: Optional[LinkStatus] = None
    confidence: Optional[float] = None


class LinkOut(BaseModel):
    id: int
    parent_node_id: int
    child_type: ChildType
    child_node_id: Optional[int] = None
    child_content_id: Optional[int] = None
    sort_order: int
    is_pinned: bool
    window_start: Optional[date] = None
    window_end: Optional[date] = None
    copy_override: Optional[Any] = None
    source: LinkSource
    confidence: Optional[float] = None
    status: LinkStatus
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Backref ────────────────────────────────────────────────────────────────────

class BackrefOut(BaseModel):
    parent_node_id: int
    parent_node_name: str
    link_id: int
    child_type: str
    sort_order: int
    is_pinned: bool
    status: str
    source: str
    window_start: Optional[date] = None
    window_end: Optional[date] = None


# ── Tree / Graph ───────────────────────────────────────────────────────────────

class NodeTreeItem(BaseModel):
    node: NodeOut
    children: list["NodeTreeItem"] = []
    content_ids: list[int] = []

    model_config = {"from_attributes": True}


NodeTreeItem.model_rebuild()


class GraphEdge(BaseModel):
    """세트 전체 그래프의 평면 엣지 — 부모 노드 → 자식(노드/콘텐츠)."""
    link_id: int
    parent_node_id: int
    child_type: ChildType
    child_node_id: Optional[int] = None
    child_content_id: Optional[int] = None
    sort_order: int
    is_pinned: bool
    window_start: Optional[date] = None
    window_end: Optional[date] = None
    source: LinkSource
    status: LinkStatus

    model_config = {"from_attributes": True}


class SetGraphOut(BaseModel):
    """세트 한 개의 전체 노드 + 모든 링크(평면 edge). 캘린더/그래프 가시화용."""
    nodes: list[NodeOut] = []
    edges: list[GraphEdge] = []


# ── Suggest / Review ───────────────────────────────────────────────────────────

class SuggestRequest(BaseModel):
    threshold: float = 0.3   # confidence 최솟값; 미달 후보 자동제외
    limit: int = 50           # match_node_to_contents 상한
    intent: str | None = None  # 자연어 편성 의도(Tier1) — 있으면 노드 rule_query/facets 갱신


class InterpretedOut(BaseModel):
    rule_query: dict
    facets: dict
    provider_used: str


class SuggestOut(BaseModel):
    saved: list[LinkOut]
    skipped_count: int
    interpreted: InterpretedOut | None = None  # intent 해석 결과(intent 사용 시)


# ── 자동편성 파이프라인 (ADR-012) ─────────────────────────────────────────────

class AutoStageEventOut(BaseModel):
    id: int
    node_id: int
    stage: AutoStage
    event_type: AutoEventType
    source: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    latency_ms: Optional[int] = None
    payload_json: Optional[Any] = None
    error_text: Optional[str] = None
    actor: str

    model_config = {"from_attributes": True}


class AutoBucketCount(BaseModel):
    bucket: int
    stage_range: str       # 예: "P1", "P2/P3", "P4" …
    count: int
    label: str


class AutoSummaryOut(BaseModel):
    """버킷별 auto_enabled 노드 카운트."""
    buckets: list[AutoBucketCount]
    total_auto_enabled: int


class AutoNodeAdvanceOut(BaseModel):
    node_id: int
    result: str            # "ok" | "not_found" | "terminal" | "hold" | "skipped"
    auto_stage: Optional[AutoStage] = None
    schedule_score: Optional[float] = None


class AutoNodeRunOut(BaseModel):
    node_id: int
    stages_advanced: int
    final_result: str
    auto_stage: Optional[AutoStage] = None
    schedule_score: Optional[float] = None


class AutoPolicyOut(BaseModel):
    id: int
    p2_auto: bool
    p3_auto: bool
    p4_auto: bool
    p5_auto: bool
    p6_auto: bool
    confidence_threshold: float
    auto_tick_enabled: bool
    batch_size: int
    visibility_timeout: int
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AutoPolicyIn(BaseModel):
    p2_auto: Optional[bool] = None
    p3_auto: Optional[bool] = None
    p4_auto: Optional[bool] = None
    p5_auto: Optional[bool] = None
    p6_auto: Optional[bool] = None
    confidence_threshold: Optional[float] = None
    auto_tick_enabled: Optional[bool] = None
    batch_size: Optional[int] = None
    visibility_timeout: Optional[int] = None


class AutoEnableIn(BaseModel):
    auto_enabled: bool
