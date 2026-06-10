"""test_curation_beat.py — weekly_banner_plan Beat 태스크 단위 테스트."""
import importlib
import sys
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ── celery stub (테스트 환경에 celery 없을 경우 대비) ────────────────────────
def _ensure_celery_stub():
    if "celery" not in sys.modules:
        celery_stub = MagicMock()
        # shared_task: decorator that returns the function unchanged
        celery_stub.shared_task = lambda **kw: (lambda f: f)
        sys.modules["celery"] = celery_stub
        sys.modules["celery.schedules"] = MagicMock()
    if "redbeat" not in sys.modules:
        sys.modules["redbeat"] = MagicMock()

_ensure_celery_stub()

import api.programming.curation.models  # noqa: F401
import api.programming.scheduling.models  # noqa: F401
from shared.database import Base


# ── DB fixture ────────────────────────────────────────────────────────────────

@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


# ── helper ────────────────────────────────────────────────────────────────────

def _this_monday() -> date:
    today = date.today()
    return today - timedelta(days=today.weekday())


# ── tests ─────────────────────────────────────────────────────────────────────

class TestWeeklyBannerPlanTask:
    def test_creates_plan_when_none_exists(self, db):
        """auto_enabled 노드 없어도 draft 편성안은 생성된다."""
        from api.programming.curation.banner_service import create_plan

        week_start = _this_monday()
        plan = create_plan(db, week_start)

        assert plan.id is not None
        assert plan.week_start == week_start
        assert plan.status.value == "draft"

    def test_idempotent_on_second_call(self, db):
        """같은 week_start 로 두 번 호출하면 동일 plan 반환."""
        from api.programming.curation.banner_service import create_plan

        week_start = _this_monday()
        p1 = create_plan(db, week_start)
        p2 = create_plan(db, week_start)

        assert p1.id == p2.id

    def test_task_skips_when_plan_exists(self, db):
        """편성안이 이미 있으면 created=False 반환."""
        from api.programming.curation.banner_service import create_plan
        import workers.tasks.curation as curation_mod

        week_start = _this_monday()
        create_plan(db, week_start)
        db.commit()

        with patch("workers.tasks.curation.SessionLocal") as mock_sl:
            mock_sl.return_value.__enter__ = lambda s: db
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            result = curation_mod.weekly_banner_plan(None)

        assert result["created"] is False
        assert result["week_start"] == str(week_start)

    def test_task_creates_plan_when_missing(self, db):
        """편성안 없으면 created=True + plan_id 반환."""
        import workers.tasks.curation as curation_mod

        with patch("workers.tasks.curation.SessionLocal") as mock_sl:
            mock_sl.return_value.__enter__ = lambda s: db
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            result = curation_mod.weekly_banner_plan(None)

        assert result["created"] is True
        assert "plan_id" in result
        assert result["week_start"] == str(_this_monday())

    def test_beat_schedule_registered(self):
        """celery_app.py 소스에 weekly-banner-plan 항목 포함 확인."""
        import pathlib
        src = pathlib.Path("workers/celery_app.py").read_text()
        assert "weekly-banner-plan" in src, "beat_schedule weekly-banner-plan 미등록"
        assert "workers.tasks.curation.weekly_banner_plan" in src, "태스크 경로 불일치"
        assert "workers.tasks.curation" in src, "include 미등록"

    def test_this_monday_is_monday(self):
        """_this_monday() 결과가 항상 월요일(weekday=0)."""
        from workers.tasks.curation import _this_monday
        assert _this_monday().weekday() == 0
