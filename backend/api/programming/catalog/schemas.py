from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel

from api.programming.catalog.models import Quality, PurchaseType


DupPolicy = Literal["merge", "overwrite", "reject"]


class CategorySetOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    category_count: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CategorySetCommit(BaseModel):
    name: str
    description: Optional[str] = None


class CategorySetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class CategoryBase(BaseModel):
    name: str
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None
    slug: Optional[str] = None


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class CategoryMoveRequest(BaseModel):
    new_parent_id: Optional[int] = None
    new_sort_order: Optional[int] = None


class CategoryMergeRequest(BaseModel):
    target_id: int


class ContentMapRequest(BaseModel):
    category_ids: list[int]
    primary_id: Optional[int] = None


class CategoryOut(BaseModel):
    id: int
    name: str
    slug: Optional[str] = None
    depth: int
    sort_order: int
    is_active: bool
    parent_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CategoryTreeNode(CategoryOut):
    children: list["CategoryTreeNode"] = []
    content_count: Optional[int] = None


CategoryTreeNode.model_rebuild()


# ── 일괄(Bulk) 입력 ───────────────────────────────────────────────────────────

class BulkCategoryNode(BaseModel):
    """일괄 입력용 정규화된 트리 노드 (파싱은 FE에서 수행)."""
    name: str
    children: list["BulkCategoryNode"] = []


class BulkCategoryCreate(BaseModel):
    nodes: list[BulkCategoryNode] = []
    parent_id: Optional[int] = None
    dup_policy: DupPolicy = "merge"


class BulkCategoryResult(BaseModel):
    created: int
    skipped: int
    overwritten: int = 0
    tree: list[CategoryTreeNode] = []


class LoadSetRequest(BaseModel):
    mode: Literal["replace", "merge"] = "replace"
    dup_policy: DupPolicy = "merge"


BulkCategoryNode.model_rebuild()
BulkCategoryResult.model_rebuild()


class ContentCategoryOut(BaseModel):
    id: int
    content_id: int
    category_id: int
    sort_order: int
    is_primary: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── 가격 정책 ─────────────────────────────────────────────────────────────────

class PricingSet(BaseModel):
    quality: Quality
    purchase_type: PurchaseType
    price: int
    changed_by: Optional[str] = None
    reason: Optional[str] = None


class PricingOut(BaseModel):
    id: int
    content_id: int
    quality: Quality
    purchase_type: PurchaseType
    price: int
    currency: str
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BulkPricingItem(BaseModel):
    content_id: int
    quality: Quality
    purchase_type: PurchaseType
    price: int


class BulkPricingRequest(BaseModel):
    items: list[BulkPricingItem]
    changed_by: Optional[str] = None
    reason: Optional[str] = None


class PriceChangeLogOut(BaseModel):
    id: int
    content_id: int
    quality: Quality
    purchase_type: PurchaseType
    old_price: Optional[int] = None
    new_price: int
    changed_by: Optional[str] = None
    reason: Optional[str] = None
    batch_id: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── 홀드백 ────────────────────────────────────────────────────────────────────

class HoldbackPolicyCreate(BaseModel):
    cp_name: str
    window_no: int
    name: str
    offset_days_start: int
    offset_days_end: Optional[int] = None
    price_rule: str
    is_active: bool = True


class HoldbackPolicyOut(BaseModel):
    id: int
    cp_name: str
    window_no: int
    name: str
    offset_days_start: int
    offset_days_end: Optional[int] = None
    price_rule: str
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class HoldbackApplyRequest(BaseModel):
    base_date: date


class HoldbackScheduleOut(BaseModel):
    id: int
    content_id: int
    window_no: int
    start_date: date
    end_date: Optional[date] = None
    price_id: Optional[int] = None
    source_policy_id: Optional[int] = None
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ActivateWindowRequest(BaseModel):
    quality: Optional[Quality] = None
    purchase_type: Optional[PurchaseType] = None
    price: Optional[int] = None
    changed_by: Optional[str] = None
