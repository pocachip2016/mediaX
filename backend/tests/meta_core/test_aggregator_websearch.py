import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

from api.meta_core.aggregator import aggregate_content
from api.meta_core.models.intelligence import FieldSuggestion
from api.programming.metadata.models.external import ExternalSourceType


@pytest.fixture
def mock_db():
    """Mock database session."""
    return MagicMock()


@pytest.fixture
def mock_content():
    """Mock Content object."""
    content = MagicMock()
    content.id = 1
    content.title = "Test Movie"
    content.production_year = 2026
    metadata = MagicMock()
    metadata.synopsis = ""
    content.metadata = metadata
    return content


def test_aggregate_content_websearch_disabled(mock_db):
    """Default: enable_web_search=False, WebSearch not called."""
    with patch(
        "api.meta_core.aggregator._add_websearch_suggestions"
    ) as mock_add_websearch:
        mock_db.query().filter().all.return_value = []

        result = aggregate_content(1, mock_db, enable_web_search=False)

        mock_add_websearch.assert_not_called()


def test_aggregate_content_websearch_enabled(mock_db):
    """enable_web_search=True, WebSearch suggestions added."""
    with patch(
        "api.meta_core.aggregator._add_websearch_suggestions"
    ) as mock_add_websearch:
        mock_db.query().filter().all.return_value = []

        result = aggregate_content(1, mock_db, enable_web_search=True)

        mock_add_websearch.assert_called_once_with(1, mock_db)


def test_add_websearch_suggestions_no_empty_fields(mock_db, mock_content):
    """No empty fields, no WebSearch."""
    # Set non-empty synopsis
    mock_content.metadata.synopsis = "Existing synopsis"
    mock_db.query().filter().first.return_value = mock_content

    from api.meta_core.aggregator import _add_websearch_suggestions

    _add_websearch_suggestions(1, mock_db)

    # No search should happen
    mock_db.add.assert_not_called()


@pytest.mark.asyncio
async def test_add_websearch_suggestions_with_results(mock_db, mock_content):
    """Empty synopsis, WebSearch results found."""
    from api.meta_core.aggregator import _add_websearch_suggestions
    from api.meta_core.web_search.base import WebSearchResult

    mock_db.query().filter().first.return_value = mock_content

    search_results = [
        WebSearchResult(
            url="http://example.com",
            title="Test",
            snippet="A great movie about love and adventure.",
            source_domain="example.com",
            score=1.0,
        )
    ]

    with patch(
        "api.meta_core.aggregator.asyncio.run"
    ) as mock_asyncio_run:
        mock_asyncio_run.return_value = (search_results, "brave")

        with patch(
            "api.meta_core.aggregator._create_websearch_suggestion"
        ) as mock_create:
            _add_websearch_suggestions(1, mock_db)

            mock_create.assert_called_once()
            call_args = mock_create.call_args[0]
            assert call_args[0] == 1  # content_id
            assert call_args[1] == "synopsis"  # field_name


def test_create_websearch_suggestion_llm_extraction(mock_db):
    """LLM extraction -> FieldSuggestion created."""
    from api.meta_core.aggregator import _create_websearch_suggestion
    from api.meta_core.web_search.base import WebSearchResult

    search_results = [
        WebSearchResult(
            url="http://example.com",
            title="Test",
            snippet="A great movie.",
            source_domain="example.com",
            score=1.0,
        )
    ]

    with patch(
        "api.meta_core.aggregator.asyncio.run"
    ) as mock_asyncio_run:
        mock_asyncio_run.return_value = "Extracted synopsis text"

        _create_websearch_suggestion(1, "synopsis", search_results, mock_db)

        # Verify FieldSuggestion was added
        mock_db.add.assert_called_once()
        suggestion = mock_db.add.call_args[0][0]

        assert suggestion.content_id == 1
        assert suggestion.field_name == "synopsis"
        assert suggestion.value_json == "Extracted synopsis text"
        assert suggestion.source_type == ExternalSourceType.websearch
        assert suggestion.confidence_score == 0.5
        assert suggestion.status == "pending"


def test_create_websearch_suggestion_empty_extraction(mock_db):
    """LLM returns empty, no FieldSuggestion."""
    from api.meta_core.aggregator import _create_websearch_suggestion
    from api.meta_core.web_search.base import WebSearchResult

    search_results = [
        WebSearchResult(
            url="http://example.com",
            title="Test",
            snippet="Minimal text",
            source_domain="example.com",
            score=1.0,
        )
    ]

    with patch(
        "api.meta_core.aggregator.asyncio.run"
    ) as mock_asyncio_run:
        mock_asyncio_run.return_value = ""  # Empty extraction

        _create_websearch_suggestion(1, "synopsis", search_results, mock_db)

        # No FieldSuggestion added
        mock_db.add.assert_not_called()
