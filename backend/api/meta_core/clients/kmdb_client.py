"""
KMDb (한국영화데이터베이스) API 클라이언트 — 동기 httpx

사용 예:
    client = KmdbClient(api_key=settings.KMDB_API_KEY)
    results = client.search_movie("기생충", year=2019)

API 키 없으면 생성 시점에 예외 없이 생성되지만 메서드 호출 시
KmdbApiKeyMissing 을 raise 함 — 호출부에서 skip 처리 필요.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_BASE = "http://api.kmdb.or.kr/openapi-data2/wisenut/search_api/search_json2.jsp"


class KmdbApiKeyMissing(Exception):
    """KMDB_API_KEY 미설정 시 raise"""


class KmdbClient:
    def __init__(self, api_key: str, timeout: float = 15.0):
        self._api_key = api_key
        self._timeout = timeout

    def _get(self, params: dict) -> dict:
        if not self._api_key:
            raise KmdbApiKeyMissing("KMDB_API_KEY is not set")
        full_params = {"ServiceKey": self._api_key, "collection": "kmdb_public2",
                       "result": "json", **params}
        try:
            resp = httpx.get(_BASE, params=full_params, timeout=self._timeout)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("[kmdb] HTTP error: %s", exc)
            return {}

    def search_movie(self, title: str, year: int | None = None) -> list[dict]:
        """제목(+연도)으로 영화 검색 → 후보 목록 반환."""
        params: dict[str, Any] = {"query": title, "listCount": "5"}
        if year:
            params["releaseDts"] = str(year)
            params["releaseDte"] = str(year)
        data = self._get(params)
        try:
            return data["Data"][0]["Result"]
        except (KeyError, IndexError, TypeError):
            return []

    def get_movie_detail(self, docid: str) -> dict:
        """DOCID 로 영화 상세 조회."""
        data = self._get({"DOCID": docid})
        try:
            return data["Data"][0]["Result"][0]
        except (KeyError, IndexError, TypeError):
            return {}

    def search_recent(self, days: int, collection: str = "kmdb_public2",
                      list_count: int = 100) -> list[dict]:
        """최근 N일 등록작 — releaseDts 필터."""
        from datetime import datetime, timedelta, timezone
        today = datetime.now(timezone.utc)
        start = (today - timedelta(days=days)).strftime("%Y%m%d")
        end = today.strftime("%Y%m%d")
        data = self._get({
            "collection": collection,
            "releaseDts": start,
            "releaseDte": end,
            "listCount": str(list_count),
            "startCount": "0",
        })
        try:
            return data["Data"][0]["Result"]
        except (KeyError, IndexError, TypeError):
            return []

    def iter_collection(self, collection: str = "kmdb_public2",
                        list_count: int = 100):
        """전체 collection 페이지네이션 이터레이터 — 백필 용도."""
        start = 0
        while True:
            data = self._get({
                "collection": collection,
                "listCount": str(list_count),
                "startCount": str(start),
            })
            try:
                results = data["Data"][0]["Result"]
                total = int(data["Data"][0].get("TotalCount", 0))
            except (KeyError, IndexError, TypeError, ValueError):
                break
            if not results:
                break
            yield from results
            start += list_count
            if start >= total:
                break
