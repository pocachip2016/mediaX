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
        "workers.tasks.metadata",     # 메타 AI 분류·외부 메타 수집
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Seoul",
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
    },
    task_routes={
        "workers.tasks.design.generate_asset":   {"queue": "design.normal"},
        "workers.tasks.design.generate_urgent":  {"queue": "design.high"},
        "workers.tasks.design.brand_check":      {"queue": "design.brand_check"},
        "workers.tasks.design.cdn_upload":       {"queue": "design.cdn"},
        "workers.tasks.ingest.*":                {"queue": "ingest"},
        "workers.tasks.analytics.*":             {"queue": "analytics"},
        "workers.tasks.metadata.*":              {"queue": "metadata"},
    },
)
