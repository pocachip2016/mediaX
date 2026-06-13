"""
TMDB API 클라이언트 — 레이트 리미터 내장

사용 예:
    async with TmdbClient(api_key=settings.TMDB_API_KEY) as client:
        data = await client.discover_movies(year=2024)

레이트 리밋: asyncio.Semaphore(max_concurrency=25) — TMDB 공식 50 req/sec 의 절반.
재시도: 429/5xx → exponential backoff (최대 3회).
API 키 보호: 로그 출력 시 `***` 로 redact.
"""

import asyncio
import logging
import time
from typing import Literal

import httpx

logger = logging.getLogger(__name__)

_BASE = "https://api.themoviedb.org/3"
_IMAGE_BASE = "https://image.tmdb.org/t/p"


class TmdbRateLimitError(Exception):
    """429 응답 후 max_retries 초과"""


class TmdbClient:
    def __init__(
        self,
        api_key: str,
        max_concurrency: int = 25,
        timeout: float = 15.0,
        max_retries: int = 3,
    ):
        self._api_key = api_key
        self._sem = asyncio.Semaphore(max_concurrency)
        self._timeout = timeout
        self._max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, *_):
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── Public API ─────────────────────────────────────────────────────

    async def discover_movies(
        self,
        year: int | None = None,
        page: int = 1,
        sort_by: str = "popularity.desc",
        release_date_gte: str | None = None,
        release_date_lte: str | None = None,
    ) -> dict:
        """GET /discover/movie — 필터·정렬·페이지네이션 지원."""
        params: dict = {"sort_by": sort_by, "page": page, "language": "ko-KR"}
        if year:
            params["primary_release_date.gte"] = f"{year}-01-01"
            params["primary_release_date.lte"] = f"{year}-12-31"
        if release_date_gte:
            params["primary_release_date.gte"] = release_date_gte
        if release_date_lte:
            params["primary_release_date.lte"] = release_date_lte
        return await self._get("/discover/movie", params)

    async def discover_tv(
        self,
        first_air_year: int | None = None,
        page: int = 1,
        sort_by: str = "popularity.desc",
        first_air_date_gte: str | None = None,
        first_air_date_lte: str | None = None,
    ) -> dict:
        """GET /discover/tv"""
        params: dict = {"sort_by": sort_by, "page": page, "language": "ko-KR"}
        if first_air_year:
            params["first_air_date.gte"] = f"{first_air_year}-01-01"
            params["first_air_date.lte"] = f"{first_air_year}-12-31"
        if first_air_date_gte:
            params["first_air_date.gte"] = first_air_date_gte
        if first_air_date_lte:
            params["first_air_date.lte"] = first_air_date_lte
        return await self._get("/discover/tv", params)

    async def changes(
        self,
        kind: Literal["movie", "tv"],
        start_date: str,
        end_date: str,
        page: int = 1,
    ) -> dict:
        """GET /movie/changes or /tv/changes — 변경된 ID 목록."""
        return await self._get(
            f"/{kind}/changes",
            {"start_date": start_date, "end_date": end_date, "page": page},
        )

    async def detail_movie(self, tmdb_id: int, language: str = "ko-KR") -> dict:
        """GET /movie/{id}?append_to_response=credits"""
        return await self._get(
            f"/movie/{tmdb_id}",
            {"language": language, "append_to_response": "credits"},
        )

    async def detail_tv(self, tmdb_id: int, language: str = "ko-KR") -> dict:
        """GET /tv/{id}?append_to_response=credits"""
        return await self._get(
            f"/tv/{tmdb_id}",
            {"language": language, "append_to_response": "credits"},
        )

    async def images_movie(self, tmdb_id: int) -> dict:
        """GET /movie/{id}/images — 포스터·백드롭·로고 다중 후보 반환 (언어 파라미터 없음 → 전 언어)."""
        return await self._get(f"/movie/{tmdb_id}/images", {})

    async def images_tv(self, tmdb_id: int) -> dict:
        """GET /tv/{id}/images — TV 포스터·백드롭·로고 다중 후보 반환."""
        return await self._get(f"/tv/{tmdb_id}/images", {})

    async def configuration(self) -> dict:
        """GET /configuration — 이미지 base URL·sizes 조회."""
        return await self._get("/configuration", {})

    @staticmethod
    def poster_url(poster_path: str | None, size: str = "w500") -> str | None:
        """poster_path → 완전한 이미지 URL 조합."""
        if not poster_path:
            return None
        return f"{_IMAGE_BASE}/{size}{poster_path}"

    # ── Internal ───────────────────────────────────────────────────────

    async def _get(self, path: str, params: dict) -> dict:
        full_params = {"api_key": self._api_key, **params}
        url = f"{_BASE}{path}"

        async with self._sem:
            for attempt in range(self._max_retries + 1):
                try:
                    client = self._client or httpx.AsyncClient(timeout=self._timeout)
                    resp = await client.get(url, params=full_params)

                    if resp.status_code == 429:
                        retry_after = int(resp.headers.get("Retry-After", 2 ** attempt))
                        logger.warning(
                            "[tmdb] 429 rate-limit on %s — waiting %ss (attempt %d/%d)",
                            path, retry_after, attempt + 1, self._max_retries,
                        )
                        if attempt < self._max_retries:
                            await asyncio.sleep(retry_after)
                            continue
                        raise TmdbRateLimitError(f"429 after {self._max_retries} retries: {path}")

                    if resp.status_code >= 500:
                        wait = 2 ** attempt
                        logger.warning(
                            "[tmdb] %d server error on %s — retry in %ss",
                            resp.status_code, path, wait,
                        )
                        if attempt < self._max_retries:
                            await asyncio.sleep(wait)
                            continue

                    resp.raise_for_status()
                    return resp.json()

                except (httpx.TimeoutException, httpx.ConnectError) as exc:
                    wait = 2 ** attempt
                    logger.warning("[tmdb] network error on %s: %s — retry in %ss", path, exc, wait)
                    if attempt < self._max_retries:
                        await asyncio.sleep(wait)
                    else:
                        raise

        return {}  # unreachable — satisfies type checker
