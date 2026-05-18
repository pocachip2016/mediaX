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
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Seoul",
    beat_scheduler="redbeat.RedBeatScheduler",
    redbeat_redis_url=settings.REDIS_URL,
    redbeat_lock_timeout=10 * 60,  # 10분 — loop interval(60s)의 10배
    beat_max_loop_interval=60,     # 60s마다 lock 갱신 (기본 300s에서 단축)
    beat_schedule={
        "poll-cp-emails": {
            "task": "workers.tasks.metadata.poll_cp_emails",
            "schedule": 300,  # 5분
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
