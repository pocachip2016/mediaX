import pytest
import httpx
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy.orm import Session

from api.meta_core.web_search.factory import get_provider_chain, search_with_fallback
from api.meta_core.web_search.base import WebSearchResult
from api.meta_core.web_search.errors import QuotaExhaustedError, ProviderUnavailableError


@pytest.fixture
def mock_quota_manager():
    """Mock QuotaManager."""
    manager = MagicMock()
    manager.is_allowed.return_value = True
    manager.current_count.return_value = 0
    return manager


@pytest.fixture
def mock_db():
    """Mock database session."""
    return MagicMock(spec=Session)


def test_get_provider_chain_default_order(mock_quota_manager):
    """Default provider order: brave, serpapi, gemini, ollama."""
    with patch("api.meta_core.web_search.factory.settings") as mock_settings:
        mock_settings.WEBSEARCH_PROVIDERS = "brave,serpapi,gemini,ollama"
        mock_settings.BRAVE_SEARCH_API_KEY = "key"
        mock_settings.SERPAPI_KEY = "key"
        mock_settings.GOOGLE_API_KEY = ""  # Skip gemini

        chain = get_provider_chain(quota_manager=mock_quota_manager)

    # Should have brave, serpapi (gemini skipped due to missing key), ollama
    assert len(chain) >= 2
    assert chain[0].provider_name == "brave"
    assert chain[1].provider_name == "serpapi"


def test_get_provider_chain_custom_order(mock_quota_manager):
    """Custom provider order via preference."""
    with patch("api.meta_core.web_search.factory.settings") as mock_settings:
        mock_settings.BRAVE_SEARCH_API_KEY = "key"
        mock_settings.SERPAPI_KEY = "key"
        mock_settings.GOOGLE_API_KEY = ""

        chain = get_provider_chain(
            quota_manager=mock_quota_manager,
            preference=["serpapi", "brave", "ollama"],
        )

    assert chain[0].provider_name == "serpapi"
    assert chain[1].provider_name == "brave"


@pytest.mark.asyncio
async def test_search_with_fallback_cache_hit(mock_db, mock_quota_manager):
    """Cache hit returns early without provider calls."""
    cached_results = [
        WebSearchResult(
            url="http://cached.com",
            title="Cached",
            snippet="From cache",
            source_domain="cached.com",
        )
    ]

    with patch("api.meta_core.web_search.factory.cache_get") as mock_cache_get, \
         patch("api.meta_core.web_search.factory.get_provider_chain") as mock_chain:

        mock_cache_get.return_value = cached_results
        mock_provider = MagicMock()
        mock_provider.provider_name = "brave"
        mock_chain.return_value = [mock_provider]

        results, provider_used = await search_with_fallback(
            "test query",
            mock_db,
            num=8,
            quota_manager=mock_quota_manager,
        )

    assert results == cached_results
    assert provider_used == "brave"
    mock_provider.search.assert_not_called()


@pytest.mark.asyncio
async def test_search_with_fallback_sequential_providers(
    mock_db, mock_quota_manager
):
    """First provider quota exhausted, second succeeds."""
    second_results = [
        WebSearchResult(
            url="http://serp.com",
            title="SerPAPI Result",
            snippet="From SerpAPI",
            source_domain="serp.com",
        )
    ]

    with patch("api.meta_core.web_search.factory.cache_get") as mock_cache_get, \
         patch("api.meta_core.web_search.factory.cache_put") as mock_cache_put, \
         patch("api.meta_core.web_search.factory.get_provider_chain") as mock_chain:

        mock_cache_get.return_value = None  # Cache miss

        # First provider (brave) exhausted
        brave_provider = AsyncMock()
        brave_provider.provider_name = "brave"
        brave_provider.search.side_effect = QuotaExhaustedError("brave", 0)

        # Second provider (serpapi) succeeds
        serpapi_provider = AsyncMock()
        serpapi_provider.provider_name = "serpapi"
        serpapi_provider.search.return_value = second_results

        mock_chain.return_value = [brave_provider, serpapi_provider]

        results, provider_used = await search_with_fallback(
            "test query",
            mock_db,
            num=8,
            quota_manager=mock_quota_manager,
        )

    assert results == second_results
    assert provider_used == "serpapi"
    brave_provider.search.assert_called_once()
    serpapi_provider.search.assert_called_once()
    mock_cache_put.assert_called_once()


@pytest.mark.asyncio
async def test_search_with_fallback_all_providers_fail(
    mock_db, mock_quota_manager
):
    """All providers fail, return empty list."""
    with patch("api.meta_core.web_search.factory.cache_get") as mock_cache_get, \
         patch("api.meta_core.web_search.factory.get_provider_chain") as mock_chain:

        mock_cache_get.return_value = None

        # All providers fail
        provider1 = AsyncMock()
        provider1.provider_name = "brave"
        provider1.search.side_effect = ProviderUnavailableError("brave", "API error")

        provider2 = AsyncMock()
        provider2.provider_name = "serpapi"
        provider2.search.side_effect = QuotaExhaustedError("serpapi", 0)

        mock_chain.return_value = [provider1, provider2]

        results, provider_used = await search_with_fallback(
            "test query",
            mock_db,
            num=8,
            quota_manager=mock_quota_manager,
        )

    assert results == []
    assert provider_used == "none"


@pytest.mark.asyncio
async def test_search_with_fallback_empty_chain(mock_db, mock_quota_manager):
    """No providers in chain, return empty."""
    with patch(
        "api.meta_core.web_search.factory.get_provider_chain"
    ) as mock_chain:
        mock_chain.return_value = []

        results, provider_used = await search_with_fallback(
            "test query",
            mock_db,
            num=8,
            quota_manager=mock_quota_manager,
        )

    assert results == []
    assert provider_used == "none"
