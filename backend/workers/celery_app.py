from celery import Celery
from celery.schedules import crontab
from shared.config import settings

celery_app = Celery(
    "media_ax",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "workers.tasks.design",       # AI 이미지 생성·브랜드 검수·배치
        "workers.tasks.ingest",       # 인코딩·QC·DRM·CDN
        "workers.tasks.analytics",    # 리포트·정산 배치
        "workers.tasks.metadata",          # 메타 AI 분류·외부 메타 수집
        "workers.tasks.tmdb_cache",        # TMDB 로컬 캐시 백필·일일 증분
        "workers.tasks.kmdb_cache",        # KMDB 로컬 캐시 백필·quota-aware Beat
        "workers.tasks.discovery_tasks",   # Phase C SEED 발굴
        "workers.websearch_tasks",         # Phase D WebSearch SEED 발굴
        "workers.tasks.distribution",      # OTT popularity sync (Watcha/Netflix/Wave/Tving)
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Seoul",
    beat_scheduler="redbeat.RedBeatScheduler",
    redbeat_redis_url=settings.REDIS_URL,
    redbeat_lock_timeout=30 * 60,  # 30분 — WSL2 sleep 후 재기동 여유 (기존 10분)
    beat_max_loop_interval=30,     # 30s마다 lock 갱신 (기존 60s에서 단축)
    beat_schedule={
        "poll-cp-emails": {
            "task": "workers.tasks.metadata.poll_cp_emails",
            "schedule": crontab(hour=0, minute=0),  # 매일 자정 (00:00 KST)
        },
        "sync-kobis-daily": {
            "task": "workers.tasks.metadata.sync_kobis",
            "schedule": crontab(hour=3, minute=0),
        },
        "sync-tmdb-daily": {
            "task": "workers.tasks.metadata.sync_tmdb",
            "schedule": crontab(hour=2, minute=0),
        },
        "reeval-quality-scores": {
            "task": "workers.tasks.metadata.reeval_quality_scores",
            "schedule": crontab(hour=1, minute=0),
        },
        "check-missing-episodes": {
            "task": "workers.tasks.metadata.check_missing_episodes",
            "schedule": crontab(hour=4, minute=0),
        },
        "retry-failed-enrichments": {
            "task": "workers.tasks.metadata.retry_failed_enrichments",
            "schedule": 21600,  # 6시간
        },
        "tmdb-daily-changes": {
            "task": "workers.tasks.tmdb_cache.daily_changes",
            "schedule": crontab(hour=3, minute=30),  # 매일 03:30 KST
        },
        "tmdb-daily-new-releases": {
            "task": "workers.tasks.tmdb_cache.daily_new_releases",
            "schedule": crontab(hour=3, minute=45),  # 매일 03:45 KST
        },
        # Phase C SEED 발굴 — 04:30~05:30 (기존 beat 충돌 방지)
        "discover-tmdb-daily": {
            "task": "workers.tasks.discovery_tasks.discover_tmdb",
            "schedule": crontab(hour=4, minute=30),
            "kwargs": {"mode": "trending_day"},
        },
        "discover-kobis-daily": {
            "task": "workers.tasks.discovery_tasks.discover_kobis",
            "schedule": crontab(hour=5, minute=0),
            "kwargs": {"mode": "box_office_daily"},
        },
        "discover-kmdb-daily": {
            "task": "workers.tasks.discovery_tasks.discover_kmdb",
            "schedule": crontab(hour=5, minute=30),
            "kwargs": {"mode": "new_release"},
        },
        "backfill-kmdb-historical": {
            "task": "workers.tasks.kmdb_cache.kmdb_quota_backfill_tick",
            "schedule": crontab(hour=6, minute=0),
        },
        "backfill-kobis-historical": {
            "task": "workers.tasks.metadata.kobis_quota_backfill_tick",
            "schedule": crontab(hour=6, minute=30),
        },
        "discover-tmdb-weekly": {
            "task": "workers.tasks.discovery_tasks.discover_tmdb",
            "schedule": crontab(hour=6, minute=0, day_of_week=0),
            "kwargs": {"mode": "trending_week"},
        },
        # Phase D WebSearch SEED 발굴 — 매일 04:30 KST (trending 5쿼리, 안전 마진)
        "discover-websearch-trending": {
            "task": "discover.websearch_trending",
            "schedule": crontab(hour=4, minute=30),
            "options": {"expires": 3600},
        },
        # Dam 포스터 catch-up — 매일 06:00 KST (webhook 누락 건 재발송, image_id 멱등)
        "sync-primary-posters-to-dam": {
            "task": "workers.tasks.metadata.sync_primary_posters_to_dam",
            "schedule": crontab(hour=6, minute=0),
        },
        # KMDB 캐시 → contents 링크 — 매일 07:00 KST (kmdb 캐시 백필 완료 후, idempotent)
        "link-kmdb-to-contents": {
            "task": "workers.tasks.metadata.link_kmdb_cache_to_contents",
            "schedule": crontab(hour=7, minute=0),
        },
        # KMDB poster/stillcut → content_images — 매일 07:15 KST (link-kmdb 07:00 완료 후)
        "sync-kmdb-posters-to-content-images": {
            "task": "workers.tasks.kmdb_cache.sync_kmdb_poster_to_content_images",
            "schedule": crontab(hour=7, minute=15),
        },
        # TMDB 캐시 → contents 링크 — 매일 07:30 KST (tmdb_movie_cache/tmdb_tv_cache, idempotent)
        "link-tmdb-to-contents": {
            "task": "workers.tasks.metadata.link_tmdb_cache_to_contents",
            "schedule": crontab(hour=7, minute=30),
        },
        # TMDB poster/backdrop → content_images — 매일 07:50 KST (link-tmdb 07:30 완료 후)
        "sync-tmdb-posters-to-content-images": {
            "task": "workers.tasks.tmdb_cache.sync_tmdb_poster_to_content_images",
            "schedule": crontab(hour=7, minute=50),
        },
        # KOBIS 캐시 → contents 링크 — 매일 07:45 KST (kobis_movie_cache, idempotent)
        "link-kobis-to-contents": {
            "task": "workers.tasks.metadata.link_kobis_cache_to_contents",
            "schedule": crontab(hour=7, minute=45),
        },
        # TMDB 역순 역사 백필 — 매일 08:30 KST (최신 연도부터 역순, quota-aware, 1일 1연도)
        "backfill-tmdb-historical": {
            "task": "workers.tasks.tmdb_cache.tmdb_quota_backfill_tick",
            "schedule": crontab(hour=8, minute=30),
        },
        # OTT popularity sync — 06:40~07:20 KST (06:30 backfill-kobis / 07:00 link-kmdb 충돌 회피)
        "sync-ott-watcha": {
            "task": "workers.tasks.distribution.sync_ott_watcha",
            "schedule": crontab(hour=6, minute=40),
        },
        "sync-ott-netflix": {
            "task": "workers.tasks.distribution.sync_ott_netflix",
            "schedule": crontab(hour=6, minute=50),
        },
        "sync-ott-wave": {
            "task": "workers.tasks.distribution.sync_ott_wave",
            "schedule": crontab(hour=7, minute=10),
        },
        "sync-ott-tving": {
            "task": "workers.tasks.distribution.sync_ott_tving",
            "schedule": crontab(hour=7, minute=20),
        },
        # 외부 큐레이션 섹션 영속화 — 매일 07:30 KST (OTT sync 완료 후)
        "backfill-external-curations": {
            "task": "workers.tasks.distribution.backfill_external_curations",
            "schedule": crontab(hour=7, minute=30),
        },
    },
    broker_connection_retry_on_startup=True,
    broker_transport_options={
        "visibility_timeout": 7200,   # 2h — backfill_movies 90s+ 재할당 방지
        "socket_keepalive": True,
        "retry_on_timeout": True,
        "max_connections": 50,
    },
    result_backend_transport_options={
        "visibility_timeout": 7200,
        "retry_on_timeout": True,
    },
    task_routes={
        "workers.tasks.design.generate_asset":   {"queue": "design.normal"},
        "workers.tasks.design.generate_urgent":  {"queue": "design.high"},
        "workers.tasks.design.brand_check":      {"queue": "design.brand_check"},
        "workers.tasks.design.cdn_upload":       {"queue": "design.cdn"},
        "workers.tasks.ingest.*":                {"queue": "ingest"},
        "workers.tasks.analytics.*":             {"queue": "analytics"},
        "workers.tasks.metadata.*":              {"queue": "metadata"},
        "workers.tasks.tmdb_cache.*":            {"queue": "metadata"},
        "workers.tasks.kmdb_cache.*":            {"queue": "metadata"},
        "workers.tasks.discovery_tasks.*":       {"queue": "metadata"},
    },
)


from celery.signals import worker_ready  # noqa: E402


@worker_ready.connect
def cleanup_stale_sync_logs(sender=None, **kwargs):
    """Worker 시작 시 1h+ running 상태 sync_log를 failed로 마킹 (crash 잔류 레코드 자동 정리)."""
    import logging
    from datetime import datetime, timedelta, timezone

    from shared.database import SessionLocal
    from api.programming.metadata.models import TmdbSyncLog, TmdbSyncStatus

    logger = logging.getLogger(__name__)
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        stale = (
            db.query(TmdbSyncLog)
            .filter(
                TmdbSyncLog.status == TmdbSyncStatus.running,
                TmdbSyncLog.started_at < cutoff,
            )
            .all()
        )
        for row in stale:
            row.status = TmdbSyncStatus.failed
            row.finished_at = datetime.now(timezone.utc)
            row.error_sample = ["auto-cleanup on worker_ready: stale > 1h"]
        if stale:
            db.commit()
            logger.warning(f"[startup_cleanup] {len(stale)} stale sync_log → failed")
        else:
            logger.info("[startup_cleanup] no stale sync_log")
    except Exception as exc:
        logger.error(f"[startup_cleanup] failed: {exc}")
        db.rollback()
    finally:
        db.close()
