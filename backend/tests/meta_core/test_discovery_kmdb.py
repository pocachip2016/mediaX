"""
KmdbDiscoverySource + kmdb_client 확장 단위 테스트

mock KmdbClient._get — 실제 KMDB API 호출 없음.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shared.database import Base
import api.meta_core.models  # noqa

from api.meta_core.discovery.kmdb_source import (
    KmdbDiscoverySource, _clean, _first_poster, _synopsis, _original_title, _item_to_result,
)
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


_MOVIE_ITEM = {
    "DOCID": "KMD12345",
    "title": "테스트 <br>영화",
    "titleEng": "Test Movie",
    "prodYear": "2025",
    "posters": "https://img1.jpg|https://img2.jpg",
    "plots": {"plot": [
        {"plotLang": "한국어", "plotText": "한국어 시놉시스"},
        {"plotLang": "영어", "plotText": "English synopsis"},
    ]},
}

_DRAMA_ITEM = {
    "DOCID": "KMD99999",
    "title": "테스트 드라마",
    "titleEng": "Test Drama",
    "prodYear": "2024",
    "posters": "",
    "plots": {"plot": []},
}

_FAKE_ENG_ITEM = {
    **_MOVIE_ITEM,
    "DOCID": "KMD77777",
    "title": "동일제목",
    "titleEng": "동일제목",  # 영문 제목 = 한국어 제목 → 가짜
}

_KMDB_RESPONSE = {
    "Data": [{"Result": [_MOVIE_ITEM], "TotalCount": 1}]
}


# ── 유틸 함수 테스트 ─────────────────────────────────────────────────────────

def test_clean_html_tags():
    assert _clean("테스트 <br>영화") == "테스트 영화"

def test_clean_kmdb_markers():
    assert _clean("!HS테스트!HE") == "테스트"

def test_clean_none():
    assert _clean(None) is None

def test_first_poster_pipe_separated():
    assert _first_poster("https://a.jpg|https://b.jpg") == "https://a.jpg"

def test_first_poster_none():
    assert _first_poster(None) is None
    assert _first_poster("") is None

def test_synopsis_korean_preferred():
    result = _synopsis(_MOVIE_ITEM)
    assert result == "한국어 시놉시스"

def test_synopsis_empty_plot():
    assert _synopsis(_DRAMA_ITEM) is None

def test_original_title_excluded_when_same():
    result = _original_title(_FAKE_ENG_ITEM)
    assert result is None

def test_original_title_returns_eng():
    result = _original_title(_MOVIE_ITEM)
    assert result == "Test Movie"


# ── _item_to_result 변환 ─────────────────────────────────────────────────────

def test_movie_to_result():
    r = _item_to_result(_MOVIE_ITEM, "movie")
    assert r is not None
    assert r.source_type == "kmdb"
    assert r.external_id == "KMD12345"
    assert r.title == "테스트 영화"      # HTML 태그 제거됨
    assert r.content_type == "movie"
    assert r.production_year == 2025
    assert r.poster_url == "https://img1.jpg"
    assert r.synopsis == "한국어 시놉시스"

def test_drama_content_type():
    r = _item_to_result(_DRAMA_ITEM, "series")
    assert r is not None
    assert r.content_type == "series"
    assert r.poster_url is None

def test_missing_docid_excluded():
    assert _item_to_result({**_MOVIE_ITEM, "DOCID": ""}, "movie") is None


# ── KmdbDiscoverySource mode 테스트 ──────────────────────────────────────────

def _make_source(get_return: dict) -> KmdbDiscoverySource:
    source = KmdbDiscoverySource(api_key="fake_key")
    source._client._get = MagicMock(return_value=get_return)
    return source


def test_new_release_mode():
    source = _make_source(_KMDB_RESPONSE)
    results = list(source.discover("new_release"))
    assert len(results) == 1
    assert results[0].content_type == "movie"


def test_discover_drama_mode():
    drama_resp = {"Data": [{"Result": [_DRAMA_ITEM], "TotalCount": 1}]}
    source = _make_source(drama_resp)
    results = list(source.discover("discover_drama"))
    assert len(results) == 1
    assert results[0].content_type == "series"


def test_empty_response():
    source = _make_source({"Data": [{"Result": [], "TotalCount": 0}]})
    results = list(source.discover("new_release"))
    assert results == []


def test_missing_api_key_returns_empty():
    source = KmdbDiscoverySource(api_key="")
    results = list(source.discover("new_release"))
    assert results == []


# ── run_discovery 연동 ───────────────────────────────────────────────────────

def test_run_discovery_kmdb(db):
    source = KmdbDiscoverySource(api_key="fake_key")
    source._client._get = MagicMock(return_value=_KMDB_RESPONSE)
    summary = run_discovery(db, source, "new_release")
    assert summary["new_seeds"] == 1
    assert db.query(ContentSeed).count() == 1
    seed = db.query(ContentSeed).first()
    assert seed.source_type == "kmdb"
    assert seed.synopsis == "한국어 시놉시스"
    assert db.query(SeedDiscoveryLog).count() == 1
