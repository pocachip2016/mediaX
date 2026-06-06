import enum

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Date,
    ForeignKey, UniqueConstraint, Index, Enum as SAEnum,
)
from sqlalchemy.sql import func

from shared.database import Base


class Quality(str, enum.Enum):
    SD = "SD"
    HD = "HD"
    FHD = "FHD"
    UHD_4K = "UHD_4K"


class PurchaseType(str, enum.Enum):
    single = "single"
    series_episode = "series_episode"
    season_package = "season_package"
    est_single = "est_single"
    est_season = "est_season"


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


class Pricing(Base):
    __tablename__ = "pricing"

    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(Integer, ForeignKey("contents.id", ondelete="CASCADE"), nullable=False)
    quality = Column(SAEnum(Quality, name="quality_enum"), nullable=False)
    purchase_type = Column(SAEnum(PurchaseType, name="purchase_type_enum"), nullable=False)
    price = Column(Integer, nullable=False)
    currency = Column(String(10), nullable=False, server_default="KRW")
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("content_id", "quality", "purchase_type", name="uq_pricing_content_quality_type"),
        Index("ix_pricing_content_id", "content_id"),
    )


class HoldbackPolicy(Base):
    __tablename__ = "holdback_policies"

    id = Column(Integer, primary_key=True, index=True)
    cp_name = Column(String(200), nullable=False)
    window_no = Column(Integer, nullable=False)
    name = Column(String(200), nullable=False)
    offset_days_start = Column(Integer, nullable=False)
    offset_days_end = Column(Integer, nullable=True)
    price_rule = Column(String(50), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("cp_name", "window_no", name="uq_holdback_policy_cp_window"),
        Index("ix_holdback_policies_cp_name", "cp_name"),
    )


class HoldbackSchedule(Base):
    __tablename__ = "holdback_schedules"

    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(Integer, ForeignKey("contents.id", ondelete="CASCADE"), nullable=False)
    window_no = Column(Integer, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    price_id = Column(Integer, ForeignKey("pricing.id", ondelete="SET NULL"), nullable=True)
    source_policy_id = Column(Integer, ForeignKey("holdback_policies.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(20), nullable=False, server_default="scheduled")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("content_id", "window_no", name="uq_holdback_schedule_content_window"),
        Index("ix_holdback_schedules_content_id", "content_id"),
        Index("ix_holdback_schedules_start_date", "start_date"),
    )


class PriceChangeLog(Base):
    __tablename__ = "price_change_log"

    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(Integer, ForeignKey("contents.id", ondelete="CASCADE"), nullable=False)
    quality = Column(SAEnum(Quality, name="quality_enum"), nullable=False)
    purchase_type = Column(SAEnum(PurchaseType, name="purchase_type_enum"), nullable=False)
    old_price = Column(Integer, nullable=True)
    new_price = Column(Integer, nullable=False)
    changed_by = Column(String(200), nullable=True)
    reason = Column(String(500), nullable=True)
    batch_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_price_change_log_content_id", "content_id"),
        Index("ix_price_change_log_batch_id", "batch_id"),
    )
