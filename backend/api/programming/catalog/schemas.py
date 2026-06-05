from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


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


class ContentCategoryOut(BaseModel):
    id: int
    content_id: int
    category_id: int
    sort_order: int
    is_primary: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
