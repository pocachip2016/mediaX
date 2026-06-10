"""curation.py — 홈 큐레이션 Beat 태스크 (ADR-013).

weekly_banner_plan (Beat 매주 월요일 01:10 KST):
  이번 주 월요일 기준 배너 편성안을 자동 생성(draft).
  이미 해당 week_start 편성안이 존재하면 멱등으로 종료.
"""
import logging
from datetime import date, timedelta

from celery import shared_task

from shared.database import SessionLocal

logger = logging.getLogger(__name__)


def _this_monday() -> date:
    """오늘 기준 이번 주 월요일(KST) 반환."""
    today = date.today()
    return today - timedelta(days=today.weekday())


@shared_task(
    name="workers.tasks.curation.weekly_banner_plan",
    queue="pipeline_fast",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def weekly_banner_plan(self) -> dict:
    """매주 월요일: 이번 주 배너 편성안 초안 자동 생성."""
    from api.programming.curation.banner_service import create_plan
    from api.programming.curation.models import CurationBannerPlan, BannerPlanStatus

    week_start = _this_monday()

    with SessionLocal() as db:
        existing = (
            db.query(CurationBannerPlan)
            .filter(CurationBannerPlan.week_start == week_start)
            .first()
        )
        if existing:
            logger.info(
                "weekly_banner_plan: week_start=%s already exists (status=%s), skipping",
                week_start,
                existing.status,
            )
            return {"week_start": str(week_start), "created": False, "status": existing.status.value}

        try:
            plan = create_plan(db, week_start)
            logger.info(
                "weekly_banner_plan: created plan id=%s week_start=%s ctr=%.3f",
                plan.id,
                week_start,
                plan.ctr_prediction or 0.0,
            )
            return {
                "week_start": str(week_start),
                "created": True,
                "plan_id": plan.id,
                "ctr_prediction": plan.ctr_prediction,
            }
        except Exception as exc:
            logger.exception("weekly_banner_plan error week_start=%s", week_start)
            raise self.retry(exc=exc)
