"""
inheritance — read-time 메타 상속 resolver

season/episode 의 빈 필드를 가장 가까운 비어있지 않은 조상(series 방향)에서
read-time 으로 채운다. DB 쓰기 없음 — 순수 함수.

ADR: docs/dev/meta-hierarchy/adr-001-content-kind-routing.md §D3
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from api.programming.metadata.content_kind import TV_TYPES
from api.programming.metadata.models.content import Content, ContentType, ContentMetadata

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

_SYNOPSIS_MIN = 50


def resolve_inherited_metadata(content: Content, db: Session) -> dict | None:
    """season/episode 에 대해 빈 필드를 조상에서 채운 dict 반환.

    반환 dict 키: production_year, country, synopsis, primary_genre, poster_url,
                  _source_id (상속 제공 조상 content_id)
    content 가 movie/series 이거나 parent 가 없으면 None 반환.
    """
    if content.content_type not in (ContentType.season, ContentType.episode):
        return None

    # 빈 필드 목록 파악
    missing: set[str] = _detect_missing(content, db)
    if not missing:
        return None

    # 조상 체인을 series 방향으로 올라가며 채움
    inherited: dict = {}
    source_id: int | None = None

    current = content
    seen: set[int] = {current.id}

    while current.parent_id is not None and missing:
        if current.parent_id in seen:
            break
        parent = db.query(Content).filter(Content.id == current.parent_id).first()
        if parent is None:
            break
        seen.add(parent.id)
        current = parent

        filled = _extract_fields(current, db, missing)
        if filled:
            inherited.update(filled)
            source_id = current.id
            missing -= set(filled.keys())

    if not inherited:
        return None

    inherited["_source_id"] = source_id
    return inherited


# ── private helpers ───────────────────────────────────────────────────────────

def _detect_missing(content: Content, db: Session) -> set[str]:
    """현재 content 에서 비어있는 상속 가능 필드 집합 반환."""
    missing: set[str] = set()

    if not content.production_year:
        missing.add("production_year")
    if not content.country:
        missing.add("country")

    meta = db.query(ContentMetadata).filter(
        ContentMetadata.content_id == content.id
    ).first()

    cp_syn = (meta.cp_synopsis or "") if meta else ""
    ai_syn = (meta.ai_synopsis or "") if meta else ""
    if len(cp_syn) < _SYNOPSIS_MIN and len(ai_syn) < _SYNOPSIS_MIN:
        missing.add("synopsis")

    has_genre = _has_primary_genre(content.id, db)
    if not has_genre and (not meta or not meta.ai_genre_primary):
        missing.add("primary_genre")

    has_poster = _has_primary_poster(content.id, db)
    if not has_poster and (not meta or not meta.cp_poster_url):
        missing.add("poster_url")

    return missing


def _extract_fields(ancestor: Content, db: Session, wanted: set[str]) -> dict:
    """ancestor 에서 wanted 필드의 값을 추출해 dict 반환 (빈 값 제외)."""
    result: dict = {}

    if "production_year" in wanted and ancestor.production_year:
        result["production_year"] = ancestor.production_year

    if "country" in wanted and ancestor.country:
        result["country"] = ancestor.country

    meta = db.query(ContentMetadata).filter(
        ContentMetadata.content_id == ancestor.id
    ).first()

    if "synopsis" in wanted and meta:
        best = meta.final_synopsis or meta.ai_synopsis or meta.cp_synopsis or ""
        if len(best) >= _SYNOPSIS_MIN:
            result["synopsis"] = best

    if "primary_genre" in wanted:
        if meta and meta.ai_genre_primary:
            result["primary_genre"] = meta.ai_genre_primary
        elif _has_primary_genre(ancestor.id, db):
            result["primary_genre"] = True  # 장르 행 존재 — 상위 쿼리에서 상세 조회

    if "poster_url" in wanted:
        url = _primary_poster_url(ancestor.id, db)
        if url:
            result["poster_url"] = url
        elif meta and meta.cp_poster_url:
            result["poster_url"] = meta.cp_poster_url

    return result


def _has_primary_genre(content_id: int, db: Session) -> bool:
    from api.programming.metadata.models.taxonomy import ContentGenre
    return db.query(ContentGenre).filter(
        ContentGenre.content_id == content_id,
        ContentGenre.is_primary.is_(True),
    ).first() is not None


def _has_primary_poster(content_id: int, db: Session) -> bool:
    from api.programming.metadata.models.image import ContentImage, ImageType
    return db.query(ContentImage).filter(
        ContentImage.content_id == content_id,
        ContentImage.image_type == ImageType.poster,
        ContentImage.is_primary.is_(True),
    ).first() is not None


def _primary_poster_url(content_id: int, db: Session) -> str | None:
    from api.programming.metadata.models.image import ContentImage, ImageType
    img = db.query(ContentImage).filter(
        ContentImage.content_id == content_id,
        ContentImage.image_type == ImageType.poster,
        ContentImage.is_primary.is_(True),
    ).first()
    return img.url if img else None
