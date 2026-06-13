"""
TMDB 캐시 Celery 태스크

태스크 목록:
  - backfill_movies                      : 연도별 슬라이싱 영화 백필 (1회성, idempotent)
  - backfill_tv                          : 연도별 슬라이싱 TV 백필
  - daily_changes                        : 일일 변경 영화/TV upsert
  - daily_new_releases                   : 어제 신규 개봉/방영 콘텐츠 upsert
  - sync_tmdb_poster_to_content_images   : TMDB poster/backdrop → content_images (07:50 KST Beat)
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

    new_overview = item.get("overview") or ""
    new_release = item.get("release_date") or ""

    # 변경 감지: popularity/vote_count 차이 또는 overview/release_date 보강
    changed = (
        existing.popularity != item.get("popularity")
        or existing.vote_count != item.get("vote_count")
        or existing.poster_path != item.get("poster_path")
        or (new_overview and not existing.overview)
        or (new_release and not existing.release_date)
    )
    existing.last_fetched_at = datetime.utcnow()
    if changed:
        existing.popularity = item.get("popularity")
        existing.vote_average = item.get("vote_average")
        existing.vote_count = item.get("vote_count")
        existing.poster_path = item.get("poster_path")
        existing.backdrop_path = item.get("backdrop_path")
        existing.raw_json = item
        if new_overview and not existing.overview:
            existing.overview = new_overview
        if new_release and not existing.release_date:
            try:
                existing.release_date = date_type.fromisoformat(new_release)
            except ValueError:
                pass
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

    new_overview = item.get("overview") or ""
    new_first_air = item.get("first_air_date") or ""

    changed = (
        existing.popularity != item.get("popularity")
        or existing.vote_count != item.get("vote_count")
        or existing.number_of_episodes != item.get("number_of_episodes")
        or (new_overview and not existing.overview)
        or (new_first_air and not existing.first_air_date)
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
        if new_overview and not existing.overview:
            existing.overview = new_overview
        if new_first_air and not existing.first_air_date:
            existing.first_air_date = _parse_date(new_first_air)
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
    from api.programming.metadata.models import TmdbSyncLog, TmdbSyncSource, TmdbSyncStatus, ExternalSourceType

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
        external_source=ExternalSourceType.tmdb,
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
            if kind == "movie":
                detail = await client.detail_movie(tmdb_id)
                if not detail.get("overview"):
                    detail_en = await client.detail_movie(tmdb_id, language="en-US")
                    detail["overview"] = detail_en.get("overview") or ""
            else:
                detail = await client.detail_tv(tmdb_id)
                if not detail.get("overview"):
                    detail_en = await client.detail_tv(tmdb_id, language="en-US")
                    detail["overview"] = detail_en.get("overview") or ""
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
    from api.programming.metadata.models import TmdbSyncLog, TmdbSyncSource, TmdbSyncStatus, ExternalSourceType

    totals = {"movie": {}, "tv": {}}
    async with TmdbClient(api_key=api_key) as client:
        for kind in ("movie", "tv"):
            source = TmdbSyncSource.changes_movie if kind == "movie" else TmdbSyncSource.changes_tv
            log = TmdbSyncLog(
                run_id=str(uuid.uuid4()),
                source=source,
                external_source=ExternalSourceType.tmdb,
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

    from api.programming.metadata.models import TmdbSyncLog, TmdbSyncSource, TmdbSyncStatus, ExternalSourceType

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
                        external_source=ExternalSourceType.tmdb,
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


# ── Quota-aware 역순 백필 Beat tick ───────────────────────────────────────────

_TMDB_DAILY_LIMIT = 40_000
_TMDB_QUOTA_THRESHOLD = 2_000   # 잔여 < 2000이면 스킵 (연도 1개 ≈ 최대 1500 calls)
# movie/tv 백필 하한 분리: TV 방송은 1950년 이전 콘텐츠가 사실상 없음 → 빈 run 회피
_TMDB_MOVIE_BACKFILL_START_YEAR = 1900
_TMDB_TV_BACKFILL_START_YEAR = 1950


def _next_backfill_year(done_years: set[int], start_year: int, current_year: int) -> int | None:
    """current_year부터 start_year까지 역순으로 첫 미완료 연도 반환 (없으면 None)."""
    for y in range(current_year, start_year - 1, -1):
        if y not in done_years:
            return y
    return None


@celery_app.task(name="workers.tasks.tmdb_cache.tmdb_quota_backfill_tick")
def tmdb_quota_backfill_tick() -> dict:
    """매일 08:30 KST Beat — movie/tv 각각 최신 연도부터 역순으로 미백필 연도 1개 트리거.

    - TmdbSyncLog(completed) 기준으로 종류별 중복 연도 스킵 (movie/tv 독립 진행)
    - movie 하한 1900, tv 하한 1950 (TV는 1950년 이전 콘텐츠가 사실상 없음)
    - QuotaManager("tmdb") 잔여 < 2000이면 해당 일 스킵
    """
    from shared.quota_manager import QuotaManager
    from api.programming.metadata.models import TmdbSyncLog, TmdbSyncSource, TmdbSyncStatus

    api_key = getattr(settings, "TMDB_API_KEY", "")
    if not api_key:
        logger.info("[tmdb-tick] TMDB_API_KEY 없음 — 스킵")
        return {"skipped": True, "reason": "no_api_key"}

    quota = QuotaManager()
    remaining = quota.daily_remaining("tmdb", _TMDB_DAILY_LIMIT)
    if remaining < _TMDB_QUOTA_THRESHOLD:
        logger.info("[tmdb-tick] quota 잔여 %d < %d — 백필 스킵", remaining, _TMDB_QUOTA_THRESHOLD)
        return {"skipped": True, "remaining": remaining}

    db = SessionLocal()
    try:
        movie_done = {
            r.target_year for r in
            db.query(TmdbSyncLog.target_year)
            .filter(
                TmdbSyncLog.source == TmdbSyncSource.backfill_movie_year,
                TmdbSyncLog.status == TmdbSyncStatus.completed,
                TmdbSyncLog.target_year.isnot(None),
            ).all()
        }
        tv_done = {
            r.target_year for r in
            db.query(TmdbSyncLog.target_year)
            .filter(
                TmdbSyncLog.source == TmdbSyncSource.backfill_tv_year,
                TmdbSyncLog.status == TmdbSyncStatus.completed,
                TmdbSyncLog.target_year.isnot(None),
            ).all()
        }
    finally:
        db.close()

    current_year = date.today().year
    movie_year = _next_backfill_year(movie_done, _TMDB_MOVIE_BACKFILL_START_YEAR, current_year)
    tv_year = _next_backfill_year(tv_done, _TMDB_TV_BACKFILL_START_YEAR, current_year)

    if movie_year is None and tv_year is None:
        logger.info(
            "[tmdb-tick] 모든 연도 백필 완료 (movie %d~%d, tv %d~%d)",
            _TMDB_MOVIE_BACKFILL_START_YEAR, current_year,
            _TMDB_TV_BACKFILL_START_YEAR, current_year,
        )
        return {"skipped": True, "reason": "all_done"}

    triggered: dict = {"remaining": remaining}
    if movie_year is not None:
        backfill_movies.delay(year_from=movie_year, year_to=movie_year)
        triggered["movie_year"] = movie_year
    if tv_year is not None:
        backfill_tv.delay(year_from=tv_year, year_to=tv_year)
        triggered["tv_year"] = tv_year

    logger.info(
        "[tmdb-tick] quota=%d → movie_year=%s tv_year=%s 백필 트리거",
        remaining, movie_year, tv_year,
    )
    return triggered


# ── TMDB 포스터 → ContentImage 동기화 ────────────────────────────────────────────

_TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"


@celery_app.task(name="workers.tasks.tmdb_cache.sync_tmdb_poster_to_content_images", max_retries=0)
def sync_tmdb_poster_to_content_images():
    """ExternalMetaSource(tmdb) raw_json.poster_path/backdrop_path → content_images 동기화 (idempotent).

    전제: external_meta_sources (source_type=tmdb) 에 content_id 매핑이 존재해야 함.
    Beat link-tmdb-to-contents (07:30) 이후 07:50 KST 에 실행.

    is_primary 규칙:
      - poster_path 첫 URL → is_primary=True (단, 해당 content 에 이미 is_primary poster 가 있으면 False)
      - backdrop_path → ImageType.banner, is_primary=False (항상)

    중복 기준: (content_id, image_type, url) 조합 — 동일하면 insert 스킵.
    """
    from api.programming.metadata.models import ContentImage, ImageType
    from api.programming.metadata.models.external import ExternalMetaSource, ExternalSourceType

    db = SessionLocal()
    posters_added = banners_added = contents_processed = errors = 0

    try:
        # content_id 매핑 (ExternalMetaSource, tmdb 소스)
        links = (
            db.query(ExternalMetaSource.content_id, ExternalMetaSource.external_id)
            .filter(
                ExternalMetaSource.source_type == ExternalSourceType.tmdb,
                ExternalMetaSource.content_id.isnot(None),
            )
            .all()
        )

        for content_id, tmdb_id in links:
            raw_json = (
                db.query(ExternalMetaSource.raw_json)
                .filter(
                    ExternalMetaSource.content_id == content_id,
                    ExternalMetaSource.source_type == ExternalSourceType.tmdb,
                )
                .scalar() or {}
            )
            if not raw_json:
                continue

            poster_path = raw_json.get("poster_path")
            backdrop_path = raw_json.get("backdrop_path")
            if not poster_path and not backdrop_path:
                continue

            try:
                # 기존 포스터/배너 URL 세트 (중복 체크용)
                existing_poster_urls: set[str] = {
                    row[0]
                    for row in db.query(ContentImage.url).filter(
                        ContentImage.content_id == content_id,
                        ContentImage.image_type == ImageType.poster,
                    ).all()
                }
                existing_banner_urls: set[str] = {
                    row[0]
                    for row in db.query(ContentImage.url).filter(
                        ContentImage.content_id == content_id,
                        ContentImage.image_type == ImageType.banner,
                    ).all()
                }
                # 기존 is_primary poster 존재 여부
                has_primary = db.query(ContentImage.id).filter(
                    ContentImage.content_id == content_id,
                    ContentImage.image_type == ImageType.poster,
                    ContentImage.is_primary == True,  # noqa: E712
                ).first() is not None

                # poster_path 처리
                if poster_path:
                    poster_url = f"{_TMDB_IMAGE_BASE}/w500{poster_path}"
                    if poster_url not in existing_poster_urls:
                        make_primary = not has_primary
                        db.add(ContentImage(
                            content_id=content_id,
                            image_type=ImageType.poster,
                            url=poster_url,
                            source="tmdb",
                            is_primary=make_primary,
                        ))
                        existing_poster_urls.add(poster_url)
                        if make_primary:
                            has_primary = True
                        posters_added += 1

                # backdrop_path 처리 (banner 타입)
                if backdrop_path:
                    banner_url = f"{_TMDB_IMAGE_BASE}/w1280{backdrop_path}"
                    if banner_url not in existing_banner_urls:
                        db.add(ContentImage(
                            content_id=content_id,
                            image_type=ImageType.banner,
                            url=banner_url,
                            source="tmdb",
                            is_primary=False,
                        ))
                        existing_banner_urls.add(banner_url)
                        banners_added += 1

                contents_processed += 1
            except Exception as exc:
                logger.warning(f"[tmdb-poster-sync] content_id={content_id} 처리 실패: {exc}")
                errors += 1

        db.commit()
        logger.info(f"[tmdb-poster-sync] posters={posters_added} banners={banners_added} contents={contents_processed} errors={errors}")
        return {
            "posters_added": posters_added,
            "banners_added": banners_added,
            "contents_processed": contents_processed,
            "errors": errors,
        }
    except Exception as exc:
        logger.error(f"[tmdb-poster-sync] 실패: {exc}")
        return {"error": str(exc)}
    finally:
        db.close()


# ── overview 빈 행 주기 보강 Beat ─────────────────────────────────────────────

@celery_app.task(name="workers.tasks.tmdb_cache.backfill_tmdb_overview_tick")
def backfill_tmdb_overview_tick(
    limit: int = 1000,
    skip_recent_days: int = 7,
    batch: int = 200,
) -> dict:
    """매일 09:10 KST Beat — overview 빈 tmdb_movie_cache 행 ko→en 폴백 보강.

    - QuotaManager("tmdb") 잔여 < threshold → skip
    - last_fetched_at 이 skip_recent_days 이내인 행 제외 (중복 억제)
    - 처리 순서: vote_count DESC (인기 콘텐츠 우선)
    """
    from shared.quota_manager import QuotaManager
    from api.programming.metadata.models.tmdb_cache import TmdbMovieCache
    from datetime import timezone

    api_key = getattr(settings, "TMDB_API_KEY", "")
    if not api_key:
        logger.info("[overview-tick] TMDB_API_KEY 없음 — 스킵")
        return {"skipped": True, "reason": "no_api_key"}

    quota = QuotaManager()
    remaining = quota.daily_remaining("tmdb", _TMDB_DAILY_LIMIT)
    if remaining < _TMDB_QUOTA_THRESHOLD:
        logger.info("[overview-tick] quota 잔여 %d < %d — 스킵", remaining, _TMDB_QUOTA_THRESHOLD)
        return {"skipped": True, "remaining": remaining}

    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=skip_recent_days)
        from sqlalchemy import or_
        rows = (
            db.query(TmdbMovieCache.id)
            .filter(
                or_(
                    TmdbMovieCache.overview.is_(None),
                    TmdbMovieCache.overview == "",
                ),
                or_(
                    TmdbMovieCache.last_fetched_at.is_(None),
                    TmdbMovieCache.last_fetched_at < cutoff,
                ),
            )
            .order_by(TmdbMovieCache.vote_count.desc().nullslast())
            .limit(limit)
            .all()
        )
        tmdb_ids = [r.id for r in rows]
    finally:
        db.close()

    if not tmdb_ids:
        logger.info("[overview-tick] 보강 대상 없음")
        return {"skipped": True, "reason": "no_targets"}

    logger.info("[overview-tick] 대상 %d건 처리 시작 (remaining quota=%d)", len(tmdb_ids), remaining)

    updated = unchanged = errors = 0

    async def _run():
        nonlocal updated, unchanged, errors
        db2 = SessionLocal()
        try:
            async with TmdbClient(api_key=api_key) as client:
                for i in range(0, len(tmdb_ids), batch):
                    batch_ids = tmdb_ids[i : i + batch]
                    for tmdb_id in batch_ids:
                        try:
                            detail = await client.detail_movie(tmdb_id)
                            if not detail.get("overview"):
                                detail_en = await client.detail_movie(tmdb_id, language="en-US")
                                detail["overview"] = detail_en.get("overview") or ""
                            action = _upsert_movie(db2, detail)
                            if action == "updated":
                                updated += 1
                            else:
                                unchanged += 1
                        except Exception as exc:
                            logger.warning("[overview-tick] id=%d 실패: %s", tmdb_id, exc)
                            errors += 1
                    db2.commit()
        finally:
            db2.close()

    asyncio.run(_run())
    logger.info("[overview-tick] 완료 updated=%d unchanged=%d errors=%d", updated, unchanged, errors)
    return {"total": len(tmdb_ids), "updated": updated, "unchanged": unchanged, "errors": errors}
