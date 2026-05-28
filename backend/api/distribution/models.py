from sqlalchemy import (
    Column, String, Integer, Float, Date, DateTime,
    Boolean, JSON, ForeignKey, UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from shared.database import Base


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    kind = Column(String(20), nullable=False)
    position = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_services_kind", "kind"),
    )


class ContentDistribution(Base):
    __tablename__ = "content_distributions"

    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(Integer, ForeignKey("contents.id"), nullable=False)
    channel = Column(String(50), nullable=False)
    channel_type = Column(String(20), nullable=False)
    external_id = Column(String(200))
    available_from = Column(Date)
    available_until = Column(Date)
    is_exclusive = Column(Boolean, default=False)
    popularity_rank = Column(Integer)
    popularity_score = Column(Float)
    raw_data = Column(JSON)
    synced_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("content_id", "channel", name="uq_distribution_content_channel"),
        Index("ix_dist_channel_type", "channel", "channel_type"),
        Index("ix_dist_content_id", "content_id"),
    )


class ServiceCategory(Base):
    __tablename__ = "service_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    category_type = Column(String(50), nullable=False)
    platform = Column(String(50), nullable=False)
    position = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    # 큐레이션 워크벤치 확장 (alembic 0025)
    headline_copy = Column(String(200), nullable=True)
    sub_copy = Column(String(300), nullable=True)
    theme_features = Column(JSON, nullable=True)
    source_mode = Column(String(20), default="manual", nullable=False)
    reference_external_id = Column(String(200), nullable=True)
    is_draft = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    items = relationship("ServiceCategoryItem", back_populates="category", cascade="all, delete-orphan")


class ServiceCategoryItem(Base):
    __tablename__ = "service_category_items"

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("service_categories.id"), nullable=False)
    content_id = Column(Integer, ForeignKey("contents.id"), nullable=False)
    rank = Column(Integer, nullable=False)
    score = Column(Float)
    added_at = Column(DateTime, server_default=func.now())

    category = relationship("ServiceCategory", back_populates="items")

    __table_args__ = (
        UniqueConstraint("category_id", "content_id", name="uq_cat_item_content"),
        Index("ix_cat_item_rank", "category_id", "rank"),
    )


class ExternalCuration(Base):
    """외부 OTT 큐레이션 섹션 영속화 — section_name이 카피 후보, content_id resolved."""
    __tablename__ = "external_curations"

    id = Column(Integer, primary_key=True, index=True)
    channel = Column(String(50), nullable=False)
    section_id = Column(String(200), nullable=False)
    section_name = Column(String(300), nullable=False)
    category_type = Column(String(50), nullable=False)
    trend_type = Column(String(20), default="ott", nullable=False)  # ott | trend | seasonal
    season_tag = Column(String(50), nullable=True)
    collected_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    matched_count = Column(Integer, default=0)
    total_count = Column(Integer, default=0)

    items = relationship("ExternalCurationItem", back_populates="curation", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("channel", "section_id", name="uq_ext_curation_channel_section"),
        Index("ix_ext_curation_channel", "channel"),
    )


class ExternalCurationItem(Base):
    """외부 큐레이션 섹션의 개별 작품 — content_id nullable (미매칭 시 NULL 보존)."""
    __tablename__ = "external_curation_items"

    id = Column(Integer, primary_key=True, index=True)
    external_curation_id = Column(Integer, ForeignKey("external_curations.id"), nullable=False)
    content_id = Column(Integer, ForeignKey("contents.id"), nullable=True)
    external_title = Column(String(300), nullable=False)
    external_rank = Column(Integer, nullable=False)
    production_year = Column(Integer, nullable=True)

    curation = relationship("ExternalCuration", back_populates="items")

    __table_args__ = (
        UniqueConstraint("external_curation_id", "external_rank", name="uq_ext_item_rank"),
        Index("ix_ext_item_content_id", "content_id"),
    )


class DeviceVariant(Base):
    __tablename__ = "device_variants"

    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(Integer, ForeignKey("contents.id"), nullable=False)
    device_type = Column(String(20), nullable=False)
    resolution = Column(String(20))
    format = Column(String(20))
    bitrate_kbps = Column(Integer)
    drm_type = Column(String(50))
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("content_id", "device_type", "resolution", name="uq_device_content_type_res"),
        Index("ix_device_content_id", "content_id"),
    )
