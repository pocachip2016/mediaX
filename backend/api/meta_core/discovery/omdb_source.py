"""
OmdbDiscoverySource — OMDb 기반 글로벌 콘텐츠 보완 발굴

지원 mode:
  search_title  — 제목 검색 (kwargs: title, year, type_)
  by_imdb_id    — IMDb ID 목록 → 상세 조회 (kwargs: imdb_ids=[...])

OMDb = IMDb 데이터 기반 글로벌 DB. 포스터·시놉시스·장르 풍부.
TMDB/KOBIS/KMDB 가 주요 발굴 소스; OMDb 는 갭 채우기 보완 용도.
참조: docs/dev/phase-c/sources.md §2 OMDb 행
"""
from __future__ import annotations

import logging
from typing import Iterator

from api.meta_core.clients.omdb_client import OmdbClient, OmdbApiKeyMissing
from api.meta_core.discovery.base import DiscoveryResult, DiscoverySource

logger = logging.getLogger(__name__)

_TYPE_MAP = {"movie": "movie", "series": "series", "episode": "series"}


def _item_to_result(item: dict) -> DiscoveryResult | None:
    imdb_id = item.get("imdbID", "")
    title = item.get("Title", "").strip()
    if not imdb_id or not title:
        return None

    raw_type = item.get("Type", "movie")
    content_type = _TYPE_MAP.get(raw_type, "movie")

    year_str = str(item.get("Year", ""))[:4]
    production_year: int | None = None
    if year_str.isdigit():
        production_year = int(year_str)

    # Poster — OMDb 반환 URL or None
    poster = item.get("Poster", "")
    poster_url = poster if poster and poster != "N/A" else None

    synopsis = item.get("Plot", "")
    synopsis = synopsis if synopsis and synopsis != "N/A" else None

    return DiscoveryResult(
        source_type="omdb",
        external_id=imdb_id,
        title=title,
        original_title=None,   # OMDb 원제 필드 없음
        content_type=content_type,
        production_year=production_year,
        poster_url=poster_url,
        synopsis=synopsis,
        raw=item,
    )


class OmdbDiscoverySource(DiscoverySource):
    """OMDb 기반 글로벌 콘텐츠 보완 소스."""

    source_type = "omdb"

    def __init__(self, api_key: str):
        self._client = OmdbClient(api_key=api_key)

    def discover(self, mode: str, **kwargs) -> Iterator[DiscoveryResult]:
        try:
            if mode == "search_title":
                return iter(self._search_title(**kwargs))
            elif mode == "by_imdb_id":
                return iter(self._by_imdb_id(kwargs.get("imdb_ids", [])))
            else:
                raise ValueError(f"지원하지 않는 mode: {mode!r}")
        except OmdbApiKeyMissing:
            logger.warning("[omdb] API 키 미설정 — 발굴 스킵")
            return iter([])

    def _search_title(self, title: str = "", year: int | None = None,
                      type_: str | None = None) -> list[DiscoveryResult]:
        if not title:
            return []
        items = self._client.search_title(title, year=year, type_=type_)
        return [r for i in items if (r := _item_to_result(i)) is not None]

    def _by_imdb_id(self, imdb_ids: list[str]) -> list[DiscoveryResult]:
        results = []
        for imdb_id in imdb_ids:
            detail = self._client.get_by_imdb_id(imdb_id)
            if detail:
                r = _item_to_result(detail)
                if r:
                    results.append(r)
        return results
