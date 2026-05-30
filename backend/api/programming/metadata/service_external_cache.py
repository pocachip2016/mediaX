"""
External cache service — TMDB / KOBIS / KMDB 로컬 캐시 통계·검색.

사용자 rollback 영역: KMDB/KOBIS/TMDB 외부소스 페이지 캐시 목록·검색·페이지네이션.
service.py 분할 과정에서 추출 (dev-service-module-split Step 2).
"""

from datetime import datetime, timedelta, timezone
from collections import defaultdict
from zoneinfo import ZoneInfo

from sqlalchemy import or_
from sqlalchemy.orm import Session


_KST = ZoneInfo("Asia/Seoul")


def _last_7_kst_dates() -> list[str]:
    """오늘(KST) 기준 지난 7일 연속 날짜(오래된→최신) ISO 문자열."""
    today = datetime.now(_KST).date()
    return [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]


def _kst_day(dt) -> str | None:
    """datetime(aware/naive)을 KST 날짜 ISO 문자열로 변환. naive는 UTC로 간주."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_KST).date().isoformat()


def get_tmdb_cache_stats(db) -> dict:
    """tmdb_movie_cache / tmdb_tv_cache / tmdb_sync_log 기반 통계."""
    from api.programming.metadata.models import (
        TmdbMovieCache, TmdbTvCache, TmdbPersonCache, TmdbSyncLog,
    )
    from sqlalchemy import func

    now = datetime.utcnow()
    cutoff_24h = now - timedelta(hours=24)
    cutoff_7d = now - timedelta(days=8)  # KST 경계 보호 — 최종 축이 7일로 필터

    total_movies = db.query(TmdbMovieCache).count()
    total_tv = db.query(TmdbTvCache).count()
    total_persons = db.query(TmdbPersonCache).count()

    last_24h_movies = db.query(TmdbMovieCache).filter(TmdbMovieCache.first_fetched_at >= cutoff_24h).count()
    last_24h_tv = db.query(TmdbTvCache).filter(TmdbTvCache.first_fetched_at >= cutoff_24h).count()
    last_24h_errors = (
        db.query(func.coalesce(func.sum(TmdbSyncLog.errors), 0))
        .filter(TmdbSyncLog.started_at >= cutoff_24h)
        .scalar() or 0
    )

    recent_logs = (
        db.query(TmdbSyncLog)
        .filter(TmdbSyncLog.started_at >= cutoff_7d)
        .all()
    )

    day_map: dict = defaultdict(lambda: {"movies": 0, "tv": 0, "errors": 0})
    for log in recent_logs:
        day_str = _kst_day(log.started_at)
        if day_str is None:
            continue
        is_movie = "movie" in str(log.source)
        day_map[day_str]["movies" if is_movie else "tv"] += log.items_inserted or 0
        day_map[day_str]["errors"] += log.errors or 0

    # 오늘(KST) 기준 연속 7일 축 — 데이터 없는 날은 0
    last_7d = [
        {"date": d, "movies": day_map[d]["movies"], "tv": day_map[d]["tv"], "errors": day_map[d]["errors"]}
        for d in _last_7_kst_dates()
    ]

    oldest = db.query(func.min(TmdbMovieCache.release_date)).scalar()
    newest = db.query(func.max(TmdbMovieCache.release_date)).scalar()

    last_log = db.query(TmdbSyncLog).order_by(TmdbSyncLog.started_at.desc()).first()

    return {
        "total_movies": total_movies,
        "total_tv": total_tv,
        "total_persons": total_persons,
        "last_24h_movies_added": last_24h_movies,
        "last_24h_tv_added": last_24h_tv,
        "last_24h_errors": int(last_24h_errors),
        "last_7d_daily": last_7d,
        "oldest_movie_year": oldest.year if oldest else None,
        "newest_movie_year": newest.year if newest else None,
        "last_run_at": last_log.started_at if last_log else None,
        "last_run_status": last_log.status.value if last_log else None,
    }


def list_tmdb_sync_log(db, source: str | None, status: str | None, page: int, size: int):
    from api.programming.metadata.models import TmdbSyncLog

    q = db.query(TmdbSyncLog)
    if source:
        q = q.filter(TmdbSyncLog.source == source)
    if status:
        q = q.filter(TmdbSyncLog.status == status)

    total = q.count()
    items = q.order_by(TmdbSyncLog.started_at.desc()).offset((page - 1) * size).limit(size).all()
    return items, total


def list_tmdb_cache_recent(db, kind: str, limit: int) -> list:
    from api.programming.metadata.models import TmdbMovieCache, TmdbTvCache
    from api.programming.metadata.tmdb_client import TmdbClient

    results = []
    if kind in ("movie", "both"):
        for r in db.query(TmdbMovieCache).order_by(TmdbMovieCache.last_fetched_at.desc(), TmdbMovieCache.id.asc()).limit(limit).all():
            results.append({
                "id": r.id, "title": r.title, "original_title": r.original_title,
                "release_date": r.release_date, "first_air_date": None,
                "popularity": r.popularity, "vote_average": r.vote_average,
                "poster_url": TmdbClient.poster_url(r.poster_path),
                "kind": "movie", "fetched_at": r.last_fetched_at,
            })
    if kind in ("tv", "both"):
        for r in db.query(TmdbTvCache).order_by(TmdbTvCache.last_fetched_at.desc(), TmdbTvCache.id.asc()).limit(limit).all():
            results.append({
                "id": r.id, "title": r.name, "original_title": r.original_name,
                "release_date": None, "first_air_date": r.first_air_date,
                "popularity": r.popularity, "vote_average": r.vote_average,
                "poster_url": TmdbClient.poster_url(r.poster_path),
                "kind": "tv", "fetched_at": r.last_fetched_at,
            })
    results.sort(key=lambda x: x["fetched_at"] or datetime.min, reverse=True)
    return results[:limit]


# ── 외부 소스 (KOBIS / KMDB) ──────────────────────────────────────────────────

def get_external_source_stats(db, source_type: str) -> dict:
    """KOBIS 또는 KMDB 통계: 로컬 캐시 테이블 건수 + sync_log 집계."""
    from api.programming.metadata.models import TmdbSyncLog, TmdbSyncSource

    kobis_sources = [TmdbSyncSource.kobis_daily, TmdbSyncSource.kobis_backfill]
    if source_type == "kobis":
        from api.programming.metadata.models.kobis_cache import KobisMovieCache
        total = db.query(KobisMovieCache).count()
        sync_sources = kobis_sources
        last_log = (
            db.query(TmdbSyncLog)
            .filter(TmdbSyncLog.source.in_(sync_sources))
            .order_by(TmdbSyncLog.started_at.desc())
            .first()
        )
        cutoff_7d = datetime.utcnow() - timedelta(days=8)  # KST 경계 보호
        recent_logs = (
            db.query(TmdbSyncLog)
            .filter(TmdbSyncLog.source.in_(sync_sources), TmdbSyncLog.started_at >= cutoff_7d)
            .all()
        )
        day_map: dict = defaultdict(lambda: {"count": 0, "errors": 0})
        for log in recent_logs:
            day_str = _kst_day(log.started_at)
            if day_str is None:
                continue
            day_map[day_str]["count"] += (log.cache_inserted or 0) + (log.cache_updated or 0)
            day_map[day_str]["errors"] += log.errors or 0
        last_7d = [{"date": d, "count": day_map[d]["count"], "errors": day_map[d]["errors"]} for d in _last_7_kst_dates()]
        return {
            "total_synced": total,
            "last_run_at": last_log.started_at if last_log else None,
            "last_run_status": last_log.status.value if last_log else None,
            "last_7d_daily": last_7d,
        }

    # KMDB: kmdb_movie_cache 건수 + external_sync_log 기준
    from api.programming.metadata.models.kmdb_cache import KmdbMovieCache
    kmdb_sources = [TmdbSyncSource.kmdb_daily, TmdbSyncSource.kmdb_backfill]
    total_cache = db.query(KmdbMovieCache).count()
    last_log = (
        db.query(TmdbSyncLog)
        .filter(TmdbSyncLog.source.in_(kmdb_sources))
        .order_by(TmdbSyncLog.started_at.desc())
        .first()
    )
    cutoff_7d = datetime.utcnow() - timedelta(days=8)  # KST 경계 보호
    recent_logs = (
        db.query(TmdbSyncLog)
        .filter(TmdbSyncLog.source.in_(kmdb_sources), TmdbSyncLog.started_at >= cutoff_7d)
        .all()
    )
    day_map: dict = defaultdict(lambda: {"count": 0, "errors": 0})
    for log in recent_logs:
        day_str = _kst_day(log.started_at)
        if day_str is None:
            continue
        day_map[day_str]["count"] += (log.cache_inserted or 0) + (log.cache_updated or 0)
        day_map[day_str]["errors"] += log.errors or 0
    last_7d = [{"date": d, "count": day_map[d]["count"], "errors": day_map[d]["errors"]} for d in _last_7_kst_dates()]
    return {
        "total_synced": total_cache,
        "last_run_at": last_log.started_at if last_log else None,
        "last_run_status": last_log.status.value if last_log else None,
        "last_7d_daily": last_7d,
    }


def list_external_source_sync_log(db, source_type: str, status: str | None, page: int, size: int):
    """KOBIS / KMDB sync 이력."""
    from api.programming.metadata.models import TmdbSyncLog, TmdbSyncSource

    if source_type == "kobis":
        sync_sources = [TmdbSyncSource.kobis_daily, TmdbSyncSource.kobis_backfill]
    elif source_type == "kmdb":
        sync_sources = [TmdbSyncSource.kmdb_daily, TmdbSyncSource.kmdb_backfill]
    else:
        return [], 0

    q = db.query(TmdbSyncLog).filter(TmdbSyncLog.source.in_(sync_sources))
    if status:
        q = q.filter(TmdbSyncLog.status == status)

    total = q.count()
    items = q.order_by(TmdbSyncLog.started_at.desc()).offset((page - 1) * size).limit(size).all()
    return items, total


def search_kmdb_cache(db, title: str | None, year: int | None, page: int, size: int):
    """kmdb_movie_cache 검색."""
    from api.programming.metadata.models.kmdb_cache import KmdbMovieCache

    q = db.query(KmdbMovieCache)
    if title:
        q = q.filter(KmdbMovieCache.title.ilike(f"%{title}%"))
    if year:
        q = q.filter(KmdbMovieCache.prod_year == year)
    total = q.count()
    items = q.order_by(KmdbMovieCache.last_fetched_at.desc()).offset((page - 1) * size).limit(size).all()
    return items, total


def _apply_poster_filter(q, poster_col, has_poster: bool | None):
    """has_poster=True → poster 있음, False → 없음, None → 필터 없음."""
    if has_poster is True:
        return q.filter(poster_col.isnot(None), poster_col != "")
    if has_poster is False:
        return q.filter(or_(poster_col.is_(None), poster_col == ""))
    return q


def search_tmdb_cache(
    db, title: str | None, kind: str, page: int, size: int,
    has_poster: bool | None = None, sort: str = "popularity",
):
    """tmdb_movie_cache / tmdb_tv_cache 단일 종류 검색.

    sort: "popularity"(기본, 인기순 DESC NULLS LAST) | "recent"(최근 fetch 순).
    has_poster: True 포스터 있음만 / False 없음만 / None 전체.
    기본 정렬을 인기순으로 둬, 포스터 없는 비인기 롱테일이 상단을 점유하지 않게 한다.
    """
    from api.programming.metadata.models import TmdbMovieCache, TmdbTvCache
    from api.programming.metadata.tmdb_client import TmdbClient

    if kind == "tv":
        Model, name_col = TmdbTvCache, TmdbTvCache.name
    else:
        Model, name_col = TmdbMovieCache, TmdbMovieCache.title

    q = db.query(Model)
    if title:
        q = q.filter(name_col.ilike(f"%{title}%"))
    q = _apply_poster_filter(q, Model.poster_path, has_poster)

    total = q.count()

    # id를 최종 tiebreaker로 둬, 동점·NULL·daily sync 값 변동에도 순서를 결정적으로 고정.
    if sort == "recent":
        order = (Model.last_fetched_at.desc(), Model.id.asc())
    else:
        order = (Model.popularity.desc().nullslast(), Model.id.asc())
    rows = q.order_by(*order).offset((page - 1) * size).limit(size).all()

    if kind == "tv":
        items = [{
            "id": r.id, "title": r.name, "original_title": r.original_name,
            "release_date": None, "first_air_date": r.first_air_date,
            "popularity": r.popularity, "vote_average": r.vote_average,
            "poster_url": TmdbClient.poster_url(r.poster_path),
            "kind": "tv", "fetched_at": r.last_fetched_at,
        } for r in rows]
    else:
        items = [{
            "id": r.id, "title": r.title, "original_title": r.original_title,
            "release_date": r.release_date, "first_air_date": None,
            "popularity": r.popularity, "vote_average": r.vote_average,
            "poster_url": TmdbClient.poster_url(r.poster_path),
            "kind": "movie", "fetched_at": r.last_fetched_at,
        } for r in rows]
    return items, total


def search_kobis_cache(db, title: str | None, year: int | None, page: int, size: int):
    """kobis_movie_cache 검색."""
    from api.programming.metadata.models.kobis_cache import KobisMovieCache

    q = db.query(KobisMovieCache)
    if title:
        q = q.filter(KobisMovieCache.title.ilike(f"%{title}%"))
    if year:
        q = q.filter(KobisMovieCache.prdt_year == year)
    total = q.count()
    items = q.order_by(KobisMovieCache.last_fetched_at.desc()).offset((page - 1) * size).limit(size).all()
    return items, total


def search_external_sources(db, source_type: str, title: str | None, year: int | None, page: int, size: int):
    """external_meta_sources에서 소스별 검색."""
    from api.programming.metadata.models import ExternalMetaSource, ExternalSourceType

    ext_type = ExternalSourceType(source_type)
    q = db.query(ExternalMetaSource).filter(ExternalMetaSource.source_type == ext_type)

    if title:
        q = q.filter(ExternalMetaSource.title_on_source.ilike(f"%{title}%"))

    total = q.count()
    items = q.order_by(ExternalMetaSource.matched_at.desc()).offset((page - 1) * size).limit(size).all()
    return items, total
