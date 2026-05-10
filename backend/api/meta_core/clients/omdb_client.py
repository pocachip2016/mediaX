"""
OMDb (Open Movie Database) API 클라이언트 — 동기 httpx

사용 예:
    client = OmdbClient(api_key=settings.OMDB_API_KEY)
    detail = client.get_by_imdb_id("tt1234567")
    results = client.search_title("Parasite", year=2019)

API 키 없으면 생성 시점에 예외 없이 생성되지만 메서드 호출 시
OmdbApiKeyMissing 을 raise 함 — 호출부에서 skip 처리 필요.
"""
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_BASE = "http://www.omdbapi.com/"


class OmdbApiKeyMissing(Exception):
    """OMDB_API_KEY 미설정 시 raise"""


class OmdbClient:
    def __init__(self, api_key: str, timeout: float = 10.0):
        self._api_key = api_key
        self._timeout = timeout

    def _get(self, params: dict) -> dict:
        if not self._api_key:
            raise OmdbApiKeyMissing("OMDB_API_KEY is not set")
        full_params = {"apikey": self._api_key, **params}
        try:
            resp = httpx.get(_BASE, params=full_params, timeout=self._timeout)
            resp.raise_for_status()
            data = resp.json()
            if data.get("Response") == "False":
                logger.debug("[omdb] API error: %s", data.get("Error"))
                return {}
            return data
        except httpx.HTTPError as exc:
            logger.warning("[omdb] HTTP error: %s", exc)
            return {}

    def get_by_imdb_id(self, imdb_id: str) -> dict:
        """IMDb ID 로 단건 상세 조회."""
        return self._get({"i": imdb_id, "plot": "short"})

    def search_title(self, title: str, year: int | None = None,
                     type_: str | None = None) -> list[dict]:
        """제목(+연도) 검색 → Search 결과 목록 반환.

        type_: 'movie' | 'series' | 'episode' | None
        """
        params: dict[str, Any] = {"s": title}
        if year:
            params["y"] = str(year)
        if type_:
            params["type"] = type_
        data = self._get(params)
        return data.get("Search", [])
