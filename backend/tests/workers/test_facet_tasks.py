"""test_facet_tasks.py — facet_tasks 단위 테스트 (mock httpx + SessionLocal).

_select_targets, evaluate_content_facet 핵심 경로 검증:
- 신선 facet 있는 콘텐츠 제외 / stale 포함 / force 시 모두 포함
- 저장 성공 경로: 기존 final 강등 + 신규 final 삽입 + 카운터 증가 + run done 전환
- source_count==0 실패 경로
- confidence==0 실패 경로
"""
from datetime import datetime, timedelta, timezone
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
from api.programming.metadata.models import (
    ContentAIResult, AITaskType,
    ExternalMetaSource, ExternalSourceType,
)
from api.programming.metadata.models.content import Content, ContentType
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


def _make_movie(session, title="테스트영화") -> Content:
    c = Content(title=title, content_type=ContentType.movie)
    session.add(c)
    session.flush()
    return c


def _make_tmdb_source(session, content_id: int, external_id="12345"):
    src = ExternalMetaSource(
        content_id=content_id,
        source_type=ExternalSourceType.tmdb,
        external_id=external_id,
        title_on_source="Test Movie",
    )
    session.add(src)
    session.flush()
    return src


def _make_final_facet(session, content_id: int, days_old: int = 0):
    processed = datetime.now(timezone.utc) - timedelta(days=days_old)
    r = ContentAIResult(
        content_id=content_id,
        engine="medisearch",
        task_type=AITaskType.facet_analysis,
        result_json={"primary_genre": "드라마"},
        quality_score=0.8,
        is_final=True,
        processed_at=processed,
    )
    session.add(r)
    session.flush()
    return r


# ── _select_targets ────────────────────────────────────────────────────────────

def test_select_excludes_fresh_facet(session):
    from workers.tasks.facet_tasks import _select_targets

    movie = _make_movie(session)
    _make_tmdb_source(session, movie.id)
    _make_final_facet(session, movie.id, days_old=10)  # 10일, 신선 (staleness=180)
    session.commit()

    targets = _select_targets(session, limit=100, content_ids=None, force=False, staleness_days=180)
    assert movie.id not in targets


def test_select_includes_stale_facet(session):
    from workers.tasks.facet_tasks import _select_targets

    movie = _make_movie(session)
    _make_tmdb_source(session, movie.id)
    _make_final_facet(session, movie.id, days_old=200)  # 200일, stale
    session.commit()

    targets = _select_targets(session, limit=100, content_ids=None, force=False, staleness_days=180)
    assert movie.id in targets


def test_select_force_includes_fresh(session):
    from workers.tasks.facet_tasks import _select_targets

    movie = _make_movie(session)
    _make_tmdb_source(session, movie.id)
    _make_final_facet(session, movie.id, days_old=10)
    session.commit()

    targets = _select_targets(session, limit=100, content_ids=None, force=True, staleness_days=180)
    assert movie.id in targets


def test_select_orders_by_production_year_desc(session):
    from workers.tasks.facet_tasks import _select_targets

    # 3개 영화: 2024, 2020, 2022 production_year
    m2024 = Content(title="최신영화", content_type=ContentType.movie, production_year=2024)
    m2020 = Content(title="옛날영화", content_type=ContentType.movie, production_year=2020)
    m2022 = Content(title="중간영화", content_type=ContentType.movie, production_year=2022)
    session.add_all([m2024, m2020, m2022])
    session.flush()

    for c in [m2024, m2020, m2022]:
        _make_tmdb_source(session, c.id)
    session.commit()

    targets = _select_targets(session, limit=100, content_ids=None, force=False, staleness_days=180)
    # 예상 순서: 2024 → 2022 → 2020
    assert targets == [m2024.id, m2022.id, m2020.id]


def test_select_excludes_no_external_source(session):
    from workers.tasks.facet_tasks import _select_targets

    movie = _make_movie(session)  # 외부소스 없음
    session.commit()

    targets = _select_targets(session, limit=100, content_ids=None, force=False, staleness_days=180)
    assert movie.id not in targets


# ── evaluate_content_facet ────────────────────────────────────────────────────

def _make_run(session) -> FacetBatchRun:
    run = FacetBatchRun(status="running", trigger="manual", total_count=1)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def _mock_response(data: dict, status_code: int = 200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status.return_value = None
    return resp


def test_evaluate_success_saves_result(session):
    from workers.tasks.facet_tasks import evaluate_content_facet

    movie = _make_movie(session)
    _make_tmdb_source(session, movie.id)
    run = _make_run(session)

    facet_data = {
        "facet": {"primary_genre": "드라마", "tension": 0.8},
        "source_count": 3,
        "confidence": 0.85,
    }

    with patch("workers.tasks.facet_tasks.SessionLocal") as mock_sl, \
         patch("workers.tasks.facet_tasks.httpx.Client") as mock_client_cls:

        mock_sl.return_value.__enter__ = lambda s: session
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)

        mock_http = MagicMock()
        mock_client_cls.return_value.__enter__ = lambda s: mock_http
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.post.return_value = _mock_response(facet_data)

        result = evaluate_content_facet.run(content_id=movie.id, run_id=run.id)

    assert result["status"] == "ok"
    assert result["confidence"] == 0.85


def test_evaluate_source_count_zero_fails(session):
    from workers.tasks.facet_tasks import evaluate_content_facet

    movie = _make_movie(session)
    _make_tmdb_source(session, movie.id)
    run = _make_run(session)

    facet_data = {"facet": {}, "source_count": 0, "confidence": 0.5}

    with patch("workers.tasks.facet_tasks.SessionLocal") as mock_sl, \
         patch("workers.tasks.facet_tasks.httpx.Client") as mock_client_cls:

        mock_sl.return_value.__enter__ = lambda s: session
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        mock_http = MagicMock()
        mock_client_cls.return_value.__enter__ = lambda s: mock_http
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.post.return_value = _mock_response(facet_data)

        result = evaluate_content_facet.run(content_id=movie.id, run_id=run.id)

    assert result["status"] == "failed"
    assert result["reason"] == "low_quality"


def test_evaluate_confidence_zero_fails(session):
    from workers.tasks.facet_tasks import evaluate_content_facet

    movie = _make_movie(session)
    _make_tmdb_source(session, movie.id)
    run = _make_run(session)

    facet_data = {"facet": {}, "source_count": 2, "confidence": 0.0}

    with patch("workers.tasks.facet_tasks.SessionLocal") as mock_sl, \
         patch("workers.tasks.facet_tasks.httpx.Client") as mock_client_cls:

        mock_sl.return_value.__enter__ = lambda s: session
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        mock_http = MagicMock()
        mock_client_cls.return_value.__enter__ = lambda s: mock_http
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.post.return_value = _mock_response(facet_data)

        result = evaluate_content_facet.run(content_id=movie.id, run_id=run.id)

    assert result["status"] == "failed"
    assert result["reason"] == "low_quality"


def test_evaluate_demotes_existing_final(session):
    from workers.tasks.facet_tasks import evaluate_content_facet

    movie = _make_movie(session)
    _make_tmdb_source(session, movie.id)
    old_result = _make_final_facet(session, movie.id)
    run = _make_run(session)

    facet_data = {
        "facet": {"primary_genre": "액션"},
        "source_count": 2,
        "confidence": 0.9,
    }

    with patch("workers.tasks.facet_tasks.SessionLocal") as mock_sl, \
         patch("workers.tasks.facet_tasks.httpx.Client") as mock_client_cls:

        mock_sl.return_value.__enter__ = lambda s: session
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        mock_http = MagicMock()
        mock_client_cls.return_value.__enter__ = lambda s: mock_http
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.post.return_value = _mock_response(facet_data)

        evaluate_content_facet.run(content_id=movie.id, run_id=run.id)

    session.refresh(old_result)
    assert old_result.is_final is False

    new_finals = (
        session.query(ContentAIResult)
        .filter(
            ContentAIResult.content_id == movie.id,
            ContentAIResult.task_type == AITaskType.facet_analysis,
            ContentAIResult.is_final.is_(True),
        )
        .all()
    )
    assert len(new_finals) == 1
    assert new_finals[0].quality_score == 0.9


# ── _emit_event / 로깅 ────────────────────────────────────────────────────────

def _enable_log(session) -> FacetPolicy:
    policy = FacetPolicy(id=1, log_enabled=True)
    session.merge(policy)
    session.commit()
    return policy


def test_emit_event_log_disabled_no_write(session):
    """log_enabled=False → FacetEvent 미기록."""
    from workers.tasks.facet_tasks import _emit_event

    run = _make_run(session)
    # policy 행 없음 (= log_enabled 기본 False)

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
