from datetime import datetime, timezone

from sqlalchemy.orm import Session

from api.distribution.models import ContentDistribution


def upsert_distribution(
    db: Session,
    *,
    content_id: int,
    channel: str,
    channel_type: str = "ott",
    rank: int,
    score: float,
    raw: dict,
    external_id: str | None,
) -> ContentDistribution:
    """(content_id, channel) UNIQUE 충돌 시 UPDATE, 없으면 INSERT."""
    now = datetime.now(timezone.utc)
    row = (
        db.query(ContentDistribution)
        .filter(
            ContentDistribution.content_id == content_id,
            ContentDistribution.channel == channel,
        )
        .first()
    )
    if row is None:
        row = ContentDistribution(
            content_id=content_id,
            channel=channel,
            channel_type=channel_type,
            external_id=external_id,
            popularity_rank=rank,
            popularity_score=score,
            raw_data=raw,
            synced_at=now,
        )
        db.add(row)
    else:
        row.popularity_rank = rank
        row.popularity_score = score
        row.raw_data = raw
        row.external_id = external_id
        row.synced_at = now
    db.commit()
    db.refresh(row)
    return row
