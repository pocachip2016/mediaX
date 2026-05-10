"""
KobisDiscoverySource 단위 테스트

mock httpx — 실제 KOBIS API 호출 없음.
DB 는 인메모리 SQLite.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shared.database import Base
import api.meta_core.models  # noqa

from api.meta_core.discovery.kobis_source import KobisDiscoverySource, _movie_to_result, _boxoffice_to_result
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


_MOVIE = {
    "movieCd": "20250001",
    "movieNm": "테스트 영화",
    "movieNmEn": "Test Movie",
    "prdtYear": "2025",
    "openDt": "20250301",
    "watchGradeNm": "15세이상관람가",
    "prdtTypeNm": "장편",
    "prdtStatNm": "개봉예정",
    "repNationNm": "한국",
}
_ADULT_MOVIE = {**_MOVIE, "movieCd": "20259999", "movieNm": "성인 영화", "watchGradeNm": "청소년관람불가"}
_SHORT_MOVIE = {**_MOVIE, "movieCd": "20258888", "movieNm": "단편 영화", "prdtTypeNm": "단편"}
_BOXOFFICE = {"movieCd": "20250001", "movieNm": "테스트 영화", "rank": "1"}


# ── _movie_to_result 변환 테스트 ──────────────────────────────────────────────

def test_movie_to_result_basic():
    r = _movie_to_result(_MOVIE)
    assert r is not None
    assert r.source_type == "kobis"
    assert r.external_id == "20250001"
    assert r.content_type == "movie"
    assert r.production_year == 2025
    assert r.poster_url is None
    assert r.synopsis is None


def test_adult_movie_excluded():
    assert _movie_to_result(_ADULT_MOVIE) is None


def test_short_movie_excluded():
    assert _movie_to_result(_SHORT_MOVIE) is None


def test_missing_movie_cd_excluded():
    assert _movie_to_result({**_MOVIE, "movieCd": ""}) is None


def test_year_null_allowed():
    """production_year NULL 허용 — discard 금지."""
    m = {**_MOVIE, "prdtYear": "", "openDt": ""}
    r = _movie_to_result(m)
    assert r is not None
    assert r.production_year is None


# ── mode 별 discover 테스트 ───────────────────────────────────────────────────

def _make_source_with_mock(mock_get_return: dict):
    """KobisClient._get 을 mock 한 source 반환."""
    source = KobisDiscoverySource(api_key="fake_key")
    source._client._get = MagicMock(return_value=mock_get_return)
    return source


def test_upcoming_mode():
    source = _make_source_with_mock(
        {"movieListResult": {"movieList": [_MOVIE, _ADULT_MOVIE]}}
    )
    results = list(source.discover("upcoming"))
    assert len(results) == 1
    assert results[0].external_id == "20250001"


def test_box_office_daily_mode():
    source = _make_source_with_mock(
        {"boxOfficeResult": {"dailyBoxOfficeList": [_BOXOFFICE]}}
    )
    results = list(source.discover("box_office_daily"))
    assert len(results) == 1
    assert results[0].external_id == "20250001"


def test_box_office_weekly_mode():
    source = _make_source_with_mock(
        {"boxOfficeResult": {"weeklyBoxOfficeList": [_BOXOFFICE]}}
    )
    results = list(source.discover("box_office_weekly"))
    assert len(results) == 1


def test_new_release_mode():
    source = _make_source_with_mock(
        {"movieListResult": {"movieList": [_MOVIE]}}
    )
    results = list(source.discover("new_release"))
    assert len(results) == 1


def test_empty_response():
    source = _make_source_with_mock({"movieListResult": {"movieList": []}})
    results = list(source.discover("upcoming"))
    assert results == []


def test_missing_api_key_returns_empty():
    source = KobisDiscoverySource(api_key="")
    results = list(source.discover("upcoming"))
    assert results == []


# ── run_discovery 연동 ───────────────────────────────────────────────────────

def test_run_discovery_kobis(db):
    source = KobisDiscoverySource(api_key="fake_key")
    source._client._get = MagicMock(
        return_value={"movieListResult": {"movieList": [_MOVIE]}}
    )
    summary = run_discovery(db, source, "upcoming")
    assert summary["new_seeds"] == 1
    assert db.query(ContentSeed).count() == 1
    assert db.query(SeedDiscoveryLog).count() == 1
    seed = db.query(ContentSeed).first()
    assert seed.source_type == "kobis"
    assert seed.content_type == "movie"
