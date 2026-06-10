"""test_facet_tasks.py — facet_tasks 단위 테스트.

_emit_event 경로 검증:
- log_enabled=False → FacetEvent 미기록
- log_enabled=True  → FacetEvent 기록

NOTE: _select_targets / evaluate_tmdb_facet 테스트는 TMDB 기반 모집단(TmdbMovieCache +
TmdbMovieFacet)으로 전면 재작성 필요. 기존 Content 기반 테스트는 모집단 모델 교체로
제거됨. 순수 분류/포맷 테스트는 tests/test_facet_classify.py 참조.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api.programming.metadata.models  # noqa: F401
import api.meta_core.models  # noqa: F401
import api.meta_core.public_api.models  # noqa: F401
import api.distribution.models  # noqa: F401
import api.programming.catalog.models  # noqa: F401
import api.programming.scheduling.models  # noqa: F401
import api.programming.scheduling.profile_models  # noqa: F401
import api.programming.curation.models  # noqa: F401
from shared.database import Base
from api.programming.metadata.models.external import FacetBatchRun, FacetEvent, FacetPolicy


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as s:
        yield s


def _make_run(session) -> FacetBatchRun:
    run = FacetBatchRun(status="running", trigger="manual", total_count=1)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def _enable_log(session) -> FacetPolicy:
    policy = FacetPolicy(id=1, log_enabled=True)
    session.merge(policy)
    session.commit()
    return policy


# ── _emit_event ───────────────────────────────────────────────────────────────

def test_emit_event_log_disabled_no_write(session):
    """log_enabled=False → FacetEvent 미기록."""
    from workers.tasks.facet_tasks import _emit_event

    run = _make_run(session)

    with patch("workers.tasks.facet_tasks.SessionLocal") as mock_sl:
        mock_sl.return_value.__enter__ = lambda s: session
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        _emit_event(run.id, None, "batch_started", "테스트")

    assert session.query(FacetEvent).count() == 0


def test_emit_event_log_enabled_writes_event(session):
    """log_enabled=True → FacetEvent 기록."""
    from workers.tasks.facet_tasks import _emit_event

    run = _make_run(session)
    _enable_log(session)

    with patch("workers.tasks.facet_tasks.SessionLocal") as mock_sl:
        mock_sl.return_value.__enter__ = lambda s: session
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        _emit_event(run.id, 42, "item_success", "저장 완료", {"confidence": 0.9})

    events = session.query(FacetEvent).all()
    assert len(events) == 1
    assert events[0].run_id == run.id
    assert events[0].content_id == 42
    assert events[0].event_type == "item_success"
