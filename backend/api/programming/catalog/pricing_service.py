import uuid
from typing import Any

from sqlalchemy.orm import Session

from api.programming.catalog.models import Pricing, PriceChangeLog, Quality, PurchaseType


def set_price(
    db: Session,
    content_id: int,
    quality: Quality | str,
    purchase_type: PurchaseType | str,
    price: int,
    changed_by: str | None = None,
    reason: str | None = None,
    batch_id: str | None = None,
) -> Pricing:
    """단건 가격 upsert. 기존 값과 다를 때만 PriceChangeLog 기록 (멱등)."""
    quality = Quality(quality) if isinstance(quality, str) else quality
    purchase_type = PurchaseType(purchase_type) if isinstance(purchase_type, str) else purchase_type

    row = db.query(Pricing).filter(
        Pricing.content_id == content_id,
        Pricing.quality == quality,
        Pricing.purchase_type == purchase_type,
    ).first()

    old_price: int | None = None
    if row is None:
        row = Pricing(
            content_id=content_id,
            quality=quality,
            purchase_type=purchase_type,
            price=price,
            is_active=True,
        )
        db.add(row)
    elif row.price == price:
        return row
    else:
        old_price = row.price
        row.price = price

    db.flush()

    log = PriceChangeLog(
        content_id=content_id,
        quality=quality,
        purchase_type=purchase_type,
        old_price=old_price,
        new_price=price,
        changed_by=changed_by,
        reason=reason,
        batch_id=batch_id,
    )
    db.add(log)
    db.flush()
    return row


def get_price_matrix(db: Session, content_id: int) -> dict[str, dict[str, int]]:
    """콘텐츠의 가격 매트릭스 반환. {purchase_type: {quality: price}}"""
    rows = db.query(Pricing).filter(
        Pricing.content_id == content_id,
        Pricing.is_active.is_(True),
    ).all()
    matrix: dict[str, dict[str, int]] = {}
    for row in rows:
        pt = row.purchase_type.value if isinstance(row.purchase_type, PurchaseType) else str(row.purchase_type)
        q = row.quality.value if isinstance(row.quality, Quality) else str(row.quality)
        matrix.setdefault(pt, {})[q] = row.price
    return matrix


def bulk_update(
    db: Session,
    items: list[dict[str, Any]],
    changed_by: str | None = None,
    reason: str | None = None,
) -> list[Pricing]:
    """여러 가격 일괄 변경. 공통 batch_id 자동 부여."""
    batch_id = str(uuid.uuid4())
    results = []
    for item in items:
        row = set_price(
            db,
            content_id=item["content_id"],
            quality=item["quality"],
            purchase_type=item["purchase_type"],
            price=item["price"],
            changed_by=changed_by,
            reason=reason,
            batch_id=batch_id,
        )
        results.append(row)
    return results


def list_price_changes(
    db: Session,
    content_id: int,
    limit: int = 50,
) -> list[PriceChangeLog]:
    return (
        db.query(PriceChangeLog)
        .filter(PriceChangeLog.content_id == content_id)
        .order_by(PriceChangeLog.id.desc())
        .limit(limit)
        .all()
    )


def delete_price(
    db: Session,
    content_id: int,
    quality: Quality | str,
    purchase_type: PurchaseType | str,
) -> None:
    quality = Quality(quality) if isinstance(quality, str) else quality
    purchase_type = PurchaseType(purchase_type) if isinstance(purchase_type, str) else purchase_type

    row = db.query(Pricing).filter(
        Pricing.content_id == content_id,
        Pricing.quality == quality,
        Pricing.purchase_type == purchase_type,
    ).first()
    if row is None:
        raise ValueError(
            f"pricing not found: content_id={content_id} quality={quality} purchase_type={purchase_type}"
        )
    db.delete(row)
    db.flush()
