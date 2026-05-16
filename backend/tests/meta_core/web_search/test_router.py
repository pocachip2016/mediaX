import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from api.meta_core.web_search.router import router, ProviderQuotaOut, QuotaStatsOut
from api.meta_core.web_search.router import CacheStatsOut, RecentCallsOut


@pytest.fixture
def mock_db():
    """Mock database session."""
    return MagicMock()


@pytest.fixture
def mock_quota_manager():
    """Mock QuotaManager."""
    mgr = MagicMock()
    mgr.current_count.return_value = 30
    return mgr


def test_quota_stats_schema():
    """Test QuotaStatsOut schema."""
    provider = ProviderQuotaOut(
        provider="brave",
        daily_limit=60,
        used_today=30,
        remaining=30,
        percent_used=50.0,
    )
    assert provider.provider == "brave"
    assert provider.remaining == 30


def test_cache_stats_schema():
    """Test CacheStatsOut schema."""
    stats = CacheStatsOut(
        period_days=7,
        total_queries=100,
        cache_hits=70,
        cache_misses=30,
        hit_rate=0.7,
        by_provider=[{"provider": "brave", "hits": 70, "misses": 0}],
    )
    assert stats.hit_rate == 0.7
    assert stats.total_queries == 100


def test_recent_calls_schema():
    """Test RecentCallsOut schema."""
    calls = RecentCallsOut(
        total=0,
        limit=50,
        calls=[],
    )
    assert calls.limit == 50


def test_get_quota_endpoint(mock_db):
    """Test GET /quota endpoint."""
    from fastapi import FastAPI
    from shared.database import get_db

    app = FastAPI()
    app.include_router(router)

    # Override get_db dependency
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)

    with patch("api.meta_core.web_search.router.QuotaManager") as mock_qm_class:
        mock_qm = MagicMock()
        mock_qm.current_count.return_value = 30
        mock_qm_class.return_value = mock_qm

        with patch("api.meta_core.web_search.router.settings") as mock_settings:
            mock_settings.WEBSEARCH_BRAVE_DAILY = 60
            mock_settings.WEBSEARCH_SERPAPI_DAILY = 3
            mock_settings.WEBSEARCH_GEMINI_DAILY = 200

            response = client.get("/web-search/quota")

    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    assert "as_of" in data
    assert len(data["providers"]) >= 3


def test_get_cache_stats_endpoint(mock_db):
    """Test GET /cache-stats endpoint."""
    from fastapi import FastAPI
    from shared.database import get_db

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: mock_db

    # Mock WebSearchCache query
    mock_db.query().filter().count.return_value = 100
    mock_db.query().filter().all.return_value = []

    client = TestClient(app)
    response = client.get("/web-search/cache-stats?days=7")

    assert response.status_code == 200
    data = response.json()
    assert data["period_days"] == 7
    assert "total_queries" in data


def test_get_recent_endpoint(mock_db):
    """Test GET /recent endpoint."""
    from fastapi import FastAPI
    from shared.database import get_db

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: mock_db

    # Mock ExternalSyncLog query
    mock_log = MagicMock()
    mock_log.source = "websearch"
    mock_log.created_at = datetime.utcnow()
    mock_log.remarks = "test query"
    mock_log.status = "completed"

    mock_db.query().filter().order_by().limit().all.return_value = [mock_log]

    client = TestClient(app)
    response = client.get("/web-search/recent?limit=50")

    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 50
    assert "calls" in data
