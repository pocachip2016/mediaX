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
    """KMDB 발굴 태스크.

    mode: new_release | discover_drama | discover_movie
    """
    try:
        from api.meta_core.discovery.kmdb_source import KmdbDiscoverySource

        db = SessionLocal()
        try:
            from api.meta_core.discovery.runner import run_discovery
            source = KmdbDiscoverySource(api_key=settings.KMDB_API_KEY, recent_days=days)
            return run_discovery(db, source, mode)
        finally:
            db.close()
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
