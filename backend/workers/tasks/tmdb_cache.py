"""
TMDB 캐시 Celery 태스크

태스크 목록:
  - backfill_movies      : 연도별 슬라이싱 영화 백필 (1회성, idempotent)
  - backfill_tv          : 연도별 슬라이싱 TV 백필
  - daily_changes        : 일일 변경 영화/TV upsert
  - daily_new_releases   : 어제 신규 개봉/방영 콘텐츠 upsert
"""

import asyncio
import logging
import uuid
from datetime import date, datetime, timedelta
from typing import Literal

import httpx

from workers.celery_app import celery_app
from shared.database import SessionLocal
from shared.config import settings
from api.programming.metadata.tmdb_client import TmdbClient

logger = logging.getLogger(__name__)

_BATCH_COMMIT = 50   # N건마다 commit (long transaction 방지)
_MAX_PAGES = 500     # TMDB discover 페이지 상한


# ── 공용 upsert 헬퍼 ──────────────────────────────────────────────────────────

def _upsert_movie(db, item: dict) -> Literal["inserted", "updated", "unchanged"]:
    """tmdb_movie_cache upsert — PK(id) 기준, 변경 감지 시만 updated."""
    from api.programming.metadata.models import TmdbMovieCache
    from datetime import date as date_type

    tmdb_id = item.get("id")
    if not tmdb_id:
        return "unchanged"

    existing = db.get(TmdbMovieCache, tmdb_id)

    release_raw = item.get("release_date") or ""
    release = None
    if release_raw:
        try:
            release = date_type.fromisoformat(release_raw)
        except ValueError:
            pass

    if existing is None:
        db.add(TmdbMovieCache(
            id=tmdb_id,
            title=item.get("title") or item.get("original_title") or "",
            original_title=item.get("original_title"),
            original_language=item.get("original_language"),
            release_date=release,
            runtime=item.get("runtime"),
            popularity=item.get("popularity"),
            vote_average=item.get("vote_average"),
            vote_count=item.get("vote_count"),
            adult=item.get("adult", False),
            poster_path=item.get("poster_path"),
            backdrop_path=item.get("backdrop_path"),
            overview=item.get("overview"),
            genre_ids=item.get("genre_ids"),
            raw_json=item,
        ))
        return "inserted"

    # 변경 감지: popularity 또는 vote_count 차이가 있으면 갱신
    changed = (
        existing.popularity != item.get("popularity")
        or existing.vote_count != item.get("vote_count")
        or existing.poster_path != item.get("poster_path")
    )
    existing.last_fetched_at = datetime.utcnow()
    if changed:
        existing.popularity = item.get("popularity")
        existing.vote_average = item.get("vote_average")
        existing.vote_count = item.get("vote_count")
        existing.poster_path = item.get("poster_path")
        existing.backdrop_path = item.get("backdrop_path")
        existing.raw_json = item
        return "updated"

    return "unchanged"


def _upsert_tv(db, item: dict) -> Literal["inserted", "updated", "unchanged"]:
    """tmdb_tv_cache upsert"""
    from api.programming.metadata.models import TmdbTvCache
    from datetime import date as date_type

    tmdb_id = item.get("id")
    if not tmdb_id:
        return "unchanged"

    existing = db.get(TmdbTvCache, tmdb_id)

    def _parse_date(val):
        if not val:
            return None
        try:
            return date_type.fromisoformat(val)
        except ValueError:
            return None

    if existing is None:
        db.add(TmdbTvCache(
            id=tmdb_id,
            name=item.get("name") or item.get("original_name") or "",
            original_name=item.get("original_name"),
            original_language=item.get("original_language"),
            first_air_date=_parse_date(item.get("first_air_date")),
            last_air_date=_parse_date(item.get("last_air_date")),
            number_of_seasons=item.get("number_of_seasons"),
            number_of_episodes=item.get("number_of_episodes"),
            status=item.get("status"),
            popularity=item.get("popularity"),
            vote_average=item.get("vote_average"),
            vote_count=item.get("vote_count"),
            poster_path=item.get("poster_path"),
            backdrop_path=item.get("backdrop_path"),
            overview=item.get("overview"),
            genre_ids=item.get("genre_ids"),
            raw_json=item,
        ))
        return "inserted"

    changed = (
        existing.popularity != item.get("popularity")
        or existing.vote_count != item.get("vote_count")
        or existing.number_of_episodes != item.get("number_of_episodes")
    )
    existing.last_fetched_at = datetime.utcnow()
    if changed:
        existing.popularity = item.get("popularity")
        existing.vote_average = item.get("vote_average")
        existing.vote_count = item.get("vote_count")
        existing.number_of_seasons = item.get("number_of_seasons")
        existing.number_of_episodes = item.get("number_of_episodes")
        existing.status = item.get("status")
        existing.poster_path = item.get("poster_path")
        existing.raw_json = item
        return "updated"

    return "unchanged"


# ── 연도 슬라이싱 내부 헬퍼 ──────────────────────────────────────────────────

async def _fetch_discover_pages(
    client,
    kind: Literal["movie", "tv"],
    db,
    log_id: int,
    date_gte: str,
    date_lte: str,
) -> dict:
    """discover API를 페이지 루프로 소진하여 upsert. TmdbSyncLog(log_id)를 갱신."""
    from api.programming.metadata.models import TmdbSyncLog

    inserted = updated = unchanged = errors = pages = fetched = 0
    page = 1

    while page <= _MAX_PAGES:
        try:
            if kind == "movie":
                resp = await client.discover_movies(
                    release_date_gte=date_gte, release_date_lte=date_lte, page=page
                )
            else:
                resp = await client.discover_tv(
                    first_air_date_gte=date_gte, first_air_date_lte=date_lte, page=page
                )
        except Exception as exc:
            logger.warning("[tmdb_cache] discover %s page=%d error: %s", kind, page, exc)
            errors += 1
            break

        results = resp.get("results", [])
        total_pages = min(resp.get("total_pages", 1), _MAX_PAGES)
        fetched += len(results)
        pages += 1

        for item in results:
            try:
                action = _upsert_movie(db, item) if kind == "movie" else _upsert_tv(db, item)
                if action == "inserted":
                    inserted += 1
                elif action == "updated":
                    updated += 1
                else:
                    unchanged += 1
            except Exception as exc:
                logger.warning("[tmdb_cache] upsert error id=%s: %s", item.get("id"), exc)
                errors += 1

        # 배치 commit
        if pages % (_BATCH_COMMIT // 20 or 1) == 0:
            db.commit()

        if page >= total_pages:
            break
        page += 1

    db.commit()

    # SyncLog 중간 갱신
    log = db.get(TmdbSyncLog, log_id)
    if log:
        log.pages_fetched += pages
        log.items_fetched += fetched
        log.items_inserted += inserted
        log.items_updated += updated
        log.items_unchanged += unchanged
        log.errors += errors
        db.commit()

    return {"inserted": inserted, "updated": updated, "unchanged": unchanged,
            "errors": errors, "pages": pages, "fetched": fetched}


async def _backfill_year(
    client, kind: Literal["movie", "tv"], year: int, db
) -> dict:
    """한 연도 백필 — 10k 한계 초과 시 상반기/하반기 재슬라이싱."""
    from api.programming.metadata.models import TmdbSyncLog, TmdbSyncSource, TmdbSyncStatus

    source = TmdbSyncSource.backfill_movie_year if kind == "movie" else TmdbSyncSource.backfill_tv_year

    # 이미 완료된 연도 스킵
    completed = (
        db.query(TmdbSyncLog)
        .filter(
            TmdbSyncLog.source == source,
            TmdbSyncLog.target_year == year,
            TmdbSyncLog.status == TmdbSyncStatus.completed,
        )
        .first()
    )
    if completed:
        logger.info("[tmdb_cache] %s year=%d 이미 완료 — 스킵", kind, year)
        return {"skipped": True, "year": year}

    log = TmdbSyncLog(
        run_id=str(uuid.uuid4()),
        source=source,
        target_year=year,
        status=TmdbSyncStatus.running,
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    totals = {"inserted": 0, "updated": 0, "unchanged": 0, "errors": 0, "pages": 0, "fetched": 0}

    try:
        # 1차: 전체 연도
        first_half = await _fetch_discover_pages(
            client, kind, db, log.id,
            date_gte=f"{year}-01-01", date_lte=f"{year}-06-30"
        )
        second_half = await _fetch_discover_pages(
            client, kind, db, log.id,
            date_gte=f"{year}-07-01", date_lte=f"{year}-12-31"
        )
        for k in totals:
            totals[k] = first_half.get(k, 0) + second_half.get(k, 0)

        log.status = TmdbSyncStatus.completed
        log.finished_at = datetime.utcnow()
        db.commit()

        logger.info(
            "[tmdb_cache] %s year=%d 완료 — inserted=%d updated=%d pages=%d",
            kind, year, totals["inserted"], totals["updated"], totals["pages"]
        )
    except Exception as exc:
        log.status = TmdbSyncStatus.failed
        log.error_sample = [str(exc)]
        log.finished_at = datetime.utcnow()
        db.commit()
        logger.error("[tmdb_cache] %s year=%d 실패: %s", kind, year, exc)

    return {**totals, "year": year}


# ── Celery 태스크 ─────────────────────────────────────────────────────────────

@celery_app.task(name="workers.tasks.tmdb_cache.backfill_movies")
def backfill_movies(
    year_from: int = 1900,
    year_to: int | None = None,
    dry_run: bool = False,
) -> dict:
    """연도별 슬라이싱 영화 전수 백필 (1회성, idempotent).

    dry_run=True 이면 DB 저장 없이 첫 페이지만 요청하여 호출 가능 여부만 검증.
    """
    api_key = getattr(settings, "TMDB_API_KEY", "")
    if not api_key:
        logger.warning("[tmdb_cache] TMDB_API_KEY 없음 — 스킵")
        return {"skipped": True, "reason": "no api key"}

    if year_to is None:
        year_to = date.today().year

    db = SessionLocal()
    grand_total = {"inserted": 0, "updated": 0, "unchanged": 0, "errors": 0, "years": 0}

    try:
        async def _run():
            async with TmdbClient(api_key=api_key) as client:
                if dry_run:
                    resp = await client.discover_movies(year=year_from, page=1)
                    return {"dry_run": True, "total_results": resp.get("total_results", 0),
                            "total_pages": resp.get("total_pages", 0)}

                for year in range(year_from, year_to + 1):
                    result = await _backfill_year(client, "movie", year, db)
                    if not result.get("skipped"):
                        for k in ("inserted", "updated", "unchanged", "errors"):
                            grand_total[k] += result.get(k, 0)
                        grand_total["years"] += 1

            return grand_total

        result = asyncio.run(_run())
        logger.info("[tmdb_cache] backfill_movies 완료: %s", result)
        return result
    except Exception as exc:
        logger.error("[tmdb_cache] backfill_movies 실패: %s", exc)
        return {"error": str(exc)}
    finally:
        db.close()


@celery_app.task(name="workers.tasks.tmdb_cache.backfill_tv")
def backfill_tv(
    year_from: int = 1950,
    year_to: int | None = None,
    dry_run: bool = False,
) -> dict:
    """연도별 슬라이싱 TV 전수 백필 (1회성, idempotent)."""
    api_key = getattr(settings, "TMDB_API_KEY", "")
    if not api_key:
        logger.warning("[tmdb_cache] TMDB_API_KEY 없음 — 스킵")
        return {"skipped": True, "reason": "no api key"}

    if year_to is None:
        year_to = date.today().year

    db = SessionLocal()
    grand_total = {"inserted": 0, "updated": 0, "unchanged": 0, "errors": 0, "years": 0}

    try:
        async def _run():
            async with TmdbClient(api_key=api_key) as client:
                if dry_run:
                    resp = await client.discover_tv(first_air_year=year_from, page=1)
                    return {"dry_run": True, "total_results": resp.get("total_results", 0),
                            "total_pages": resp.get("total_pages", 0)}

                for year in range(year_from, year_to + 1):
                    result = await _backfill_year(client, "tv", year, db)
                    if not result.get("skipped"):
                        for k in ("inserted", "updated", "unchanged", "errors"):
                            grand_total[k] += result.get(k, 0)
                        grand_total["years"] += 1

            return grand_total

        result = asyncio.run(_run())
        logger.info("[tmdb_cache] backfill_tv 완료: %s", result)
        return result
    except Exception as exc:
        logger.error("[tmdb_cache] backfill_tv 실패: %s", exc)
        return {"error": str(exc)}
    finally:
        db.close()


# ── Daily 증분 태스크 ─────────────────────────────────────────────────────────

async def _fetch_changed_details(client, kind: Literal["movie", "tv"], changed_ids: list[int], db) -> dict:
    """변경 ID 목록 → detail 조회 → upsert."""
    inserted = updated = unchanged = errors = 0
    for tmdb_id in changed_ids:
        try:
            detail = await client.detail_movie(tmdb_id) if kind == "movie" else await client.detail_tv(tmdb_id)
            action = _upsert_movie(db, detail) if kind == "movie" else _upsert_tv(db, detail)
            if action == "inserted":
                inserted += 1
            elif action == "updated":
                updated += 1
            else:
                unchanged += 1
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                # TMDB changes API includes deleted items — 404 is expected, skip silently
                logger.debug("[tmdb_cache] %s_id=%d not found (deleted) — skip", kind, tmdb_id)
            else:
                logger.warning("[tmdb_cache] detail fetch 실패 %s_id=%d: %s", kind, tmdb_id, exc)
                errors += 1
        except Exception as exc:
            logger.warning("[tmdb_cache] detail fetch 실패 %s_id=%d: %s", kind, tmdb_id, exc)
            errors += 1
        # 10건마다 commit
        if (inserted + updated + unchanged) % 10 == 0:
            db.commit()
    db.commit()
    return {"inserted": inserted, "updated": updated, "unchanged": unchanged, "errors": errors}


async def _run_daily_changes(api_key: str, target_date: str, db) -> dict:
    """changes API → detail → upsert for movie + tv."""
    from api.programming.metadata.models import TmdbSyncLog, TmdbSyncSource, TmdbSyncStatus

    totals = {"movie": {}, "tv": {}}
    async with TmdbClient(api_key=api_key) as client:
        for kind in ("movie", "tv"):
            source = TmdbSyncSource.changes_movie if kind == "movie" else TmdbSyncSource.changes_tv
            log = TmdbSyncLog(
                run_id=str(uuid.uuid4()),
                source=source,
                target_date=date.fromisoformat(target_date),
                status=TmdbSyncStatus.running,
            )
            db.add(log)
            db.commit()
            db.refresh(log)

            changed_ids = []
            page = 1
            try:
                while True:
                    resp = await client.changes(kind=kind, start_date=target_date,
                                                end_date=target_date, page=page)
                    for entry in resp.get("results", []):
                        if entry.get("id"):
                            changed_ids.append(entry["id"])
                    total_pages = resp.get("total_pages", 1)
                    if page >= total_pages:
                        break
                    page += 1

                log.items_fetched = len(changed_ids)
                log.pages_fetched = page

                result = await _fetch_changed_details(client, kind, changed_ids, db)
                log.items_inserted = result["inserted"]
                log.items_updated = result["updated"]
                log.items_unchanged = result["unchanged"]
                log.errors = result["errors"]
                if result["errors"] > 0:
                    log.error_sample = [f"{result['errors']} detail fetch failures"]
                log.status = TmdbSyncStatus.completed
                log.finished_at = datetime.utcnow()
                totals[kind] = result

            except Exception as exc:
                log.status = TmdbSyncStatus.failed
                log.error_sample = [str(exc)]
                log.finished_at = datetime.utcnow()
                logger.error("[tmdb_cache] daily_changes %s 실패: %s", kind, exc)

            db.commit()
    return totals


@celery_app.task(name="workers.tasks.tmdb_cache.daily_changes")
def daily_changes(target_date: str | None = None) -> dict:
    """어제 변경된 movie/tv를 TMDB changes API로 가져와 upsert.

    target_date=None 이면 어제(KST) 날짜 자동 사용.
    """
    api_key = getattr(settings, "TMDB_API_KEY", "")
    if not api_key:
        return {"skipped": True, "reason": "no api key"}

    if target_date is None:
        from zoneinfo import ZoneInfo
        yesterday = (datetime.now(ZoneInfo("Asia/Seoul")) - timedelta(days=1)).date()
        target_date = yesterday.isoformat()

    db = SessionLocal()
    try:
        result = asyncio.run(_run_daily_changes(api_key, target_date, db))
        logger.info("[tmdb_cache] daily_changes %s 완료: %s", target_date, result)
        return {"date": target_date, **result}
    except Exception as exc:
        logger.error("[tmdb_cache] daily_changes 실패: %s", exc)
        return {"error": str(exc)}
    finally:
        db.close()


@celery_app.task(name="workers.tasks.tmdb_cache.daily_new_releases")
def daily_new_releases(target_date: str | None = None) -> dict:
    """어제 첫 개봉/방영된 신작 — discover API로 수집."""
    api_key = getattr(settings, "TMDB_API_KEY", "")
    if not api_key:
        return {"skipped": True, "reason": "no api key"}

    if target_date is None:
        from zoneinfo import ZoneInfo
        yesterday = (datetime.now(ZoneInfo("Asia/Seoul")) - timedelta(days=1)).date()
        target_date = yesterday.isoformat()

    from api.programming.metadata.models import TmdbSyncLog, TmdbSyncSource, TmdbSyncStatus

    db = SessionLocal()
    totals = {}
    try:
        async def _run():
            async with TmdbClient(api_key=api_key) as client:
                for kind in ("movie", "tv"):
                    source = (TmdbSyncSource.discover_movie if kind == "movie"
                              else TmdbSyncSource.discover_tv)
                    log = TmdbSyncLog(
                        run_id=str(uuid.uuid4()),
                        source=source,
                        target_date=date.fromisoformat(target_date),
                        status=TmdbSyncStatus.running,
                    )
                    db.add(log)
                    db.commit()
                    db.refresh(log)

                    result = await _fetch_discover_pages(
                        client, kind, db, log.id,
                        date_gte=target_date, date_lte=target_date,
                    )
                    log.status = TmdbSyncStatus.completed
                    log.finished_at = datetime.utcnow()
                    db.commit()
                    totals[kind] = result

        asyncio.run(_run())
        logger.info("[tmdb_cache] daily_new_releases %s 완료: %s", target_date, totals)
        return {"date": target_date, **totals}
    except Exception as exc:
        logger.error("[tmdb_cache] daily_new_releases 실패: %s", exc)
        return {"error": str(exc)}
    finally:
        db.close()
