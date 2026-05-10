"""
KOBIS (영화진흥위원회) API 클라이언트 — 동기 httpx, 1 req/sec

사용 예:
    client = KobisClient(api_key=settings.KOBIS_API_KEY)
    movies = client.search_movies(open_start_dt="20250101", open_end_dt="20250131")

Rate limit: 정부 공개 API (공식 무제한) — 정중함을 위해 1 req/sec 유지.
"""
import logging
import time
from datetime import datetime, timedelta

import httpx

logger = logging.getLogger(__name__)

_BASE = "http://www.kobis.or.kr/kobisopenapi/webservice/rest"
_DEFAULT_TIMEOUT = 30.0
_MIN_INTERVAL = 1.0   # 1 req/sec


class KobisApiKeyMissing(Exception):
    """KOBIS_API_KEY 미설정 시 raise"""


class KobisClient:
    def __init__(self, api_key: str, timeout: float = _DEFAULT_TIMEOUT):
        self._api_key = api_key
        self._timeout = timeout
        self._last_call = 0.0

    def _get(self, path: str, params: dict) -> dict:
        if not self._api_key:
            raise KobisApiKeyMissing("KOBIS_API_KEY 미설정")
        # 1 req/sec 준수
        elapsed = time.monotonic() - self._last_call
        if elapsed < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - elapsed)
        try:
            resp = httpx.get(
                f"{_BASE}{path}",
                params={"key": self._api_key, "itemPerPage": "100", **params},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            self._last_call = time.monotonic()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("[kobis] HTTP error %s: %s", path, exc)
            return {}

    # ── 개봉예정작 / 신규 등록 ──────────────────────────────────────────────

    def search_movies(
        self,
        open_start_dt: str | None = None,
        open_end_dt: str | None = None,
        prdt_stat_nm: str | None = None,
        cur_page: int = 1,
    ) -> list[dict]:
        """searchMovieList — 날짜 범위·제작상태 필터."""
        params: dict = {"curPage": str(cur_page)}
        if open_start_dt:
            params["openStartDt"] = open_start_dt
        if open_end_dt:
            params["openEndDt"] = open_end_dt
        if prdt_stat_nm:
            params["prdtStatNm"] = prdt_stat_nm
        data = self._get("/movie/searchMovieList.json", params)
        return data.get("movieListResult", {}).get("movieList", [])

    # ── 박스오피스 ──────────────────────────────────────────────────────────

    def daily_box_office(self, target_dt: str) -> list[dict]:
        """searchDailyBoxOfficeList — target_dt: YYYYMMDD."""
        data = self._get("/boxoffice/searchDailyBoxOfficeList.json",
                         {"targetDt": target_dt})
        return data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])

    def weekly_box_office(self, target_dt: str, week_gb: str = "0") -> list[dict]:
        """searchWeeklyBoxOfficeList — target_dt: YYYYMMDD, weekGb 0=전체 1=주말."""
        data = self._get("/boxoffice/searchWeeklyBoxOfficeList.json",
                         {"targetDt": target_dt, "weekGb": week_gb})
        return data.get("boxOfficeResult", {}).get("weeklyBoxOfficeList", [])
