"""facet 평가 모집단 정의 — 단일 SSOT.

드레인 셀렉터(`workers.tasks.facet_tasks._select_targets`)와 통계 API
(`router_facets.get_coverage`)가 동일 모집단을 쓰도록 공유한다. 한쪽만 바꾸면
드리프트가 생기므로 모집단 조건/정렬을 여기서만 정의한다.

정책 E: 개봉작 ∧ 시놉시스(overview) 보유. 국내/해외 무관, vote/popularity 게이트 폐지.
  - facet 분석의 실질 입력이 시놉시스이므로 overview 보유를 필요충분 조건으로 채택.
  - 모집단은 overview backfill 진척에 따라 점증(현재 ~48k → 최대 ~583k).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import and_, case

from api.programming.metadata.models.tmdb_cache import TmdbMovieCache


def released_with_overview_filter(today: date):
    """모집단 조건: 개봉작(release_date ≤ today) ∧ overview 보유."""
    return and_(
        TmdbMovieCache.release_date.isnot(None),
        TmdbMovieCache.release_date <= today,
        TmdbMovieCache.overview.isnot(None),
        TmdbMovieCache.overview != "",
    )


def facet_order_by():
    """드레인 정렬: 한국영화 우선 → 화제성(popularity) → 최신 → id.

    슬로우 드레인(~1,000/day)에서 의미작이 먼저 소진되도록 정렬한다.
    """
    ko_priority = case((TmdbMovieCache.original_language == "ko", 0), else_=1)
    return [
        ko_priority,
        TmdbMovieCache.popularity.desc().nullslast(),
        TmdbMovieCache.release_date.desc(),
        TmdbMovieCache.id.desc(),
    ]
