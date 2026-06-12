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


# ── _handle_stale_running_runs (return value) ─────────────────────────────────

def test_handle_stale_returns_count(session):
    """stale run이 있으면 closed 수를 반환한다."""
    from datetime import timedelta
    from workers.tasks.facet_tasks import _handle_stale_running_runs

    run = FacetBatchRun(
        status="running",
        trigger="auto",
        total_count=1,
        created_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    session.add(run)
    session.commit()

    closed = _handle_stale_running_runs(session)
    assert closed == 1
    session.refresh(run)
    assert run.status == "failed"


def test_handle_stale_returns_zero_when_fresh(session):
    """stale 기준 미달 run은 0 반환."""
    from workers.tasks.facet_tasks import _handle_stale_running_runs

    run = FacetBatchRun(status="running", trigger="auto", total_count=1)
    session.add(run)
    session.commit()

    closed = _handle_stale_running_runs(session)
    assert closed == 0
    session.refresh(run)
    assert run.status == "running"


# ── _summarize_sources ───────────────────────────────────────────────────────

def test_summarize_sources_normal():
    """정상 입력 → compact 요약 반환."""
    from workers.tasks.facet_tasks import _summarize_sources

    data = {
        "sources_detail": [
            {"provider": "playwright", "docs_count": 1, "evaluated": True},
            {"provider": "wikipedia", "docs_count": 1, "evaluated": True},
            {"provider": "omdb", "docs_count": 0, "evaluated": False},
        ]
    }
    result = _summarize_sources(data)
    assert result is not None
    assert len(result) == 3
    assert result[0] == {"p": "playwright", "docs": 1, "eval": True}
    assert result[2] == {"p": "omdb", "docs": 0, "eval": False}


def test_summarize_sources_missing():
    """sources_detail 없음/None/빈 리스트 → None 반환."""
    from workers.tasks.facet_tasks import _summarize_sources

    assert _summarize_sources({}) is None
    assert _summarize_sources({"sources_detail": None}) is None
    assert _summarize_sources({"sources_detail": []}) is None


def test_summarize_sources_broken_entries():
    """키 누락 엔트리 포함 → raise 없이 통과, 정상 엔트리는 반환."""
    from workers.tasks.facet_tasks import _summarize_sources

    data = {
        "sources_detail": [
            "not_a_dict",
            {"provider": "kowiki", "docs_count": 2, "evaluated": True},
        ]
    }
    result = _summarize_sources(data)
    assert result is not None
    assert len(result) == 1
    assert result[0]["p"] == "kowiki"


# ── check_stale_facet_runs ────────────────────────────────────────────────────

def test_watchdog_disabled_no_redispatch(session):
    """FACET_BATCH_ENABLED=False면 idle여도 재디스패치 안 함 (의도적 정지 존중)."""
    with patch("workers.tasks.facet_tasks.SessionLocal") as mock_sl, \
         patch("workers.tasks.facet_tasks.dispatch_facet_batch") as mock_dispatch, \
         patch("workers.tasks.facet_tasks.settings") as mock_settings:
        mock_sl.return_value.__enter__ = lambda s: session
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        mock_settings.FACET_CONTINUOUS = True
        mock_settings.FACET_BATCH_ENABLED = False

        from workers.tasks.facet_tasks import check_stale_facet_runs
        result = check_stale_facet_runs()

    assert result == {"closed": 0}
    mock_dispatch.apply_async.assert_not_called()


def test_watchdog_idle_redispatches(session):
    """running run이 없으면(idle) stale 닫은 게 없어도 재디스패치한다."""
    with patch("workers.tasks.facet_tasks.SessionLocal") as mock_sl, \
         patch("workers.tasks.facet_tasks.dispatch_facet_batch") as mock_dispatch, \
         patch("workers.tasks.facet_tasks.settings") as mock_settings:
        mock_sl.return_value.__enter__ = lambda s: session
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        mock_settings.FACET_CONTINUOUS = True
        mock_settings.FACET_BATCH_ENABLED = True
        mock_settings.FACET_CONTINUOUS_DELAY_S = 60

        from workers.tasks.facet_tasks import check_stale_facet_runs
        result = check_stale_facet_runs()

    assert result == {"closed": 0}
    mock_dispatch.apply_async.assert_called_once_with(
        kwargs={"trigger": "auto"}, countdown=60
    )


def test_watchdog_running_no_redispatch(session):
    """신선한(non-stale) running run이 있으면 재디스패치 안 함."""
    run = FacetBatchRun(
        status="running",
        trigger="auto",
        total_count=1,
        created_at=datetime.now(timezone.utc),
    )
    session.add(run)
    session.commit()

    with patch("workers.tasks.facet_tasks.SessionLocal") as mock_sl, \
         patch("workers.tasks.facet_tasks.dispatch_facet_batch") as mock_dispatch, \
         patch("workers.tasks.facet_tasks.settings") as mock_settings:
        mock_sl.return_value.__enter__ = lambda s: session
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        mock_settings.FACET_CONTINUOUS = True
        mock_settings.FACET_BATCH_ENABLED = True
        mock_settings.FACET_CONTINUOUS_DELAY_S = 60

        from workers.tasks.facet_tasks import check_stale_facet_runs
        result = check_stale_facet_runs()

    assert result == {"closed": 0}
    mock_dispatch.apply_async.assert_not_called()


def test_watchdog_stale_triggers_redispatch(session):
    """stale run 있고 FACET_CONTINUOUS=True면 재디스패치한다."""
    from datetime import timedelta

    run = FacetBatchRun(
        status="running",
        trigger="auto",
        total_count=1,
        created_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    session.add(run)
    session.commit()

    with patch("workers.tasks.facet_tasks.SessionLocal") as mock_sl, \
         patch("workers.tasks.facet_tasks.dispatch_facet_batch") as mock_dispatch, \
         patch("workers.tasks.facet_tasks.settings") as mock_settings:
        mock_sl.return_value.__enter__ = lambda s: session
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        mock_settings.FACET_CONTINUOUS = True
        mock_settings.FACET_BATCH_ENABLED = True
        mock_settings.FACET_CONTINUOUS_DELAY_S = 60

        from workers.tasks.facet_tasks import check_stale_facet_runs
        result = check_stale_facet_runs()

    assert result == {"closed": 1}
    mock_dispatch.apply_async.assert_called_once_with(
        kwargs={"trigger": "auto"}, countdown=60
    )


# ── evaluate_tmdb_facet payload ───────────────────────────────────────────────

def test_evaluate_payload_includes_backfill(session):
    """evaluate_tmdb_facet이 MediSearch에 보내는 payload에 backfill=True가 포함된다."""
    import httpx
    from unittest.mock import patch, MagicMock
    from api.programming.metadata.models.external import FacetBatchRun
    from api.programming.metadata.models.tmdb_cache import TmdbMovieCache

    # 테스트용 run + cache row 준비
    run = FacetBatchRun(status="running", trigger="manual", total_count=1)
    session.add(run)
    session.commit()
    session.refresh(run)

    from datetime import date
    cache = TmdbMovieCache(
        id=99999,
        title="테스트영화",
        original_language="ko",
        vote_count=100,
        release_date=date(2020, 1, 1),
    )
    session.add(cache)
    session.commit()

    captured_payload = {}

    def fake_post(url, json=None, **kwargs):
        captured_payload.update(json or {})
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "source_count": 2,
            "facet": {"mood": ["경쾌"]},
        }
        return mock_resp

    with patch("workers.tasks.facet_tasks.SessionLocal") as mock_sl, \
         patch("workers.tasks.facet_tasks.httpx.Client") as mock_client:
        # SessionLocal이 테스트 session 반환
        mock_sl.return_value.__enter__ = lambda s: session
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        # httpx.Client.post → fake_post
        mock_client.return_value.__enter__ = lambda s: MagicMock(post=fake_post)
        mock_client.return_value.__exit__ = MagicMock(return_value=False)

        from workers.tasks.facet_tasks import evaluate_tmdb_facet
        evaluate_tmdb_facet(tmdb_id=99999, run_id=run.id)

    assert captured_payload.get("backfill") is True, \
        f"payload에 backfill=True 없음: {captured_payload}"
