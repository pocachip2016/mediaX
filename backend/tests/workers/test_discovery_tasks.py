"""
discovery_tasks 단위 테스트

Celery task 를 직접 호출 (apply — 동기). Redis 불필요.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.database import Base, SessionLocal
import api.meta_core.models  # noqa
import api.programming.metadata.models  # noqa

from api.meta_core.models.seed import ContentSeed


@pytest.fixture(autouse=True)
def patch_session():
    """SessionLocal → in-memory SQLite."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with patch("workers.tasks.discovery_tasks.SessionLocal", Session):
        yield Session


# ── discover_tmdb ──────────────────────────────────────────────────────────────

def test_discover_tmdb_runs(patch_session):
    from workers.tasks.discovery_tasks import discover_tmdb
    from api.meta_core.discovery.tmdb_source import TmdbDiscoverySource

    mock_result = [
        MagicMock(source_type="tmdb", external_id="111", title="Test",
                  content_type="movie", production_year=2024,
                  original_title=None, poster_url=None, synopsis=None, raw={})
    ]
    with patch.object(TmdbDiscoverySource, "discover", return_value=iter(mock_result)):
        summary = discover_tmdb.apply(args=["trending_day"]).get()

    assert summary["new_seeds"] == 1
    assert summary["total"] == 1


def test_discover_tmdb_empty_returns_zero(patch_session):
    from workers.tasks.discovery_tasks import discover_tmdb
    from api.meta_core.discovery.tmdb_source import TmdbDiscoverySource

    with patch.object(TmdbDiscoverySource, "discover", return_value=iter([])):
        summary = discover_tmdb.apply(args=["trending_day"]).get()

    assert summary["new_seeds"] == 0


# ── discover_kobis ─────────────────────────────────────────────────────────────

def test_discover_kobis_runs(patch_session):
    from workers.tasks.discovery_tasks import discover_kobis
    from api.meta_core.discovery.kobis_source import KobisDiscoverySource

    mock_result = [
        MagicMock(source_type="kobis", external_id="K001", title="한국영화",
                  content_type="movie", production_year=2024,
                  original_title=None, poster_url=None, synopsis=None, raw={})
    ]
    with patch.object(KobisDiscoverySource, "discover", return_value=iter(mock_result)):
        summary = discover_kobis.apply(args=["box_office_daily"]).get()

    assert summary["total"] == 1


# ── discover_kmdb ──────────────────────────────────────────────────────────────

def test_discover_kmdb_runs(patch_session):
    from workers.tasks.discovery_tasks import discover_kmdb
    from api.meta_core.discovery.kmdb_source import KmdbDiscoverySource

    mock_result = [
        MagicMock(source_type="kmdb", external_id="KMD001", title="한국영화",
                  content_type="movie", production_year=2024,
                  original_title=None, poster_url=None, synopsis=None, raw={})
    ]
    with patch.object(KmdbDiscoverySource, "discover", return_value=iter(mock_result)):
        summary = discover_kmdb.apply(kwargs={"mode": "new_release", "days": 7}).get()

    assert summary["total"] == 1


# ── discover_all_daily ─────────────────────────────────────────────────────────

def test_discover_all_daily_returns_group_id(patch_session):
    from workers.tasks.discovery_tasks import discover_all_daily

    with patch("workers.tasks.discovery_tasks.group") as mock_group:
        mock_result = MagicMock()
        mock_result.id = "test-group-id"
        mock_group.return_value.apply_async.return_value = mock_result

        result = discover_all_daily.apply().get()

    assert "group_id" in result
