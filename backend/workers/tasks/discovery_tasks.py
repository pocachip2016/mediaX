"""
Phase C SEED 발굴 Celery 태스크

Beat 스케줄: ADR docs/dev/phase-c/beat-schedule.md §5 참조
  - discover_tmdb_daily:  04:30 KST
  - discover_kobis_daily: 05:00 KST
  - discover_kmdb_daily:  05:30 KST
  - discover_tmdb_weekly: 일요일 06:00 KST

API 키 미설정 시 DiscoverySource 내부에서 자동 skip — 태스크 실패 아님.
"""
from __future__ import annotations

import logging

from celery import shared_task, chord, group

from shared.database import SessionLocal
from shared.config import settings

logger = logging.getLogger(__name__)


def _run_source(source_class, api_key: str, mode: str, **kwargs) -> dict:
    """소스 1건 실행 + DB 반영. 태스크 공통 진입점."""
    db = SessionLocal()
    try:
        from api.meta_core.discovery.runner import run_discovery
        source = source_class(api_key=api_key)
        summary = run_discovery(db, source, mode, **kwargs)
        logger.info("[discovery] %s.%s 완료: %s", source_class.__name__, mode, summary)
        return summary
    except Exception as exc:
        logger.error("[discovery] %s.%s 실패: %s", source_class.__name__, mode, exc)
        raise
    finally:
        db.close()


@shared_task(
    name="workers.tasks.discovery_tasks.discover_tmdb",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def discover_tmdb(self, mode: str = "trending_day"):
    """TMDB 발굴 태스크.

    mode: trending_day | trending_week | upcoming | discover
    """
    try:
        from api.meta_core.discovery.tmdb_source import TmdbDiscoverySource
        return _run_source(TmdbDiscoverySource, settings.TMDB_API_KEY, mode)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(
    name="workers.tasks.discovery_tasks.discover_kobis",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def discover_kobis(self, mode: str = "box_office_daily"):
    """KOBIS 발굴 태스크.

    mode: upcoming | box_office_daily | box_office_weekly | new_release
    """
    try:
        from api.meta_core.discovery.kobis_source import KobisDiscoverySource
        return _run_source(KobisDiscoverySource, settings.KOBIS_API_KEY, mode)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(
    name="workers.tasks.discovery_tasks.discover_kmdb",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def discover_kmdb(self, mode: str = "new_release", days: int = 7):
    """KMDB 발굴 태스크 — SEED 발굴 + kmdb_movie_cache 동시 upsert + ExternalSyncLog 기록.

    mode: new_release | discover_drama | discover_movie
    """
    try:
        import time
        import uuid
        from datetime import datetime

        from api.meta_core.discovery.kmdb_source import KmdbDiscoverySource
        from api.meta_core.discovery.dedup import match_or_create_seed
        from api.programming.metadata.models.tmdb_cache import (
            TmdbSyncLog, TmdbSyncSource, TmdbSyncStatus,
        )
        from api.programming.metadata.models.external import ExternalSourceType
        from workers.tasks.kmdb_cache import _upsert_kmdb_movie

        db = SessionLocal()
        t0 = time.monotonic()
        run_id = str(uuid.uuid4())

        # ExternalSyncLog 시작 행
        log_row = TmdbSyncLog(
            run_id=run_id,
            source=TmdbSyncSource.kmdb_daily,
            external_source=ExternalSourceType.kmdb,
            status=TmdbSyncStatus.running,
        )
        db.add(log_row)
        db.flush()

        total = new_seeds = matched_existing = duplicates = alt_id_added = errors = 0
        inserted = updated = unchanged_cache = 0

        try:
            source = KmdbDiscoverySource(api_key=settings.KMDB_API_KEY, recent_days=days)
            results = list(source.discover(mode))
            total = len(results)

            for result in results:
                # kmdb_movie_cache upsert
                try:
                    outcome = _upsert_kmdb_movie(db, result.raw)
                    if outcome == "inserted":
                        inserted += 1
                    elif outcome == "updated":
                        updated += 1
                    else:
                        unchanged_cache += 1
                except Exception as exc:
                    logger.warning("[kmdb] cache upsert 실패 %s: %s", result.external_id, exc)
                    errors += 1

                # SEED 발굴 (기존 dedup 흐름)
                try:
                    _, action = match_or_create_seed(db, result)
                    if action == "created":
                        new_seeds += 1
                    elif action == "matched_existing":
                        matched_existing += 1
                    elif action == "duplicate":
                        duplicates += 1
                    elif action == "alt_id_added":
                        alt_id_added += 1
                except Exception as exc:
                    logger.warning("[kmdb] dedup 실패 %s: %s", result.external_id, exc)
                    errors += 1

            db.commit()

            log_row.status = TmdbSyncStatus.completed
        except Exception as exc:
            logger.error("[kmdb] discover_kmdb.%s 실패: %s", mode, exc)
            db.rollback()
            log_row.status = TmdbSyncStatus.failed
            errors += 1
            raise

        duration_ms = int((time.monotonic() - t0) * 1000)
        log_row.finished_at = datetime.utcnow()
        log_row.items_fetched = total
        log_row.items_inserted = inserted
        log_row.items_updated = updated
        log_row.items_unchanged = unchanged_cache
        log_row.errors = errors
        db.commit()

        summary = {
            "total": total,
            "new_seeds": new_seeds,
            "matched_existing": matched_existing,
            "duplicates": duplicates,
            "alt_id_added": alt_id_added,
            "cache_inserted": inserted,
            "cache_updated": updated,
            "errors": errors,
            "duration_ms": duration_ms,
        }
        logger.info("[kmdb] discover_kmdb.%s 완료 — %s", mode, summary)
        db.close()
        return summary

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(name="workers.tasks.discovery_tasks.discover_all_daily")
def discover_all_daily():
    """매일 발굴 3소스 일괄 실행 (group — 병렬, 순서 무관)."""
    job = group(
        discover_tmdb.s("trending_day"),
        discover_tmdb.s("upcoming"),
        discover_kobis.s("box_office_daily"),
        discover_kobis.s("new_release"),
        discover_kmdb.s("new_release"),
    )
    result = job.apply_async()
    logger.info("[discovery] discover_all_daily 실행 — group_id=%s", result.id)
    return {"group_id": str(result.id)}
