"""
통합 소스 검색 — TMDB, KOBIS, KMDB, Watcha 병렬 호출
"""

import asyncio
import logging
from typing import Optional

from shared.config import settings
from api.programming.metadata.tmdb_client import TmdbClient
from api.meta_core.clients.kobis_client import KobisClient

logger = logging.getLogger(__name__)


class SourcesAggregator:
    """여러 외부 소스에서 병렬로 검색하는 aggregator."""

    async def search(
        self, query: str, sources: Optional[list[str]] = None
    ) -> dict:
        """
        병렬 검색 (asyncio.gather).
        단일 source 실패 시 다른 source 결과 반환 + errors[] 포함.

        Args:
            query: 검색어
            sources: 검색 대상 ['tmdb', 'kobis', 'kmdb', 'watcha'] (기본: ['tmdb', 'kobis'])

        Returns:
            {
                "results": [
                    {"title", "year", "director", "source", "match_percent", "metadata"},
                    ...
                ],
                "errors": [
                    {"source": "tmdb", "error": "..."}
                ]
            }
        """
        if sources is None:
            sources = ["tmdb", "kobis"]

        tasks = []
        source_map = {}

        for source in sources:
            if source == "tmdb":
                tasks.append(self._search_tmdb(query))
                source_map[len(tasks) - 1] = "tmdb"
            elif source == "kobis":
                tasks.append(self._search_kobis(query))
                source_map[len(tasks) - 1] = "kobis"
            elif source == "kmdb":
                tasks.append(self._search_kmdb(query))
                source_map[len(tasks) - 1] = "kmdb"
            elif source == "watcha":
                tasks.append(self._search_watcha(query))
                source_map[len(tasks) - 1] = "watcha"

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_results = []
        errors = []

        for idx, result in enumerate(results):
            source_name = source_map.get(idx, "unknown")

            if isinstance(result, Exception):
                logger.warning(f"Search failed for {source_name}: {result}")
                errors.append({"source": source_name, "error": str(result)})
            elif result:
                for item in result:
                    item["source"] = source_name
                    all_results.append(item)

        return {
            "results": all_results,
            "errors": errors if errors else None,
        }

    async def _search_tmdb(self, query: str) -> list[dict]:
        """TMDB 검색 (영화+TV)."""
        try:
            async with TmdbClient(
                api_key=settings.TMDB_API_KEY,
                max_concurrency=5,
                timeout=10.0,
            ) as client:
                # TMDB는 search/multi endpoint가 있지만, 여기선 간단히 discover로 처리
                # 실제로는 search/multi를 사용하면 더 정확함
                movies = await client.discover_movies(
                    with_keywords=query
                )  # 단순화된 검색
                return [
                    {
                        "title": m.get("title", ""),
                        "year": m.get("release_date", "")[:4] if m.get("release_date") else None,
                        "director": None,  # TMDB discover에선 director 미포함
                        "match_percent": int(m.get("popularity", 0) * 10 // 100),
                        "metadata": {
                            "tmdb_id": m.get("id"),
                            "overview": m.get("overview"),
                            "poster_path": m.get("poster_path"),
                        },
                    }
                    for m in movies if isinstance(movies, list) and m
                ]
        except Exception as e:
            logger.error(f"TMDB search error: {e}")
            raise

    async def _search_kobis(self, query: str) -> list[dict]:
        """KOBIS 검색 (한국 영화)."""
        try:
            client = KobisClient(api_key=settings.KOBIS_API_KEY)
            results = client.search_movies(query)
            return [
                {
                    "title": r.get("movieNm", ""),
                    "year": int(r.get("openDt", "")[:4]) if r.get("openDt") else None,
                    "director": r.get("directors", [{}])[0].get("peopleNm") if r.get("directors") else None,
                    "match_percent": 80,  # KOBIS는 직접 검색이므로 높은 매치율
                    "metadata": {
                        "kobis_movie_cd": r.get("movieCd"),
                        "movie_nm_en": r.get("movieNmEn"),
                    },
                }
                for r in results if isinstance(results, list) and r
            ]
        except Exception as e:
            logger.error(f"KOBIS search error: {e}")
            raise

    async def _search_kmdb(self, query: str) -> list[dict]:
        """KMDB 검색 (한국 드라마·예능)."""
        # KMDB client 미구현 — stub
        return []

    async def _search_watcha(self, query: str) -> list[dict]:
        """Watcha 검색."""
        # Watcha client 미구현 — stub
        return []
