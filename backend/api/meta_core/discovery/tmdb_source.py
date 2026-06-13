"""
TmdbDiscoverySource — TMDB API 기반 신규 콘텐츠 발굴

지원 mode:
  trending_day   — /trending/{movie,tv}/day
  trending_week  — /trending/{movie,tv}/week
  upcoming       — /movie/upcoming?region=KR
  discover       — /discover/{movie,tv}?region=KR&with_origin_country=KR

참조: docs/dev/phase-c/sources.md §2, docs/dev/phase-c/beat-schedule.md §5
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import time
from typing import Iterator

from api.meta_core.discovery.base import DiscoveryResult, DiscoverySource
from api.programming.metadata.tmdb_client import TmdbClient

logger = logging.getLogger(__name__)

_MAX_PAGES = 5          # TMDB 페이지당 20건 → 최대 100건/소스/일
_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

# 19+ 등급 원어 표기 (TMDB certification 기준)
_ADULT_CERTIFICATIONS = {"NC-17", "X", "XXX", "18+", "R18+"}


def _poster(path: str | None) -> str | None:
    return f"{_IMAGE_BASE}{path}" if path else None


def _year(date_str: str | None) -> int | None:
    if date_str and len(date_str) >= 4:
        try:
            return int(date_str[:4])
        except ValueError:
            pass
    return None


def _is_adult(item: dict) -> bool:
    return bool(item.get("adult", False))


def _movie_to_result(item: dict) -> DiscoveryResult:
    return DiscoveryResult(
        source_type="tmdb",
        external_id=str(item["id"]),
        title=item.get("title") or item.get("name") or "",
        original_title=item.get("original_title") or item.get("original_name"),
        content_type="movie",
        production_year=_year(item.get("release_date")),
        poster_url=_poster(item.get("poster_path")),
        synopsis=item.get("overview") or None,
        raw=item,
    )


def _tv_to_result(item: dict) -> DiscoveryResult:
    return DiscoveryResult(
        source_type="tmdb",
        external_id=f"tv:{item['id']}",
        title=item.get("name") or item.get("title") or "",
        original_title=item.get("original_name") or item.get("original_title"),
        content_type="series",
        production_year=_year(item.get("first_air_date")),
        poster_url=_poster(item.get("poster_path")),
        synopsis=item.get("overview") or None,
        raw=item,
    )


class TmdbDiscoverySource(DiscoverySource):
    """TMDB Trending/Upcoming/Discover 발굴 소스."""

    source_type = "tmdb"

    def __init__(self, api_key: str, max_pages: int = _MAX_PAGES):
        self._api_key = api_key
        self._max_pages = max_pages

    def discover(self, mode: str, **kwargs) -> Iterator[DiscoveryResult]:
        """동기 인터페이스 — asyncio.run 으로 내부 비동기 메서드 위임."""
        return asyncio.run(self._discover_async(mode, **kwargs))

    async def _discover_async(self, mode: str, **kwargs) -> list[DiscoveryResult]:
        async with TmdbClient(api_key=self._api_key) as client:
            if mode == "trending_day":
                return await self._trending(client, "day")
            elif mode == "trending_week":
                return await self._trending(client, "week")
            elif mode == "upcoming":
                return await self._upcoming(client)
            elif mode == "discover":
                return await self._discover_kr(client)
            else:
                raise ValueError(f"지원하지 않는 mode: {mode!r}")

    async def _fill_overview(self, client: TmdbClient, item: dict, kind: str) -> None:
        """ko overview가 빈 값이면 en-US detail로 폴백 (in-place)."""
        if item.get("overview"):
            return
        tmdb_id = item.get("id")
        if not tmdb_id:
            return
        try:
            detail = await client._get(f"/{kind}/{tmdb_id}", {"language": "en-US"})
            item["overview"] = detail.get("overview") or ""
        except Exception:
            pass

    async def _trending(self, client: TmdbClient, window: str) -> list[DiscoveryResult]:
        results: list[DiscoveryResult] = []
        for kind in ("movie", "tv"):
            for page in range(1, self._max_pages + 1):
                data = await client._get(f"/trending/{kind}/{window}", {"page": page, "language": "ko-KR"})
                items = data.get("results", [])
                if not items:
                    break
                for item in items:
                    if _is_adult(item):
                        continue
                    await self._fill_overview(client, item, kind)
                    results.append(_movie_to_result(item) if kind == "movie" else _tv_to_result(item))
                if page >= data.get("total_pages", 1):
                    break
        return results

    async def _upcoming(self, client: TmdbClient) -> list[DiscoveryResult]:
        results: list[DiscoveryResult] = []
        for page in range(1, self._max_pages + 1):
            data = await client._get("/movie/upcoming", {"page": page, "language": "ko-KR", "region": "KR"})
            items = data.get("results", [])
            if not items:
                break
            for item in items:
                if _is_adult(item):
                    continue
                await self._fill_overview(client, item, "movie")
                results.append(_movie_to_result(item))
            if page >= data.get("total_pages", 1):
                break
        return results

    async def _discover_kr(self, client: TmdbClient) -> list[DiscoveryResult]:
        results: list[DiscoveryResult] = []
        for kind, convert in (("movie", _movie_to_result), ("tv", _tv_to_result)):
            for page in range(1, self._max_pages + 1):
                data = await client._get(
                    f"/discover/{kind}",
                    {
                        "page": page,
                        "language": "ko-KR",
                        "region": "KR",
                        "with_origin_country": "KR",
                        "sort_by": "popularity.desc",
                        "include_adult": "false",
                    },
                )
                items = data.get("results", [])
                if not items:
                    break
                for item in items:
                    if _is_adult(item):
                        continue
                    await self._fill_overview(client, item, kind)
                    results.append(convert(item))
                if page >= data.get("total_pages", 1):
                    break
        return results


# ── CLI 진입점 ──────────────────────────────────────────────────────────────

def _cli():
    parser = argparse.ArgumentParser(description="TMDB Discovery CLI")
    parser.add_argument("--mode", required=True,
                        choices=["trending_day", "trending_week", "upcoming", "discover"])
    parser.add_argument("--limit", type=int, default=0, help="출력 행 수 제한 (0=무제한)")
    args = parser.parse_args()

    api_key = os.environ.get("TMDB_API_KEY", "")
    if not api_key:
        print("TMDB_API_KEY 환경변수 미설정 — 스킵")
        return

    source = TmdbDiscoverySource(api_key=api_key)
    results = list(source.discover(args.mode))
    shown = results[: args.limit] if args.limit else results
    for r in shown:
        print(f"[{r.content_type}] {r.external_id} | {r.title} ({r.production_year})")
    print(f"총 {len(results)}건")


if __name__ == "__main__":
    _cli()
