from sqlalchemy import Boolean, Column, Float, Integer, JSON, String
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP

from shared.database import Base


class DamEvent(Base):
    __tablename__ = "dam_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(50), nullable=False, index=True)  # asset_matched | asset_unlinked | asset_confirmed
    content_id = Column(Integer, nullable=False, index=True)     # soft FK — 제약 없음
    asset_id = Column(String(200), nullable=False, index=True)   # Dam 측 자산 ID
    confidence = Column(Float, nullable=True)
    match_method = Column(String(50), nullable=True)             # clip_similarity | ocr_text | manual | web_search
    confirmed = Column(Boolean, default=False, nullable=False)
    payload_json = Column(JSON)
    received_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False, index=True)
