from sqlalchemy.orm import Session

from api.meta_core.scoring import normalize_title
from api.programming.metadata.models.content import Content

from .base import OttItem


def match_content(db: Session, item: OttItem) -> int | None:
    """title(정규화) + optional year 매칭 → content_id. 미매칭 시 None."""
    norm = normalize_title(item.title)
    if not norm:
        return None

    candidates = (
        db.query(Content)
        .filter(Content.title.isnot(None))
        .order_by(Content.id.desc())
        .all()
    )

    for content in candidates:
        if normalize_title(content.title or "") != norm:
            continue
        if item.production_year is not None and content.production_year is not None:
            if content.production_year != item.production_year:
                continue
        return content.id

    return None
