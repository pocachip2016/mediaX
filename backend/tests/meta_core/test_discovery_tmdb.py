"""
TmdbDiscoverySource + run_discovery 단위 테스트

mock httpx — 실제 TMDB API 호출 없음.
DB 는 인메모리 SQLite 사용.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shared.database import Base
import api.meta_core.models  # noqa — 모든 테이블 등록

from api.meta_core.discovery.base import DiscoveryResult, DiscoverySource
from api.meta_core.discovery.tmdb_source import TmdbDiscoverySource, _year, _poster
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


def _page(results: list[dict], total_pages: int = 1) -> dict:
    return {"results": results, "total_pages": total_pages, "page": 1}


_MOVIE = {
    "id": 1001, "title": "테스트 영화", "original_title": "Test Movie",
    "release_date": "2025-03-15", "poster_path": "/abc.jpg",
    "overview": "시놉시스", "adult": False,
}
_TV = {
    "id": 2001, "name": "테스트 시리즈", "original_name": "Test Series",
    "first_air_date": "2025-01-01", "poster_path": "/def.jpg",
    "overview": "시리즈 설명", "adult": False,
}
_ADULT_MOVIE = {**_MOVIE, "id": 9999, "adult": True, "title": "성인 영화"}


# ── helper: 빈 응답 mock ─────────────────────────────────────────────────────

def _make_source(api_responses: dict) -> TmdbDiscoverySource:
    """api_responses: {path_suffix: response_dict} — _get path 기반 매핑."""
    source = TmdbDiscoverySource(api_key="fake_key", max_pages=1)
    return source


# ── 유틸 함수 테스트 ─────────────────────────────────────────────────────────

def test_year_from_date():
    assert _year("2025-03-15") == 2025

def test_year_none_on_empty():
    assert _year(None) is None
    assert _year("") is None

def test_poster_url_built():
    assert _poster("/abc.jpg") == "https://image.tmdb.org/t/p/w500/abc.jpg"

def test_poster_none_on_missing():
    assert _poster(None) is None


# ── DiscoveryResult 기본 ─────────────────────────────────────────────────────

def test_discovery_result_fields():
    r = DiscoveryResult(source_type="tmdb", external_id="1001", title="영화", content_type="movie")
    assert r.original_title is None
    assert r.raw == {}


# ── TmdbDiscoverySource mock 테스트 ──────────────────────────────────────────

@patch("api.meta_core.discovery.tmdb_source.TmdbClient")
def test_trending_day_yields_results(MockClient, db):
    """정상 응답 → movie + tv 합산 결과 반환."""
    mock_client = AsyncMock()
    MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    MockClient.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_client._get = AsyncMock(side_effect=[
        _page([_MOVIE]),   # movie/day page 1 (total_pages=1 → loop break)
        _page([_TV]),      # tv/day page 1
    ])

    source = TmdbDiscoverySource(api_key="fake", max_pages=1)
    results = list(source.discover("trending_day"))
    assert len(results) == 2
    assert results[0].content_type == "movie"
    assert results[1].content_type == "series"
    assert results[1].external_id == "tv:2001"


@patch("api.meta_core.discovery.tmdb_source.TmdbClient")
def test_adult_content_excluded(MockClient, db):
    """adult=True 항목은 필터링."""
    mock_client = AsyncMock()
    MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    MockClient.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_client._get = AsyncMock(side_effect=[
        _page([_MOVIE, _ADULT_MOVIE]),  # movie
        _page([]),                       # tv
    ])

    source = TmdbDiscoverySource(api_key="fake", max_pages=1)
    results = list(source.discover("trending_day"))
    assert len(results) == 1
    assert results[0].external_id == "1001"


@patch("api.meta_core.discovery.tmdb_source.TmdbClient")
def test_empty_response_yields_nothing(MockClient, db):
    """빈 응답 → 결과 0건."""
    mock_client = AsyncMock()
    MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    MockClient.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_client._get = AsyncMock(return_value=_page([]))

    source = TmdbDiscoverySource(api_key="fake", max_pages=1)
    results = list(source.discover("upcoming"))
    assert results == []


# ── run_discovery DB 연동 테스트 ─────────────────────────────────────────────

class _FakeSource(DiscoverySource):
    source_type = "tmdb"

    def __init__(self, results):
        self._results = results

    def discover(self, mode, **kwargs):
        return iter(self._results)


def test_run_discovery_inserts_seeds(db):
    """정상 결과 → content_seeds 행 생성 + log 기록."""
    r = DiscoveryResult(source_type="tmdb", external_id="1001",
                        title="영화", content_type="movie", raw={"id": 1001})
    source = _FakeSource([r])
    summary = run_discovery(db, source, "trending_day")

    assert summary["new_seeds"] == 1
    assert summary["duplicates"] == 0
    assert db.query(ContentSeed).count() == 1
    assert db.query(SeedDiscoveryLog).count() == 1


def test_run_discovery_upsert_on_duplicate(db):
    """동일 external_id 두 번 → UPDATE (dup count 증가, 행 수 1 유지)."""
    r = DiscoveryResult(source_type="tmdb", external_id="1001",
                        title="영화", content_type="movie", raw={"id": 1001})
    source1 = _FakeSource([r])
    source2 = _FakeSource([r])
    run_discovery(db, source1, "trending_day")
    summary = run_discovery(db, source2, "trending_day")

    assert summary["duplicates"] == 1
    assert db.query(ContentSeed).count() == 1
    assert db.query(SeedDiscoveryLog).count() == 2


def test_run_discovery_empty_creates_log(db):
    """빈 결과 → content_seeds 0건, log 1건."""
    source = _FakeSource([])
    summary = run_discovery(db, source, "upcoming")

    assert summary["total"] == 0
    assert summary["new_seeds"] == 0
    assert db.query(ContentSeed).count() == 0
    assert db.query(SeedDiscoveryLog).count() == 1
