"""
tmdb_quota_backfill_tick 연도 선택 로직 회귀 테스트.

핵심: _next_backfill_year — current_year부터 start_year까지 역순으로
첫 미완료 연도를 고르고, 범위를 모두 채우면 None을 반환한다.
movie/tv 하한이 분리(1900/1950)되어 종류별로 독립 진행되는지 검증.
"""
from workers.tasks.tmdb_cache import (
    _next_backfill_year,
    _TMDB_MOVIE_BACKFILL_START_YEAR,
    _TMDB_TV_BACKFILL_START_YEAR,
)


def test_picks_highest_missing_year_reverse():
    """최신 연도부터 역순 — 가장 높은 미완료 연도를 선택"""
    done = {2026, 2025, 2024}
    assert _next_backfill_year(done, 1900, 2026) == 2023


def test_fills_gap_in_middle():
    """중간 갭이 있으면 그 연도를 선택 (종류별 갭 보완)"""
    done = {2026, 2025, 2023, 2022}  # 2024 누락
    assert _next_backfill_year(done, 1900, 2026) == 2024


def test_returns_none_when_range_exhausted():
    """하한~current 전부 완료 시 None (all_done 분기 유발)"""
    done = set(range(1990, 2027))
    assert _next_backfill_year(done, 1990, 2026) is None


def test_respects_lower_bound():
    """하한 미만 연도는 선택하지 않음 — 하한까지만 내려감"""
    done = set(range(1951, 2027))  # 1950만 미완료
    assert _next_backfill_year(done, 1950, 2026) == 1950
    # 1950까지 완료되면 그 아래(1949)는 건드리지 않음
    done.add(1950)
    assert _next_backfill_year(done, 1950, 2026) is None


def test_movie_tv_independent_lower_bounds():
    """movie 하한 1900, tv 하한 1950 — 같은 done 집합이라도 다른 결과"""
    # 1950~current 모두 완료, 1900~1949 미완료라고 가정
    done = set(range(1950, 2027))
    # movie는 1949까지 더 내려감
    assert _next_backfill_year(done, _TMDB_MOVIE_BACKFILL_START_YEAR, 2026) == 1949
    # tv는 1950이 하한이므로 더 내려갈 곳 없음 → None
    assert _next_backfill_year(done, _TMDB_TV_BACKFILL_START_YEAR, 2026) is None


def test_start_year_constants():
    """하한 상수 회귀 가드 — movie=1900, tv=1950"""
    assert _TMDB_MOVIE_BACKFILL_START_YEAR == 1900
    assert _TMDB_TV_BACKFILL_START_YEAR == 1950
