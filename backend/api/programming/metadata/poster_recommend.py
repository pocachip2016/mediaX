"""
포스터 후보 추천 서비스

TMDB /images API 에서 다중 포스터 후보를 수집해 ContentImage 에 멱등 upsert 하고,
운영자가 원하는 포스터를 primary 로 선택할 수 있게 한다.

정렬 기준 (고정):
  1. iso_639_1 == "ko" 우선
  2. vote_average DESC
  3. width × height DESC (해상도)
"""

import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from api.programming.metadata.models import ContentImage, ImageType, ExternalMetaSource
from api.programming.metadata.models.external import ExternalSourceType
from api.programming.metadata.models.content import Content
from api.programming.metadata.content_kind import is_tv_type
from api.programming.metadata.tmdb_client import TmdbClient
from shared.config import settings

logger = logging.getLogger(__name__)

_TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


@dataclass
class PosterCandidate:
    url: str
    width: int | None
    height: int | None
    iso_639_1: str | None
    vote_average: float
    tmdb_file_path: str


def _sort_key(c: PosterCandidate) -> tuple:
    return (
        0 if c.iso_639_1 == "ko" else 1,
        -c.vote_average,
        -((c.width or 0) * (c.height or 0)),
    )


async def fetch_tmdb_poster_candidates(
    content: Content,
    db: Session,
    *,
    client: TmdbClient | None = None,
) -> list[PosterCandidate]:
    """TMDB /images API 호출 → 정렬된 PosterCandidate 리스트 반환.

    content 에 연결된 ExternalMetaSource(source_type=tmdb) 에서 external_id(tmdb_id) 를 조회.
    TMDB 매핑이 없으면 빈 리스트를 반환한다(예외 없음).
    """
    api_key = getattr(settings, "TMDB_API_KEY", "")
    if not api_key:
        logger.warning("[poster_recommend] TMDB_API_KEY 없음. 스킵.")
        return []

    src = (
        db.query(ExternalMetaSource)
        .filter(
            ExternalMetaSource.content_id == content.id,
            ExternalMetaSource.source_type == ExternalSourceType.tmdb,
        )
        .first()
    )
    if not src or not src.external_id:
        logger.info("[poster_recommend] content_id=%d TMDB 매핑 없음.", content.id)
        return []

    tmdb_id = int(src.external_id)
    is_tv = is_tv_type(content)

    async def _fetch(tc: TmdbClient) -> dict:
        if is_tv:
            return await tc.images_tv(tmdb_id)
        return await tc.images_movie(tmdb_id)

    try:
        if client is not None:
            data = await _fetch(client)
        else:
            async with TmdbClient(api_key=api_key) as tc:
                data = await _fetch(tc)
    except Exception as exc:
        logger.warning("[poster_recommend] TMDB /images 호출 실패 (content_id=%d): %s", content.id, exc)
        return []

    candidates: list[PosterCandidate] = []
    for p in data.get("posters", []):
        file_path = p.get("file_path")
        if not file_path:
            continue
        candidates.append(PosterCandidate(
            url=f"{_TMDB_IMAGE_BASE}{file_path}",
            width=p.get("width"),
            height=p.get("height"),
            iso_639_1=p.get("iso_639_1"),
            vote_average=float(p.get("vote_average") or 0),
            tmdb_file_path=file_path,
        ))

    candidates.sort(key=_sort_key)
    return candidates


def recommend_posters_for_content(
    db: Session,
    content_id: int,
    *,
    max_candidates: int = 10,
    client: TmdbClient | None = None,
) -> tuple[list[ContentImage], int]:
    """TMDB 포스터 후보를 ContentImage 에 멱등 upsert.

    - 신규 후보는 항상 is_primary=False (기존 primary 포스터를 절대 건드리지 않는다).
    - 이미 동일 URL 의 ContentImage 가 있으면 skip (멱등).
    - source='tmdb_recommend' 로 구분.

    반환: (image_type=poster 인 ContentImage 리스트, 신규 추가된 수)
    """
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        return [], 0

    candidates = asyncio.run(
        fetch_tmdb_poster_candidates(content, db, client=client)
    )

    existing_urls: set[str] = {
        img.url
        for img in db.query(ContentImage).filter(
            ContentImage.content_id == content_id,
            ContentImage.image_type == ImageType.poster,
        ).all()
    }

    added = 0
    for cand in candidates[:max_candidates]:
        if cand.url in existing_urls:
            continue
        db.add(ContentImage(
            content_id=content_id,
            image_type=ImageType.poster,
            url=cand.url,
            width=cand.width,
            height=cand.height,
            source="tmdb_recommend",
            is_primary=False,
        ))
        existing_urls.add(cand.url)
        added += 1

    if added:
        db.commit()

    result = (
        db.query(ContentImage)
        .filter(
            ContentImage.content_id == content_id,
            ContentImage.image_type == ImageType.poster,
        )
        .order_by(ContentImage.is_primary.desc(), ContentImage.id.asc())
        .all()
    )
    return result, added


def select_primary_poster(
    db: Session,
    content_id: int,
    image_id: int,
) -> ContentImage:
    """image_id 의 poster 를 primary 로 지정, 나머지 동일 content poster 는 primary 해제.

    image_id 가 해당 content 소속이 아니거나 image_type != poster 이면 ValueError.
    """
    target = (
        db.query(ContentImage)
        .filter(
            ContentImage.id == image_id,
            ContentImage.content_id == content_id,
            ContentImage.image_type == ImageType.poster,
        )
        .first()
    )
    if not target:
        raise ValueError(f"image_id={image_id} 는 content_id={content_id} 의 poster 가 아닙니다.")

    (
        db.query(ContentImage)
        .filter(
            ContentImage.content_id == content_id,
            ContentImage.image_type == ImageType.poster,
        )
        .update({"is_primary": False}, synchronize_session="fetch")
    )
    target.is_primary = True
    db.commit()
    db.refresh(target)
    return target
