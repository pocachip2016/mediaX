"""
KMDB 캐시 Celery 태스크

태스크 목록:
  - backfill_kmdb            : 연도별 슬라이싱 백필 (idempotent)
  - kmdb_quota_backfill_tick : quota-aware Beat 트리거 (Step 5)

헬퍼:
  - _upsert_kmdb_movie       : KMDB Result dict → kmdb_movie_cache upsert
"""

import logging
import uuid
from datetime import datetime
from typing import Literal

from celery import shared_task

from shared.database import SessionLocal

logger = logging.getLogger(__name__)


# ── upsert 헬퍼 ────────────────────────────────────────────────────────────────

def _upsert_kmdb_movie(db, raw: dict) -> Literal["inserted", "updated", "unchanged"]:
    """KMDB Result 딕셔너리 → kmdb_movie_cache upsert.

    변경 감지 기준: title / poster_url / synopsis 중 하나라도 달라지면 'updated'.
    last_fetched_at 은 항상 갱신.
    """
    from api.programming.metadata.models.kmdb_cache import KmdbMovieCache

    docid = raw.get("DOCID") or raw.get("docid")
    if not docid:
        return "unchanged"

    title = (raw.get("title") or "").strip()
    title_eng = (raw.get("titleEng") or "").strip() or None
    title_org = (raw.get("titleOrg") or "").strip() or None

    prod_year_raw = raw.get("prodYear") or raw.get("prod_year") or ""
    try:
        prod_year = int(str(prod_year_raw)[:4]) if prod_year_raw else None
    except (ValueError, TypeError):
        prod_year = None

    nation = (raw.get("nation") or "").strip() or None
    genre = (raw.get("genre") or "").strip() or None

    runtime_raw = raw.get("runtime") or raw.get("runtime") or ""
    try:
        runtime = int(runtime_raw) if runtime_raw else None
    except (ValueError, TypeError):
        runtime = None

    # 포스터: posters.poster[] 목록 중 첫 번째 포스터 URL
    poster_url = None
    posters = raw.get("posters") or {}
    poster_list = posters.get("poster") if isinstance(posters, dict) else []
    if poster_list and isinstance(poster_list, list):
        poster_url = poster_list[0].get("posters") or poster_list[0].get("url") or None

    # 시놉시스
    synopsis = None
    plots = raw.get("plots") or {}
    plot_list = plots.get("plot") if isinstance(plots, dict) else []
    if plot_list and isinstance(plot_list, list):
        synopsis = plot_list[0].get("plotText") or None

    # directors / actors — 중첩 구조 그대로 저장
    directors_raw = raw.get("directors") or {}
    directors = directors_raw.get("director") if isinstance(directors_raw, dict) else []

    actors_raw = raw.get("actors") or {}
    actors = actors_raw.get("actor") if isinstance(actors_raw, dict) else []

    existing = db.get(KmdbMovieCache, docid)

    if existing is None:
        db.add(KmdbMovieCache(
            docid=docid,
            title=title or docid,
            title_eng=title_eng,
            title_org=title_org,
            prod_year=prod_year,
            nation=nation,
            genre=genre,
            runtime=runtime,
            poster_url=poster_url,
            synopsis=synopsis,
            directors=directors,
            actors=actors,
            raw_json=raw,
        ))
        return "inserted"

    existing.last_fetched_at = datetime.utcnow()

    changed = (
        existing.title != (title or docid)
        or existing.poster_url != poster_url
        or existing.synopsis != synopsis
    )
    if changed:
        existing.title = title or docid
        existing.title_eng = title_eng
        existing.title_org = title_org
        existing.prod_year = prod_year
        existing.nation = nation
        existing.genre = genre
        existing.runtime = runtime
        existing.poster_url = poster_url
        existing.synopsis = synopsis
        existing.directors = directors
        existing.actors = actors
        existing.raw_json = raw
        return "updated"

    return "unchanged"


# ── Celery 태스크 ────────────────────────────────────────────────────────────

_BATCH_COMMIT = 100   # N건마다 commit


@shared_task(
    name="workers.tasks.kmdb_cache.backfill_kmdb",
    bind=True,
    max_retries=0,      # quota 초과 등 실패 시 재시도 안 함 — 다음 날 Beat가 재실행
)
def backfill_kmdb(self, year: int):
    """1개 연도의 KMDB 영화를 페이지네이션으로 캐시에 적재 (idempotent).

    KmdbDailyLimitExceeded 발생 시 graceful 종료 (태스크 실패 아님).
    """
    from api.meta_core.clients.kmdb_client import KmdbClient, KmdbDailyLimitExceeded
    from api.programming.metadata.models.tmdb_cache import (
        TmdbSyncLog, TmdbSyncSource, TmdbSyncStatus,
    )
    from api.programming.metadata.models.external import ExternalSourceType
    from shared.config import settings

    db = SessionLocal()
    run_id = str(uuid.uuid4())
    log_row = TmdbSyncLog(
        run_id=run_id,
        source=TmdbSyncSource.kmdb_backfill,
        external_source=ExternalSourceType.kmdb,
        target_year=year,
        status=TmdbSyncStatus.running,
    )
    db.add(log_row)
    db.flush()

    client = KmdbClient(api_key=settings.KMDB_API_KEY)
    inserted = updated = unchanged = errors = 0
    start = 0
    list_count = 100
    quota_hit = False

    try:
        while True:
            try:
                items, total = client.search_year(year, start=start, list_count=list_count)
            except KmdbDailyLimitExceeded:
                logger.warning("[kmdb-backfill] year=%d quota 초과 — 중단 (start=%d)", year, start)
                quota_hit = True
                break

            if not items:
                break

            for raw in items:
                try:
                    outcome = _upsert_kmdb_movie(db, raw)
                    if outcome == "inserted":
                        inserted += 1
                    elif outcome == "updated":
                        updated += 1
                    else:
                        unchanged += 1
                except Exception as exc:
                    logger.warning("[kmdb-backfill] upsert 실패: %s", exc)
                    errors += 1

            start += list_count
            if start % _BATCH_COMMIT == 0:
                db.commit()

            if start >= total:
                break

        db.commit()
        log_row.status = TmdbSyncStatus.completed if not quota_hit else TmdbSyncStatus.failed
    except Exception as exc:
        logger.error("[kmdb-backfill] year=%d 실패: %s", year, exc)
        db.rollback()
        log_row.status = TmdbSyncStatus.failed
        errors += 1

    log_row.finished_at = datetime.utcnow()
    log_row.items_inserted = inserted
    log_row.items_updated = updated
    log_row.items_unchanged = unchanged
    log_row.errors = errors
    db.commit()
    db.close()

    summary = {
        "year": year,
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "errors": errors,
        "quota_hit": quota_hit,
    }
    logger.info("[kmdb-backfill] year=%d 완료 — %s", year, summary)
    return summary


_QUOTA_THRESHOLD = 200   # 잔여 quota 가 이 값 미만이면 백필 스킵
_BACKFILL_START_YEAR = 1990


@shared_task(name="workers.tasks.kmdb_cache.kmdb_quota_backfill_tick")
def kmdb_quota_backfill_tick():
    """매일 06:00 KST Beat — quota 잔여 확인 후 미백필 연도 1개 비동기 트리거.

    잔여 quota < 200 이면 skip.
    """
    from datetime import date
    from api.programming.metadata.models.tmdb_cache import TmdbSyncSource
    from shared.quota_manager import QuotaManager

    quota = QuotaManager()
    remaining = quota.daily_remaining("kmdb", 500)
    if remaining < _QUOTA_THRESHOLD:
        logger.info("[kmdb-tick] quota 잔여 %d < %d — 백필 스킵", remaining, _QUOTA_THRESHOLD)
        return {"skipped": True, "remaining": remaining}

    # 미백필 연도 탐색 — external_sync_log 에서 kmdb_backfill completed 연도 조회
    db = SessionLocal()
    try:
        from sqlalchemy import text
        rows = db.execute(
            text("""
                SELECT DISTINCT target_year FROM external_sync_log
                WHERE source = :src AND status = 'completed' AND target_year IS NOT NULL
            """),
            {"src": TmdbSyncSource.kmdb_backfill.value},
        ).fetchall()
        done_years = {r[0] for r in rows}
    finally:
        db.close()

    current_year = date.today().year
    target_year = None
    for y in range(_BACKFILL_START_YEAR, current_year + 1):
        if y not in done_years:
            target_year = y
            break

    if target_year is None:
        logger.info("[kmdb-tick] 모든 연도(%d~%d) 백필 완료", _BACKFILL_START_YEAR, current_year)
        return {"skipped": True, "reason": "all_done"}

    logger.info("[kmdb-tick] quota=%d → year=%d 백필 트리거", remaining, target_year)
    backfill_kmdb.delay(year=target_year)
    return {"triggered_year": target_year, "remaining": remaining}
