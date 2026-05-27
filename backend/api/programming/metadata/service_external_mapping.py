"""
External mapping service — TMDB / KOBIS / KMDB 매핑 콘텐츠 목록.

service.py 분할 과정에서 추출 (dev-service-module-split Step 3).
"""

from sqlalchemy.orm import Session

from api.programming.metadata.models import (
    Content, ContentMetadata, ContentImage,
)


def list_tmdb_synced(
    db: Session,
    content_type: str | None = None,
    search: str | None = None,
    page: int = 1,
    size: int = 20,
):
    """TMDB ExternalMetaSource가 있는 최상위 콘텐츠 목록"""
    from api.programming.metadata.models import ExternalMetaSource, ExternalSourceType
    from api.programming.metadata.schemas import TmdbSyncedItem

    TMDB_IMG = "https://image.tmdb.org/t/p/w300"

    q = (
        db.query(Content, ExternalMetaSource, ContentMetadata)
        .join(
            ExternalMetaSource,
            (ExternalMetaSource.content_id == Content.id)
            & (ExternalMetaSource.source_type == ExternalSourceType.tmdb),
        )
        .outerjoin(ContentMetadata, ContentMetadata.content_id == Content.id)
        .filter(Content.parent_id.is_(None))
    )

    if content_type:
        q = q.filter(Content.content_type == content_type)
    if search:
        q = q.filter(Content.title.ilike(f"%{search}%"))

    total = q.count()
    rows = (
        q.order_by(ExternalMetaSource.matched_at.desc().nulls_last())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )

    items = []
    for content, ext, meta in rows:
        poster_path = ext.raw_json.get("poster_path") if ext.raw_json else None
        items.append(
            TmdbSyncedItem(
                content_id=content.id,
                title=content.title,
                original_title=content.original_title,
                content_type=content.content_type.value,
                status=content.status.value,
                production_year=content.production_year,
                cp_name=content.cp_name,
                tmdb_id=ext.external_id or "",
                poster_url=f"{TMDB_IMG}{poster_path}" if poster_path else None,
                match_confidence=ext.match_confidence,
                matched_at=ext.matched_at,
                quality_score=meta.quality_score if meta else None,
            )
        )

    return items, total


def list_external_mapped_contents(
    db: Session,
    source: str,
    content_type: str | None = None,
    search: str | None = None,
    page: int = 1,
    size: int = 20,
):
    """KOBIS/KMDB ExternalMetaSource가 연결된 콘텐츠 목록 (TMDB 스타일 조인)."""
    from api.programming.metadata.models import (
        ExternalMetaSource, ExternalSourceType, ContentImage, ImageType,
    )
    from api.programming.metadata.schemas import MappedExternalItem

    src_enum = ExternalSourceType(source)

    q = (
        db.query(Content, ExternalMetaSource, ContentMetadata)
        .join(
            ExternalMetaSource,
            (ExternalMetaSource.content_id == Content.id)
            & (ExternalMetaSource.source_type == src_enum),
        )
        .outerjoin(ContentMetadata, ContentMetadata.content_id == Content.id)
        .filter(Content.parent_id.is_(None))
    )

    if content_type:
        q = q.filter(Content.content_type == content_type)
    if search:
        q = q.filter(Content.title.ilike(f"%{search}%"))

    total = q.count()
    rows = (
        q.order_by(ExternalMetaSource.matched_at.desc().nulls_last())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )

    content_ids = [r[0].id for r in rows]
    poster_map: dict[int, str] = {}
    if content_ids:
        from api.programming.metadata.models import ImageType
        posters = (
            db.query(ContentImage)
            .filter(
                ContentImage.content_id.in_(content_ids),
                ContentImage.image_type == ImageType.poster,
                ContentImage.is_primary == True,  # noqa: E712
            )
            .all()
        )
        poster_map = {p.content_id: p.url for p in posters if p.url}

    items = []
    for content, ext, meta in rows:
        items.append(
            MappedExternalItem(
                content_id=content.id,
                title=content.title,
                original_title=content.original_title,
                content_type=content.content_type.value,
                status=content.status.value,
                production_year=content.production_year,
                cp_name=content.cp_name,
                external_id=ext.external_id or "",
                poster_url=poster_map.get(content.id),
                match_confidence=ext.match_confidence,
                matched_at=ext.matched_at,
                quality_score=meta.quality_score if meta else None,
            )
        )

    return items, total
