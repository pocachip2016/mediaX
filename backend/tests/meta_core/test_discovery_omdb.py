"""
OmdbDiscoverySource + omdb_client 단위 테스트

mock OmdbClient._get — 실제 OMDb API 호출 없음.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shared.database import Base
import api.meta_core.models  # noqa

from api.meta_core.discovery.omdb_source import OmdbDiscoverySource, _item_to_result
from api.meta_core.discovery.runner import run_discovery
from api.meta_core.models.seed import ContentSeed, SeedDiscoveryLog


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


_MOVIE_DETAIL = {
    "imdbID": "tt1375666",
    "Title": "Inception",
    "Year": "2010",
    "Type": "movie",
    "Poster": "https://example.com/poster.jpg",
    "Plot": "A thief who steals corporate secrets.",
    "Response": "True",
}

_SERIES_DETAIL = {
    "imdbID": "tt0903747",
    "Title": "Breaking Bad",
    "Year": "2008",
    "Type": "series",
    "Poster": "N/A",
    "Plot": "N/A",
    "Response": "True",
}

_SEARCH_RESULTS = {
    "Search": [
        {"imdbID": "tt1375666", "Title": "Inception", "Year": "2010", "Type": "movie", "Poster": "https://example.com/poster.jpg"},
        {"imdbID": "tt0816692", "Title": "Interstellar", "Year": "2014", "Type": "movie", "Poster": "N/A"},
    ],
    "totalResults": "2",
    "Response": "True",
}


# ── _item_to_result 변환 ─────────────────────────────────────────────────────

def test_movie_detail_to_result():
    r = _item_to_result(_MOVIE_DETAIL)
    assert r is not None
    assert r.source_type == "omdb"
    assert r.external_id == "tt1375666"
    assert r.title == "Inception"
    assert r.content_type == "movie"
    assert r.production_year == 2010
    assert r.poster_url == "https://example.com/poster.jpg"
    assert r.synopsis == "A thief who steals corporate secrets."


def test_series_type_mapped():
    r = _item_to_result(_SERIES_DETAIL)
    assert r is not None
    assert r.content_type == "series"
    assert r.poster_url is None    # N/A → None
    assert r.synopsis is None      # N/A → None


def test_missing_imdb_id_excluded():
    assert _item_to_result({**_MOVIE_DETAIL, "imdbID": ""}) is None


def test_missing_title_excluded():
    assert _item_to_result({**_MOVIE_DETAIL, "Title": ""}) is None


def test_year_partial_string():
    r = _item_to_result({**_MOVIE_DETAIL, "Year": "2010-2012"})
    assert r is not None
    assert r.production_year == 2010  # 앞 4자리만


def test_non_digit_year():
    r = _item_to_result({**_MOVIE_DETAIL, "Year": "N/A"})
    assert r is not None
    assert r.production_year is None


def test_episode_type_mapped_to_series():
    r = _item_to_result({**_MOVIE_DETAIL, "Type": "episode"})
    assert r is not None
    assert r.content_type == "series"


# ── OmdbDiscoverySource — by_imdb_id mode ────────────────────────────────────

def _make_source(get_return: dict) -> OmdbDiscoverySource:
    source = OmdbDiscoverySource(api_key="fake_key")
    source._client._get = MagicMock(return_value=get_return)
    return source


def test_by_imdb_id_single():
    source = _make_source(_MOVIE_DETAIL)
    results = list(source.discover("by_imdb_id", imdb_ids=["tt1375666"]))
    assert len(results) == 1
    assert results[0].external_id == "tt1375666"


def test_by_imdb_id_empty_response():
    source = _make_source({})
    results = list(source.discover("by_imdb_id", imdb_ids=["tt9999999"]))
    assert results == []


def test_by_imdb_id_empty_list():
    source = _make_source(_MOVIE_DETAIL)
    results = list(source.discover("by_imdb_id", imdb_ids=[]))
    assert results == []
    source._client._get.assert_not_called()


# ── OmdbDiscoverySource — search_title mode ──────────────────────────────────

def test_search_title_returns_multiple():
    source = OmdbDiscoverySource(api_key="fake_key")
    source._client._get = MagicMock(return_value=_SEARCH_RESULTS)
    results = list(source.discover("search_title", title="Inception"))
    assert len(results) == 2
    assert results[0].external_id == "tt1375666"


def test_search_title_na_poster_is_none():
    source = OmdbDiscoverySource(api_key="fake_key")
    source._client._get = MagicMock(return_value=_SEARCH_RESULTS)
    results = list(source.discover("search_title", title="Interstellar"))
    inter = next(r for r in results if r.external_id == "tt0816692")
    assert inter.poster_url is None


def test_search_title_empty_title_returns_empty():
    source = OmdbDiscoverySource(api_key="fake_key")
    source._client._get = MagicMock(return_value=_SEARCH_RESULTS)
    results = list(source.discover("search_title", title=""))
    assert results == []
    source._client._get.assert_not_called()


def test_missing_api_key_returns_empty():
    source = OmdbDiscoverySource(api_key="")
    results = list(source.discover("search_title", title="Inception"))
    assert results == []


# ── run_discovery 연동 ───────────────────────────────────────────────────────

def test_run_discovery_omdb_by_imdb_id(db):
    source = OmdbDiscoverySource(api_key="fake_key")
    source._client._get = MagicMock(return_value=_MOVIE_DETAIL)
    summary = run_discovery(db, source, "by_imdb_id", imdb_ids=["tt1375666"])
    assert summary["new_seeds"] == 1
    assert db.query(ContentSeed).count() == 1
    seed = db.query(ContentSeed).first()
    assert seed.source_type == "omdb"
    assert seed.synopsis == "A thief who steals corporate secrets."
    assert db.query(SeedDiscoveryLog).count() == 1


def test_run_discovery_omdb_search_title(db):
    source = OmdbDiscoverySource(api_key="fake_key")
    source._client._get = MagicMock(return_value=_SEARCH_RESULTS)
    summary = run_discovery(db, source, "search_title", title="Inception")
    assert summary["new_seeds"] == 2
    assert db.query(ContentSeed).count() == 2
    assert db.query(SeedDiscoveryLog).count() == 1
