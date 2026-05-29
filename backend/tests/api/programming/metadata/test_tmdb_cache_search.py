"""
search_tmdb_cache — 인기순 기본 정렬 + has_poster 필터 회귀 테스트.

배경: 캐시 브라우저가 last_fetched_at 순으로 정렬돼 포스터 없는 비인기 롱테일이
상단을 점유하던 문제(dev-tmdb-poster-cache-ux Step 1) 수정 검증.
"""
from datetime import date, datetime, timedelta

from api.programming.metadata.models import TmdbMovieCache
from api.programming.metadata.service_external_cache import search_tmdb_cache


def _mk(db, tmdb_id, title, popularity, poster_path, fetched_offset_days):
    db.add(TmdbMovieCache(
        id=tmdb_id,
        title=title,
        original_title=title,
        release_date=date(2020, 1, 1),
        popularity=popularity,
        poster_path=poster_path,
        last_fetched_at=datetime.utcnow() - timedelta(days=fetched_offset_days),
    ))


def _seed(db):
    # 인기 높지만 fetch는 오래됨 + 포스터 있음
    _mk(db, 1, "Popular w/ poster", popularity=50.0, poster_path="/p1.jpg", fetched_offset_days=10)
    # 비인기 + 포스터 없음 + 가장 최근 fetch (기존 정렬이면 1순위로 떴음)
    _mk(db, 2, "Obscure no poster", popularity=0.1, poster_path=None, fetched_offset_days=0)
    # 중간 인기 + 포스터 있음
    _mk(db, 3, "Mid w/ poster", popularity=5.0, poster_path="/p3.jpg", fetched_offset_days=5)
    # popularity NULL + 포스터 없음 (빈 문자열)
    _mk(db, 4, "Null pop empty poster", popularity=None, poster_path="", fetched_offset_days=1)
    db.commit()


def test_default_sort_is_popularity_desc_nulls_last(db):
    _seed(db)
    items, total = search_tmdb_cache(db, title=None, kind="movie", page=1, size=10)
    assert total == 4
    order = [it["id"] for it in items]
    # 인기순: 1(50) > 3(5) > 2(0.1) > 4(NULL, 맨 뒤)
    assert order == [1, 3, 2, 4]


def test_has_poster_true_filters_out_missing(db):
    _seed(db)
    items, total = search_tmdb_cache(db, title=None, kind="movie", page=1, size=10, has_poster=True)
    assert total == 2
    assert {it["id"] for it in items} == {1, 3}
    assert all(it["poster_url"] for it in items)


def test_has_poster_false_returns_only_missing(db):
    _seed(db)
    items, total = search_tmdb_cache(db, title=None, kind="movie", page=1, size=10, has_poster=False)
    assert total == 2
    assert {it["id"] for it in items} == {2, 4}
    assert all(it["poster_url"] is None for it in items)


def test_sort_recent_preserves_fetch_order(db):
    _seed(db)
    items, _ = search_tmdb_cache(db, title=None, kind="movie", page=1, size=10, sort="recent")
    # 최근 fetch 순: 2(0d) > 4(1d) > 3(5d) > 1(10d)
    assert [it["id"] for it in items] == [2, 4, 3, 1]
