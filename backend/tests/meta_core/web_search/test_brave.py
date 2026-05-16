import pytest
import httpx
from unittest.mock import MagicMock, AsyncMock, patch

from api.meta_core.web_search.brave import BraveSearchProvider
from api.meta_core.web_search.errors import QuotaExhaustedError, ProviderUnavailableError


@pytest.fixture
def mock_quota_manager():
    """Mock QuotaManager."""
    manager = MagicMock()
    manager.is_allowed.return_value = True
    manager.current_count.return_value = 5
    return manager


@pytest.fixture
def brave_provider(mock_quota_manager):
    """BraveSearchProvider with mocked QuotaManager."""
    with patch("api.meta_core.web_search.brave.settings") as mock_settings:
        mock_settings.BRAVE_SEARCH_API_KEY = "test-key-123"
        mock_settings.WEBSEARCH_BRAVE_DAILY = 60
        return BraveSearchProvider(quota_manager=mock_quota_manager)


@pytest.mark.asyncio
async def test_brave_search_success(brave_provider, mock_quota_manager):
    """Normal search with valid results."""
    mock_response_json = {
        "web": {
            "results": [
                {
                    "url": "https://imdb.com/title/tt1234567/",
                    "title": "Movie Title",
                    "description": "A brief description of the movie.",
                },
                {
                    "url": "https://www.wikipedia.org/wiki/Movie",
                    "title": "Movie - Wikipedia",
                    "description": "Wikipedia article about the movie.",
                },
            ]
        }
    }

    with patch("api.meta_core.web_search.brave.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_json
        mock_client.__aenter__.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_response)

        mock_client_class.return_value = mock_client

        results = await brave_provider.search("test movie 2026", num=8)

    assert len(results) == 2
    assert results[0].url == "https://imdb.com/title/tt1234567/"
    assert results[0].title == "Movie Title"
    assert results[0].snippet == "A brief description of the movie."
    assert results[0].source_domain == "imdb.com"
    assert results[0].score == 1.0

    assert results[1].url == "https://www.wikipedia.org/wiki/Movie"
    assert results[1].title == "Movie - Wikipedia"
    assert results[1].source_domain == "wikipedia.org"

    # Verify quota check was called
    mock_quota_manager.is_allowed.assert_called_once_with("websearch:brave", 60)


@pytest.mark.asyncio
async def test_brave_quota_exhausted(brave_provider, mock_quota_manager):
    """Quota exhausted before API call."""
    mock_quota_manager.is_allowed.return_value = False
    mock_quota_manager.current_count.return_value = 60

    with pytest.raises(QuotaExhaustedError) as exc_info:
        await brave_provider.search("test query")

    assert exc_info.value.provider == "brave"
    assert exc_info.value.remaining == 0


@pytest.mark.asyncio
async def test_brave_rate_limit_429(brave_provider, mock_quota_manager):
    """API returns 429 rate limit."""
    mock_quota_manager.current_count.return_value = 50

    with patch("api.meta_core.web_search.brave.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock(status_code=429)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=MagicMock(),
            response=mock_response,
        )
        mock_client.__aenter__.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_response)

        mock_client_class.return_value = mock_client

        with pytest.raises(QuotaExhaustedError) as exc_info:
            await brave_provider.search("test query")

        assert exc_info.value.provider == "brave"
        assert exc_info.value.remaining == 10  # 60 - 50


@pytest.mark.asyncio
async def test_brave_api_error_500(brave_provider):
    """API returns 500 error."""
    with patch("api.meta_core.web_search.brave.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock(status_code=500)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=MagicMock(),
            response=mock_response,
        )
        mock_client.__aenter__.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_response)

        mock_client_class.return_value = mock_client

        with pytest.raises(ProviderUnavailableError) as exc_info:
            await brave_provider.search("test query")

        assert exc_info.value.provider == "brave"


@pytest.mark.asyncio
async def test_brave_no_api_key():
    """API key not configured."""
    with patch("api.meta_core.web_search.brave.settings") as mock_settings:
        mock_settings.BRAVE_SEARCH_API_KEY = ""
        mock_settings.WEBSEARCH_BRAVE_DAILY = 60
        provider = BraveSearchProvider(quota_manager=MagicMock())

        with pytest.raises(ProviderUnavailableError) as exc_info:
            await provider.search("test query")

        assert "API key not configured" in str(exc_info.value)


def test_provider_properties(brave_provider):
    """Test provider metadata."""
    assert brave_provider.provider_name == "brave"
    assert brave_provider.daily_limit == 60
