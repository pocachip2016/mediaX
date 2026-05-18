from sqlalchemy.orm import Session

from .models import ContentDistribution, ServiceCategory, DeviceVariant


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
