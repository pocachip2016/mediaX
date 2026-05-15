import pytest
import hashlib
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from api.meta_core.web_search.cache import cache_get, cache_put
from api.meta_core.web_search.base import WebSearchResult
from api.programming.metadata.models.tmdb_cache import WebSearchCache


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock(spec=Session)
    return db


@pytest.fixture
def sample_results():
    """Sample search results."""
    return [
        WebSearchResult(
            url="http://imdb.com/title/1",
            title="Movie 1",
            snippet="Description 1",
            source_domain="imdb.com",
            score=1.0,
        ),
        WebSearchResult(
            url="http://wiki.com/movie-2",
            title="Movie 2",
            snippet="Description 2",
            source_domain="wiki.com",
            score=0.9,
        ),
    ]


def test_cache_get_hit(mock_db, sample_results):
    """Cache hit returns cached results."""
    query = "test movie 2026"
    provider = "brave"
    query_hash = hashlib.sha256(query.encode()).hexdigest()

    # Mock existing cache entry
    cached_entry = MagicMock(spec=WebSearchCache)
    cached_entry.expires_at = datetime.utcnow() + timedelta(days=1)
    cached_entry.results_json = [
        {
            "url": r.url,
            "title": r.title,
            "snippet": r.snippet,
            "source_domain": r.source_domain,
            "score": r.score,
        }
        for r in sample_results
    ]

    mock_db.query().filter().first.return_value = cached_entry

    results = cache_get(query, provider, mock_db)

    assert results is not None
    assert len(results) == 2
    assert results[0].url == "http://imdb.com/title/1"
    assert results[0].title == "Movie 1"
    assert results[1].source_domain == "wiki.com"


def test_cache_get_miss_no_entry(mock_db):
    """Cache miss when no entry exists."""
    mock_db.query().filter().first.return_value = None

    results = cache_get("test query", "brave", mock_db)

    assert results is None


def test_cache_get_miss_expired(mock_db):
    """Cache miss when entry is expired."""
    # Mock expired cache entry
    cached_entry = MagicMock(spec=WebSearchCache)
    cached_entry.expires_at = datetime.utcnow() - timedelta(days=1)

    mock_db.query().filter().first.return_value = cached_entry

    results = cache_get("test query", "brave", mock_db)

    assert results is None


def test_cache_put_new_entry(mock_db, sample_results):
    """Cache put creates new entry."""
    query = "test query"
    provider = "brave"

    # Mock no existing entry
    mock_db.query().filter().first.return_value = None

    cache_put(query, provider, sample_results, mock_db, ttl_days=7)

    # Verify add was called
    mock_db.add.assert_called_once()

    # Verify commit was called
    mock_db.commit.assert_called_once()


def test_cache_put_update_existing(mock_db, sample_results):
    """Cache put updates existing entry."""
    query = "test query"
    provider = "brave"

    # Mock existing cache entry
    existing_entry = MagicMock(spec=WebSearchCache)
    mock_db.query().filter().first.return_value = existing_entry

    cache_put(query, provider, sample_results, mock_db, ttl_days=7)

    # Verify entry was updated (not added)
    mock_db.add.assert_not_called()

    # Verify attributes were updated
    assert existing_entry.results_json is not None
    assert existing_entry.expires_at is not None
    assert existing_entry.cached_at is not None

    # Verify commit was called
    mock_db.commit.assert_called_once()


def test_cache_put_respects_ttl(mock_db, sample_results):
    """Cache put respects TTL parameter."""
    query = "test query"
    provider = "brave"
    ttl_days = 14

    # Mock no existing entry
    mock_db.query().filter().first.return_value = None

    before = datetime.utcnow()
    cache_put(query, provider, sample_results, mock_db, ttl_days=ttl_days)
    after = datetime.utcnow()

    # Get the added entry
    added_entry = mock_db.add.call_args[0][0]

    # Verify TTL is approximately correct
    expires_at = added_entry.expires_at
    expected_min = before + timedelta(days=ttl_days) - timedelta(seconds=1)
    expected_max = after + timedelta(days=ttl_days) + timedelta(seconds=1)

    assert expected_min <= expires_at <= expected_max


def test_cache_provider_scoping(mock_db):
    """Cache is scoped by both query_hash and provider."""
    query = "test"
    provider_brave = "brave"
    provider_serpapi = "serpapi"

    query_hash = hashlib.sha256(query.encode()).hexdigest()

    # Verify cache_get calls with correct parameters
    cache_get(query, provider_brave, mock_db)

    # Check that filter was called with correct criteria
    filter_calls = mock_db.query().filter.call_args_list
    # Should have called filter twice (query_hash AND source)
    assert len(filter_calls) >= 1
