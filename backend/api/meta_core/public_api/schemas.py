from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class ContentSummary(BaseModel):
    content_id: int
    title: str
    original_title: Optional[str] = None
    content_type: str        # movie | series | season | episode
    production_year: Optional[int] = None
    status: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContentSummaryPage(BaseModel):
    items: list[ContentSummary]
    next_ts: Optional[int] = None   # 다음 폴링용 unix timestamp (millis)
    total: int


class DamEventRequest(BaseModel):
    event_type: str                  # asset_matched | asset_unlinked | asset_confirmed
    content_id: int
    asset_id: str
    confidence: Optional[float] = None
    match_method: Optional[str] = None   # clip_similarity | ocr_text | manual | web_search
    confirmed: bool = False
    payload: Optional[dict[str, Any]] = None
