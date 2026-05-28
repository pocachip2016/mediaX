import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    name="workers.tasks.distribution.sync_ott_watcha",
    bind=True,
    max_retries=2,
    default_retry_delay=600,
)
def sync_ott_watcha(self) -> dict:
    from shared.database import SessionLocal
    from api.distribution.ott.runner import run_source
    from api.distribution.ott.watcha import WatchaTopSource

    db = SessionLocal()
    try:
        summary = run_source(db, WatchaTopSource())
        return vars(summary)
    except Exception as exc:
        logger.exception("sync_ott_watcha 실패")
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"error": str(exc)}
    finally:
        db.close()


@shared_task(
    name="workers.tasks.distribution.sync_ott_netflix",
    bind=True,
    max_retries=2,
    default_retry_delay=600,
)
def sync_ott_netflix(self) -> dict:
    from shared.database import SessionLocal
    from api.distribution.ott.runner import run_source
    from api.distribution.ott.netflix import NetflixTudumSource

    db = SessionLocal()
    try:
        summary = run_source(db, NetflixTudumSource())
        return vars(summary)
    except Exception as exc:
        logger.exception("sync_ott_netflix 실패")
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"error": str(exc)}
    finally:
        db.close()


@shared_task(
    name="workers.tasks.distribution.sync_ott_wave",
    bind=True,
    max_retries=2,
    default_retry_delay=600,
)
def sync_ott_wave(self) -> dict:
    from shared.database import SessionLocal
    from api.distribution.ott.runner import run_source
    from api.distribution.ott.wave import WaveTopSource

    db = SessionLocal()
    try:
        summary = run_source(db, WaveTopSource())
        return vars(summary)
    except Exception as exc:
        logger.exception("sync_ott_wave 실패")
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"error": str(exc)}
    finally:
        db.close()


@shared_task(
    name="workers.tasks.distribution.sync_ott_tving",
    bind=True,
    max_retries=2,
    default_retry_delay=600,
)
def sync_ott_tving(self) -> dict:
    from shared.database import SessionLocal
    from api.distribution.ott.runner import run_source
    from api.distribution.ott.tving import TvingTopSource

    db = SessionLocal()
    try:
        summary = run_source(db, TvingTopSource())
        return vars(summary)
    except Exception as exc:
        logger.exception("sync_ott_tving 실패")
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"error": str(exc)}
    finally:
        db.close()


@shared_task(
    name="workers.tasks.distribution.backfill_external_curations",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def backfill_external_curations(self) -> dict:
    """모든 OTT 소스의 섹션을 external_curations/items에 영속화.
    fetch_sections() + ott/matcher content_id resolve 재사용."""
    from shared.database import SessionLocal
    from api.distribution.ott.curation_runner import run_curation_source
    from api.distribution.ott.watcha import WatchaTopSource
    from api.distribution.ott.netflix import NetflixTudumSource
    from api.distribution.ott.wave import WaveTopSource
    from api.distribution.ott.tving import TvingTopSource

    sources = [WatchaTopSource(), NetflixTudumSource(), WaveTopSource(), TvingTopSource()]
    db = SessionLocal()
    results = []
    try:
        for source in sources:
            summary = run_curation_source(db, source)
            results.append({
                "channel": summary.channel,
                "sections": summary.sections,
                "items_total": summary.items_total,
                "items_resolved": summary.items_resolved,
                "errors": summary.errors,
            })
        return {"sources": results}
    except Exception as exc:
        logger.exception("backfill_external_curations 실패")
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"error": str(exc)}
    finally:
        db.close()
