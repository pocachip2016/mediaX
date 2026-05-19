"""
content_kind — content_type 라우팅 SSOT

movie vs tv-type(series/season/episode) 판별 및 외부 소스 조회 대상 결정.
모든 `content_type == series` 리터럴은 이 모듈의 헬퍼로 대체한다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

from api.programming.metadata.models.content import Content, ContentType

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

TV_TYPES = frozenset({ContentType.series, ContentType.season, ContentType.episode})


def is_tv_type(content_or_type: Union[Content, ContentType, str]) -> bool:
    """series / season / episode 이면 True, movie 이면 False."""
    if isinstance(content_or_type, Content):
        ct = content_or_type.content_type
    elif isinstance(content_or_type, str):
        try:
            ct = ContentType(content_or_type)
        except ValueError:
            return False
    else:
        ct = content_or_type
    return ct in TV_TYPES


def tmdb_search_kind(content: Content) -> str:
    """TMDB 검색 엔드포인트 종류 반환 — "tv" | "movie"."""
    return "tv" if is_tv_type(content) else "movie"


def external_lookup_target(content: Content, db: Session) -> Content:
    """season/episode 는 최상위 series 조상을 반환, 없으면 self 반환.

    enrich 시 season/episode 단독 타이틀보다 series 단위로 외부 조회해야
    TMDB 매칭률이 높다. movie/series 는 self 를 그대로 반환한다.
    """
    if content.content_type not in (ContentType.season, ContentType.episode):
        return content

    current = content
    seen: set[int] = {current.id}

    while current.parent_id is not None:
        if current.parent_id in seen:
            break
        parent = db.query(Content).filter(Content.id == current.parent_id).first()
        if parent is None:
            break
        seen.add(parent.id)
        current = parent
        if current.content_type == ContentType.series:
            return current

    return content
