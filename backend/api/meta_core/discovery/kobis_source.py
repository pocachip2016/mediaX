"""
KobisDiscoverySource — KOBIS 기반 신규 한국 영화 발굴

지원 mode:
  upcoming          — 개봉예정작 (prdtStatNm=개봉예정)
  box_office_daily  — 어제 일별 박스오피스
  box_office_weekly — 이번 주 주간 박스오피스
  new_release       — 최근 30일 신규 개봉 영화

KOBIS 영역 = 영화만. 드라마/시리즈 없음.
참조: docs/dev/phase-c/sources.md §2, docs/dev/phase-c/beat-schedule.md §5.2
"""
from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Iterator

from api.meta_core.clients.kobis_client import KobisClient, KobisApiKeyMissing
from api.meta_core.discovery.base import DiscoveryResult, DiscoverySource

logger = logging.getLogger(__name__)

_ADULT_GRADES = {"청소년관람불가"}
_SKIP_TYPES = {"단편"}


def _movie_to_result(movie: dict) -> DiscoveryResult | None:
    movie_cd = movie.get("movieCd", "")
    movie_nm = movie.get("movieNm", "")
    if not movie_cd or not movie_nm:
        return None

    # 19+ 제외
    if movie.get("watchGradeNm") in _ADULT_GRADES:
        return None

    # 단편 제외 (옵션)
    if movie.get("prdtTypeNm") in _SKIP_TYPES:
        return None

    year_str = movie.get("prdtYear") or movie.get("openDt", "")[:4]
    production_year: int | None = None
    if year_str and year_str.isdigit() and len(year_str) == 4:
        production_year = int(year_str)

    return DiscoveryResult(
        source_type="kobis",
        external_id=movie_cd,
        title=movie_nm,
        original_title=movie.get("movieNmEn") or None,
        content_type="movie",
        production_year=production_year,
        poster_url=None,   # KOBIS 포스터 없음 — TMDB/KMDB 보강 영역
        synopsis=None,     # KOBIS 시놉시스 없음
        raw=movie,
    )


def _boxoffice_to_result(entry: dict) -> DiscoveryResult | None:
    """박스오피스 항목 → DiscoveryResult. 기본 필드만 채움."""
    movie_cd = entry.get("movieCd", "")
    movie_nm = entry.get("movieNm", "")
    if not movie_cd or not movie_nm:
        return None
    return DiscoveryResult(
        source_type="kobis",
        external_id=movie_cd,
        title=movie_nm,
        original_title=entry.get("movieNmEn") or None,
        content_type="movie",
        production_year=None,  # 박스오피스 응답에 연도 없음
        poster_url=None,
        synopsis=None,
        raw=entry,
    )


class KobisDiscoverySource(DiscoverySource):
    """KOBIS 기반 한국 영화 발굴 소스."""

    source_type = "kobis"

    def __init__(self, api_key: str):
        self._client = KobisClient(api_key=api_key)

    def discover(self, mode: str, **kwargs) -> Iterator[DiscoveryResult]:
        try:
            if mode == "upcoming":
                return iter(self._upcoming())
            elif mode == "box_office_daily":
                return iter(self._box_office_daily())
            elif mode == "box_office_weekly":
                return iter(self._box_office_weekly())
            elif mode == "new_release":
                return iter(self._new_release())
            else:
                raise ValueError(f"지원하지 않는 mode: {mode!r}")
        except KobisApiKeyMissing:
            logger.warning("[kobis] API 키 미설정 — 발굴 스킵")
            return iter([])

    def _upcoming(self) -> list[DiscoveryResult]:
        movies = self._client.search_movies(prdt_stat_nm="개봉예정")
        return [r for m in movies if (r := _movie_to_result(m)) is not None]

    def _box_office_daily(self) -> list[DiscoveryResult]:
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y%m%d")
        entries = self._client.daily_box_office(target_dt=yesterday)
        return [r for e in entries if (r := _boxoffice_to_result(e)) is not None]

    def _box_office_weekly(self) -> list[DiscoveryResult]:
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y%m%d")
        entries = self._client.weekly_box_office(target_dt=yesterday)
        return [r for e in entries if (r := _boxoffice_to_result(e)) is not None]

    def _new_release(self) -> list[DiscoveryResult]:
        today = datetime.now(timezone.utc)
        start = (today - timedelta(days=30)).strftime("%Y%m%d")
        end = today.strftime("%Y%m%d")
        movies = self._client.search_movies(open_start_dt=start, open_end_dt=end)
        return [r for m in movies if (r := _movie_to_result(m)) is not None]


# ── CLI 진입점 ──────────────────────────────────────────────────────────────

def _cli():
    parser = argparse.ArgumentParser(description="KOBIS Discovery CLI")
    parser.add_argument("--mode", required=True,
                        choices=["upcoming", "box_office_daily", "box_office_weekly", "new_release"])
    args = parser.parse_args()

    api_key = os.environ.get("KOBIS_API_KEY", "")
    if not api_key:
        print("KOBIS_API_KEY 환경변수 미설정 — 스킵")
        return

    source = KobisDiscoverySource(api_key=api_key)
    results = list(source.discover(args.mode))
    for r in results:
        print(f"[{r.content_type}] {r.external_id} | {r.title} ({r.production_year})")
    print(f"총 {len(results)}건")


if __name__ == "__main__":
    _cli()
