from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.programming.metadata.models import Content
from .models import ContentDistribution, ServiceCategory, ServiceCategoryItem, DeviceVariant, Service
from .schemas import ServiceCategoryCreate, ServiceCategoryUpdate, ServiceCategoryItemCreate, ReorderRequest

_OTT_CHANNELS = ["ott_watcha", "ott_netflix", "ott_wave", "ott_tving"]


def get_services(db: Session, kind: str | None = None) -> list[Service]:
    q = db.query(Service).filter(Service.is_active == True)  # noqa: E712
    if kind:
        q = q.filter(Service.kind == kind)
    return q.order_by(Service.position).all()


def get_service_by_code(db: Session, code: str) -> Service | None:
    return db.query(Service).filter(Service.code == code).first()


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


def create_category(db: Session, data: ServiceCategoryCreate) -> ServiceCategory:
    obj = ServiceCategory(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_category_or_404(db: Session, category_id: int) -> ServiceCategory:
    obj = db.query(ServiceCategory).filter(ServiceCategory.id == category_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Category not found")
    return obj


def get_category_with_items(db: Session, category_id: int) -> dict:
    category = get_category_or_404(db, category_id)
    rows = (
        db.query(ServiceCategoryItem, Content.title)
        .join(Content, ServiceCategoryItem.content_id == Content.id)
        .filter(ServiceCategoryItem.category_id == category_id)
        .order_by(ServiceCategoryItem.rank)
        .all()
    )
    items = []
    for item, title in rows:
        item.content_title = title
        items.append(item)
    category.items = items
    return category


def update_category(db: Session, category_id: int, data: ServiceCategoryUpdate) -> ServiceCategory:
    obj = get_category_or_404(db, category_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    db.commit()
    db.refresh(obj)
    return obj


def delete_category(db: Session, category_id: int) -> dict:
    obj = get_category_or_404(db, category_id)
    db.delete(obj)
    db.commit()
    return {"id": category_id, "deleted": True}


def add_item(db: Session, category_id: int, data: ServiceCategoryItemCreate) -> ServiceCategoryItem:
    get_category_or_404(db, category_id)
    existing = (
        db.query(ServiceCategoryItem)
        .filter(
            ServiceCategoryItem.category_id == category_id,
            ServiceCategoryItem.content_id == data.content_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Item already in category")
    item = ServiceCategoryItem(
        category_id=category_id,
        content_id=data.content_id,
        rank=data.rank,
        score=data.score,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    content = db.query(Content).filter(Content.id == data.content_id).first()
    item.content_title = content.title if content else None
    return item


def remove_item(db: Session, category_id: int, item_id: int) -> dict:
    item = (
        db.query(ServiceCategoryItem)
        .filter(
            ServiceCategoryItem.id == item_id,
            ServiceCategoryItem.category_id == category_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    return {"id": item_id, "deleted": True}


def reorder_items(db: Session, category_id: int, data: ReorderRequest) -> dict:
    get_category_or_404(db, category_id)
    updated = 0
    for entry in data.items:
        item = (
            db.query(ServiceCategoryItem)
            .filter(
                ServiceCategoryItem.id == entry.id,
                ServiceCategoryItem.category_id == category_id,
            )
            .first()
        )
        if item:
            item.rank = entry.rank
            updated += 1
    db.commit()
    return {"updated": updated}


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
