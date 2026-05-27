from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import ContentDistribution, ServiceCategory, DeviceVariant

_OTT_CHANNELS = ["ott_watcha", "ott_netflix", "ott_wave", "ott_tving"]


def get_channels_for_content(db: Session, content_id: int) -> list[ContentDistribution]:
    return (
        db.query(ContentDistribution)
        .filter(ContentDistribution.content_id == content_id)
        .order_by(ContentDistribution.channel)
        .all()
    )


def get_categories(db: Session, platform: str | None = None, is_active: bool | None = None) -> list[ServiceCategory]:
    q = db.query(ServiceCategory)
    if platform:
        q = q.filter(ServiceCategory.platform == platform)
    if is_active is not None:
        q = q.filter(ServiceCategory.is_active == is_active)
    return q.order_by(ServiceCategory.position).all()


def get_devices_for_content(db: Session, content_id: int) -> list[DeviceVariant]:
    return (
        db.query(DeviceVariant)
        .filter(DeviceVariant.content_id == content_id)
        .order_by(DeviceVariant.device_type)
        .all()
    )


def get_sync_status(db: Session) -> list[dict]:
    """4개 OTT 채널의 동기화 현황. 빈 DB에서도 4 row 반환."""
    rows = (
        db.query(
            ContentDistribution.channel,
            func.count(ContentDistribution.id).label("total_rows"),
            func.max(ContentDistribution.synced_at).label("last_synced_at"),
        )
        .filter(ContentDistribution.channel.in_(_OTT_CHANNELS))
        .group_by(ContentDistribution.channel)
        .all()
    )
    result = {r.channel: r for r in rows}
    return [
        {
            "channel": ch,
            "total_rows": result[ch].total_rows if ch in result else 0,
            "last_synced_at": result[ch].last_synced_at if ch in result else None,
        }
        for ch in _OTT_CHANNELS
    ]
