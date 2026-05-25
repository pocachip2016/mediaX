"""StageEvent — 파이프라인 단계별 이벤트 SSOT 테이블 (ADR-006)."""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship

from shared.database import Base
from api.programming.metadata.models.content import PipelineStage, StageEventType


def _utcnow():
    return datetime.now(timezone.utc)


class StageEvent(Base):
    __tablename__ = "stage_event"

    id          = Column(Integer, primary_key=True)
    content_id  = Column(Integer, ForeignKey("contents.id", ondelete="CASCADE"), nullable=False, index=True)
    stage       = Column(Enum(PipelineStage,  name="pipelinestage",  create_type=False, values_callable=lambda x: [e.value for e in x]), nullable=False, index=True)
    event_type  = Column(Enum(StageEventType, name="stageeventtype", create_type=False, values_callable=lambda x: [e.value for e in x]), nullable=False, index=True)
    source      = Column(String(100), nullable=True)  # tmdb/kobis/dam/brave/serpapi/gemini/ollama/user/system
    started_at  = Column(DateTime(timezone=True), default=_utcnow, index=True)
    ended_at    = Column(DateTime(timezone=True), nullable=True)
    latency_ms  = Column(Integer, nullable=True)
    payload_json = Column(JSON, nullable=True)   # ≤ 4KB; truncated if over
    error_text  = Column(Text, nullable=True)
    actor       = Column(String(100), nullable=False, default="system")

    content = relationship("Content", back_populates="stage_events")

    __table_args__ = (
        Index("ix_stage_event_content_stage",   "content_id", "stage"),
        Index("ix_stage_event_event_started",   "event_type", "started_at"),
    )
