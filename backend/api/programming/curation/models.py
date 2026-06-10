import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, Date, DateTime,
    Enum as SAEnum, Float, ForeignKey, Index, Integer,
    String, UniqueConstraint,
)
from sqlalchemy.sql import func

from shared.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class SlotCode(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"


class SlotType(str, enum.Enum):
    banner   = "banner"
    theme    = "theme"
    personal = "personal"
    genre    = "genre"
    ranking  = "ranking"
    promo    = "promo"


class Device(str, enum.Enum):
    all    = "all"
    tv     = "tv"
    mobile = "mobile"
    web    = "web"


class TimeBand(str, enum.Enum):
    all       = "all"
    morning   = "morning"
    afternoon = "afternoon"
    evening   = "evening"
    night     = "night"


class BannerPlanStatus(str, enum.Enum):
    draft     = "draft"
    review    = "review"
    approved  = "approved"
    published = "published"


class HomeSlot(Base):
    __tablename__ = "home_slots"

    id          = Column(Integer, primary_key=True, index=True)
    slot_code   = Column(SAEnum(SlotCode, name="slot_code"), nullable=False)
    slot_type   = Column(SAEnum(SlotType, name="slot_type"), nullable=False)
    device      = Column(SAEnum(Device,   name="curation_device"), nullable=False, server_default="all")
    time_band   = Column(SAEnum(TimeBand, name="time_band"),       nullable=False, server_default="all")
    position    = Column(Integer, nullable=False, server_default="0")
    node_set_id = Column(Integer, ForeignKey("programming_node_sets.id", ondelete="SET NULL"), nullable=True)
    is_active   = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at  = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_home_slots_slot_code_device_time_band", "slot_code", "device", "time_band"),
    )


class CurationBannerPlan(Base):
    __tablename__ = "curation_banner_plans"

    id             = Column(Integer, primary_key=True, index=True)
    week_start     = Column(Date, nullable=False)
    status         = Column(SAEnum(BannerPlanStatus, name="banner_plan_status"), nullable=False, server_default="draft")
    node_set_id    = Column(Integer, ForeignKey("programming_node_sets.id", ondelete="SET NULL"), nullable=True)
    ctr_prediction = Column(Float, nullable=True)
    reviewer       = Column(String(100), nullable=True)
    reviewed_at    = Column(DateTime(timezone=True), nullable=True)
    published_at   = Column(DateTime(timezone=True), nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at     = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("week_start", name="uq_curation_banner_plans_week_start"),
    )
