import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from api.meta_core.discovery.websearch_source import WebSearchDiscoverySource
from api.meta_core.web_search.base import WebSearchResult


@pytest.fixture
def mock_db():
    """Mock database session."""
    return MagicMock()


@pytest.fixture
def websearch_source(mock_db):
    """WebSearchDiscoverySource instance."""
    return WebSearchDiscoverySource(db=mock_db)


@pytest.fixture
def sample_search_results():
    """Sample web search results."""
    return [
        WebSearchResult(
            url="http://example.com/movie1",
            title="New Korean Drama 2026",
            snippet="A new Korean drama about love and family. Starring actor A and B.",
            source_domain="example.com",
            score=1.0,
        ),
        WebSearchResult(
            url="http://example.com/movie2",
            title="Sci-Fi Movie Release",
            snippet="An upcoming sci-fi movie with action and adventure. Release date 2026.",
            source_domain="example.com",
            score=0.9,
        ),
    ]


@pytest.mark.asyncio
async def test_discover_query_mode(websearch_source, sample_search_results):
    """Test query mode discovery."""
    with patch(
        "api.meta_core.discovery.websearch_source.search_with_fallback"
    ) as mock_search, patch.object(
        websearch_source, "_extract_with_llm"
    ) as mock_extract:

        mock_search.return_value = (sample_search_results, "brave")

        # Mock LLM extraction
        mock_result1 = MagicMock()
        mock_result1.title = "New Drama"
        mock_result1.content_type = "series"
        mock_result1.production_year = 2026

        mock_extract.side_effect = [mock_result1, None]

        results = await websearch_source._discover_async(
            "query", query="Korean drama 2026"
        )

    assert len(results) == 1
    assert results[0].title == "New Drama"
    mock_search.assert_called_once()


@pytest.mark.asyncio
async def test_discover_topic_mode(websearch_source, sample_search_results):
    """Test topic mode discovery."""
    with patch(
        "api.meta_core.discovery.websearch_source.search_with_fallback"
    ) as mock_search:

        mock_search.return_value = (sample_search_results, "serpapi")

        results = await websearch_source._discover_async(
            "topic", topic="OTT exclusive movies"
        )

    # Should call search_with_fallback with combined query
    mock_search.assert_called_once()
    call_args = mock_search.call_args[0][0]
    assert "OTT exclusive movies" in call_args


@pytest.mark.asyncio
async def test_discover_trending_mode(websearch_source):
    """Test trending mode with 5 predefined queries."""
    with patch(
        "api.meta_core.discovery.websearch_source.search_with_fallback"
    ) as mock_search:

        mock_search.return_value = ([], "brave")

        results = await websearch_source._discover_async("trending")

    # Should call search_with_fallback 5 times (one per query)
    assert mock_search.call_count == 5


def test_parse_extraction_response(websearch_source):
    """Test LLM response JSON parsing."""
    response = """
    Based on the search result, here's the extracted information:
    {
        "title": "Drama Title",
        "original_title": "드라마 제목",
        "content_type": "series",
        "production_year": 2026,
        "confidence": 0.85
    }
    """

    parsed = websearch_source._parse_extraction_response(response)

    assert parsed is not None
    assert parsed["title"] == "Drama Title"
    assert parsed["content_type"] == "series"
    assert parsed["production_year"] == 2026
    assert parsed["confidence"] == 0.85


def test_parse_extraction_response_invalid_json(websearch_source):
    """Test parsing invalid JSON response."""
    response = "Unable to parse the content"

    parsed = websearch_source._parse_extraction_response(response)

    assert parsed is None


@pytest.mark.asyncio
async def test_discover_sync_interface(websearch_source):
    """Test synchronous discover() interface."""
    with patch.object(
        websearch_source, "_discover_async"
    ) as mock_async:

        mock_async.return_value = []

        # Call synchronous discover
        result = websearch_source.discover("query", query="test")

        assert isinstance(result, type(iter([])))
        mock_async.assert_called_once_with("query", query="test")
