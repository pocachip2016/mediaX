import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from .base import OttSource
from .matcher import match_content
from .writer import upsert_distribution

logger = logging.getLogger(__name__)


@dataclass
class SyncSummary:
    channel: str
    fetched: int
    matched: int
    upserted: int
    dropped: int


def run_source(db: Session, source: OttSource, limit: int = 20) -> SyncSummary:
    """source.fetch_top() 결과를 DB에 upsert. item 단위 예외 격리."""
    items = source.fetch_top(limit=limit)
    summary = SyncSummary(
        channel=source.channel,
        fetched=len(items),
        matched=0,
        upserted=0,
        dropped=0,
    )
    for item in items:
        try:
            content_id = match_content(db, item)
            if content_id is None:
                summary.dropped += 1
                continue
            upsert_distribution(
                db,
                content_id=content_id,
                channel=source.channel,
                channel_type=source.channel_type,
                rank=item.rank,
                score=max(0.0, 1.0 - (item.rank - 1) * 0.05),
                raw=item.raw,
                external_id=item.external_id,
            )
            summary.matched += 1
            summary.upserted += 1
        except Exception:
            logger.exception("run_source item 처리 실패: channel=%s title=%s", source.channel, item.title)
            summary.dropped += 1
    return summary
