"""
WebSearchDiscoverySource — 웹 검색 기반 신규 콘텐츠 발굴

Mode:
  query    — 단일 쿼리 (e.g., "한국 드라마 2026 신작")
  topic    — 주제 검색 (e.g., "OTT 단독 영화")
  trending — 사전 정의 5개 쿼리 일괄 (e.g., "넷플릭스 신작", "디즈니+ 예정작", ...)

결과:
  1. search_with_fallback으로 웹 검색
  2. Snippet에서 LLM 구조화 추출 (title, year, content_type)
  3. DiscoveryResult 생성 (external_id = URL SHA256 prefix)
"""

import asyncio
import hashlib
import json
import logging
import time
from typing import Iterator
from sqlalchemy.orm import Session

from api.meta_core.discovery.base import DiscoveryResult, DiscoverySource
from api.meta_core.web_search import search_with_fallback
from api.programming.metadata.llm import get_provider_chain

logger = logging.getLogger(__name__)

# 사전 정의 trending 쿼리 (5개, 한정)
_TRENDING_QUERIES = [
    "넷플릭스 신작 영화 2026",
    "디즈니플러스 예정작",
    "쿠팡플레이 한국 드라마",
    "웨이브 시리즈 신작",
    "티빙 독점 콘텐츠 2026",
]


class WebSearchDiscoverySource(DiscoverySource):
    """웹 검색 기반 SEED 발굴 소스."""

    source_type = "websearch"

    def __init__(self, db: Session):
        self._db = db

    def discover(self, mode: str, **kwargs) -> Iterator[DiscoveryResult]:
        """동기 인터페이스 → asyncio.run으로 위임."""
        results = asyncio.run(self._discover_async(mode, **kwargs))
        return iter(results)

    async def _discover_async(self, mode: str, **kwargs) -> list[DiscoveryResult]:
        """비동기 발굴 로직."""
        if mode == "query":
            return await self._query_mode(kwargs.get("query", ""))
        elif mode == "topic":
            return await self._topic_mode(kwargs.get("topic", ""))
        elif mode == "trending":
            return await self._trending_mode()
        else:
            logger.warning(f"Unknown mode: {mode}")
            return []

    async def _query_mode(self, query: str) -> list[DiscoveryResult]:
        """단일 쿼리 검색."""
        if not query:
            logger.warning("query_mode: empty query")
            return []

        logger.info(f"[websearch] query_mode: {query}")
        search_query = f"{query} 영화 드라마 시리즈"
        results = await self._search_and_extract(search_query, mode="query")
        return results

    async def _topic_mode(self, topic: str) -> list[DiscoveryResult]:
        """주제 검색."""
        if not topic:
            logger.warning("topic_mode: empty topic")
            return []

        logger.info(f"[websearch] topic_mode: {topic}")
        search_query = f"{topic} 한국 콘텐츠 2026"
        results = await self._search_and_extract(search_query, mode="topic")
        return results

    async def _trending_mode(self) -> list[DiscoveryResult]:
        """사전 정의 5개 쿼리 일괄."""
        all_results = []

        for query in _TRENDING_QUERIES:
            logger.info(f"[websearch] trending_mode: {query}")
            results = await self._search_and_extract(query, mode="trending")
            all_results.extend(results)

        logger.info(f"[websearch] trending_mode: {len(all_results)} total results")
        return all_results

    async def _search_and_extract(
        self, search_query: str, mode: str
    ) -> list[DiscoveryResult]:
        """
        웹 검색 + LLM 구조화 추출.

        Returns:
            DiscoveryResult 리스트
        """
        # Step 1: 웹 검색 (폴백 체인)
        try:
            results, provider = await search_with_fallback(
                search_query, self._db, num=8
            )
        except Exception as e:
            logger.error(f"[websearch] search_with_fallback failed: {e}")
            return []

        if not results:
            logger.warning(f"[websearch] no results for: {search_query}")
            return []

        logger.info(f"[websearch] {len(results)} results from {provider}")

        # Step 2: LLM 구조화 추출
        discovery_results = []
        for search_result in results:
            try:
                extracted = await self._extract_with_llm(search_result)
                if extracted:
                    discovery_results.append(extracted)
            except Exception as e:
                logger.warning(f"[websearch] extraction failed for {search_result.url}: {e}")

        return discovery_results

    async def _extract_with_llm(
        self, search_result
    ) -> DiscoveryResult | None:
        """
        LLM으로 snippet에서 구조화된 정보 추출.

        목표: title, original_title, content_type (movie/series), production_year
        """
        snippet = search_result.snippet[:500]  # 처음 500자만 사용

        prompt = f"""
웹 검색 결과에서 콘텐츠 정보를 추출해줘. 반드시 JSON으로 응답해.

검색 결과:
- 제목: {search_result.title}
- 설명: {snippet}
- URL: {search_result.url}

추출할 필드 (JSON):
{{
  "title": "콘텐츠 한국 제목 또는 영문명",
  "original_title": "원어 제목 (있으면) 또는 null",
  "content_type": "movie 또는 series (판단 불가면 null)",
  "production_year": "숫자 년도 (불명확하면 null)",
  "confidence": 0.0~1.0 (신뢰도)
}}

올바른 JSON만 반환. 해석 불가능하면 null값 사용.
"""

        try:
            # LLM 폴백 체인 사용
            chain = get_provider_chain("gemini")  # Gemini 우선
            for provider_class in chain:
                try:
                    provider = provider_class()
                    response = await provider.generate(prompt, system="")

                    # JSON 파싱
                    extracted = self._parse_extraction_response(response)
                    if extracted:
                        # external_id = URL SHA256 prefix (10자)
                        url_hash = hashlib.sha256(
                            search_result.url.encode()
                        ).hexdigest()[:10]

                        result = DiscoveryResult(
                            source_type=self.source_type,
                            external_id=url_hash,
                            title=extracted.get("title", search_result.title),
                            content_type=extracted.get("content_type", "movie"),
                            original_title=extracted.get("original_title"),
                            production_year=extracted.get("production_year"),
                            poster_url=None,
                            synopsis=search_result.snippet,
                            raw={
                                "url": search_result.url,
                                "search_title": search_result.title,
                                "provider": provider.engine_name,
                                "confidence": extracted.get("confidence", 0.5),
                            },
                        )
                        logger.info(f"[websearch] extracted: {result.title}")
                        return result

                except Exception as e:
                    logger.debug(f"[websearch] provider {provider_class.__name__} failed: {e}")
                    continue

        except Exception as e:
            logger.error(f"[websearch] LLM extraction error: {e}")

        return None

    def _parse_extraction_response(self, response: str) -> dict | None:
        """LLM 응답에서 JSON 추출."""
        try:
            # 응답에서 JSON 블록 찾기
            import re

            json_pattern = r"\{[^{}]*\}"
            match = re.search(json_pattern, response)
            if match:
                json_str = match.group(0)
                data = json.loads(json_str)
                return data
        except Exception as e:
            logger.debug(f"[websearch] JSON parse failed: {e}")

        return None
