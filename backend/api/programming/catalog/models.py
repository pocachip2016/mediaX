from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime,
    ForeignKey, UniqueConstraint, Index,
)
from sqlalchemy.sql import func

from shared.database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(120), nullable=True)
    depth = Column(Integer, default=0, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_categories_parent_id", "parent_id"),
        Index("ix_categories_parent_sort", "parent_id", "sort_order"),
    )


class ContentCategory(Base):
    __tablename__ = "content_categories"

    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(Integer, ForeignKey("contents.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("content_id", "category_id", name="uq_content_category"),
        Index("ix_content_categories_content_id", "content_id"),
        Index("ix_content_categories_category_id", "category_id"),
    )
