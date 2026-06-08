from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel

from .models import ChildType, LinkSource, LinkStatus, NodeKind


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
