"""
KmdbDiscoverySource — KMDB 기반 신규 한국 영화·드라마 발굴

지원 mode:
  new_release     — 최근 90일 등록 영화 (kmdb_public2)
  discover_drama  — 한국 드라마 (kmdb_dr)
  discover_movie  — 영화 풀스캔 페이지네이션 (백필 용도)

KMDB 는 시놉시스(plot)·포스터(posters) 보유 → 다른 소스보다 메타 풍부.
참조: docs/dev/phase-c/sources.md §2 KMDB 행
"""
from __future__ import annotations

import argparse
import logging
import os
import re
from typing import Iterator

from api.meta_core.clients.kmdb_client import KmdbClient, KmdbApiKeyMissing
from api.meta_core.discovery.base import DiscoveryResult, DiscoverySource

logger = logging.getLogger(__name__)

_HTML_TAG = re.compile(r"<[^>]+>")


def _clean(text: str | None) -> str | None:
    """HTML 태그 및 KMDB !HS/!HE 마커 제거."""
    if not text:
        return None
    cleaned = _HTML_TAG.sub("", text).replace("!HS", "").replace("!HE", "").strip()
    return cleaned or None


def _first_poster(posters: str | None) -> str | None:
    """'|' 구분 포스터 문자열에서 첫 번째 URL 추출."""
    if not posters:
        return None
    first = posters.split("|")[0].strip()
    return first or None


def _synopsis(item: dict) -> str | None:
    """plots.plot[] 에서 한국어 시놉시스 우선 추출."""
    plots = item.get("plots", {}).get("plot", [])
    for p in plots:
        if p.get("plotLang") == "한국어":
            return _clean(p.get("plotText"))
    if plots:
        return _clean(plots[0].get("plotText"))
    return None


def _original_title(item: dict) -> str | None:
    """titleEng 가 title 과 동일하면 가짜 영문 제목 → None."""
    title_ko = _clean(item.get("title"))
    title_en = _clean(item.get("titleEng"))
    if not title_en or title_en == title_ko:
        return None
    return title_en


def _item_to_result(item: dict, content_type: str) -> DiscoveryResult | None:
    docid = item.get("DOCID", "")
    title = _clean(item.get("title"))
    if not docid or not title:
        return None

    year_str = item.get("prodYear", "")
    production_year: int | None = None
    if year_str and str(year_str).isdigit():
        production_year = int(year_str)

    return DiscoveryResult(
        source_type="kmdb",
        external_id=docid,
        title=title,
        original_title=_original_title(item),
        content_type=content_type,
        production_year=production_year,
        poster_url=_first_poster(item.get("posters")),
        synopsis=_synopsis(item),
        raw=item,
    )


class KmdbDiscoverySource(DiscoverySource):
    """KMDB 기반 한국 영화·드라마 발굴 소스."""

    source_type = "kmdb"

    def __init__(self, api_key: str, recent_days: int = 90):
        self._client = KmdbClient(api_key=api_key)
        self._recent_days = recent_days

    def discover(self, mode: str, **kwargs) -> Iterator[DiscoveryResult]:
        try:
            if mode == "new_release":
                return iter(self._new_release())
            elif mode == "discover_drama":
                return iter(self._discover_drama())
            elif mode == "discover_movie":
                return iter(self._discover_movie())
            else:
                raise ValueError(f"지원하지 않는 mode: {mode!r}")
        except KmdbApiKeyMissing:
            logger.warning("[kmdb] API 키 미설정 — 발굴 스킵")
            return iter([])

    def _new_release(self) -> list[DiscoveryResult]:
        items = self._client.search_recent(days=self._recent_days, collection="kmdb_public2")
        return [r for i in items if (r := _item_to_result(i, "movie")) is not None]

    def _discover_drama(self) -> list[DiscoveryResult]:
        results = []
        for item in self._client.iter_collection(collection="kmdb_dr"):
            r = _item_to_result(item, "series")
            if r:
                results.append(r)
        return results

    def _discover_movie(self) -> list[DiscoveryResult]:
        results = []
        for item in self._client.iter_collection(collection="kmdb_public2"):
            r = _item_to_result(item, "movie")
            if r:
                results.append(r)
        return results


# ── CLI 진입점 ──────────────────────────────────────────────────────────────

def _cli():
    parser = argparse.ArgumentParser(description="KMDB Discovery CLI")
    parser.add_argument("--mode", required=True,
                        choices=["new_release", "discover_drama", "discover_movie"])
    parser.add_argument("--days", type=int, default=90, help="new_release 기준 일수")
    args = parser.parse_args()

    api_key = os.environ.get("KMDB_API_KEY", "")
    if not api_key:
        print("KMDB_API_KEY 환경변수 미설정 — 스킵")
        return

    source = KmdbDiscoverySource(api_key=api_key, recent_days=args.days)
    results = list(source.discover(args.mode))
    for r in results:
        print(f"[{r.content_type}] {r.external_id} | {r.title} ({r.production_year})")
    print(f"총 {len(results)}건")


if __name__ == "__main__":
    _cli()
