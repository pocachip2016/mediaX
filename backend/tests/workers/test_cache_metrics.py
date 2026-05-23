"""cache_inserted / cache_updated 카운터가 sync_log에 올바르게 기록되는지 검증."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.database import Base
import api.programming.metadata.models  # noqa
import api.programming.metadata.models.kobis_cache  # noqa
import api.programming.metadata.models.kmdb_cache  # noqa
import api.programming.metadata.models.tmdb_cache  # noqa


@pytest.fixture
def Session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _last_log(Session):
    from api.programming.metadata.models import TmdbSyncLog
    db = Session()
    try:
        return db.query(TmdbSyncLog).order_by(TmdbSyncLog.id.desc()).first()
    finally:
        db.close()


# ── KMDB backfill ──────────────────────────────────────────────────────────────

def test_kmdb_backfill_cache_inserted(Session):
    """backfill_kmdb 실행 시 새로운 캐시 행 수가 cache_inserted 에 기록된다."""
    from workers.tasks.kmdb_cache import backfill_kmdb

    fake_movie = {
        "DOCID": "TEST001",
        "title": "테스트 영화",
        "prodYear": "2023",
    }

    mock_client = MagicMock()
    mock_client.search_year.side_effect = [
        ([fake_movie], 1),
        ([], 0),
    ]

    with (
        patch("workers.tasks.kmdb_cache.SessionLocal", Session),
        patch("api.meta_core.clients.kmdb_client.KmdbClient", return_value=mock_client),
        patch("shared.config.settings") as mock_settings,
    ):
        mock_settings.KMDB_API_KEY = "fake-key"
        backfill_kmdb(year=2023)

    log = _last_log(Session)
    assert log is not None
    assert log.cache_inserted == 1, f"expected cache_inserted=1, got {log.cache_inserted}"
    assert log.cache_updated == 0


def test_kmdb_backfill_cache_updated_on_duplicate(Session):
    """같은 DOCID를 두 번 backfill하면 두 번째엔 cache_updated 만 오른다."""
    from workers.tasks.kmdb_cache import backfill_kmdb

    fake_movie = {"DOCID": "TEST002", "title": "중복 영화", "prodYear": "2022"}

    mock_client = MagicMock()
    mock_client.search_year.side_effect = [([fake_movie], 1), ([], 0)]

    ctx = dict(
        patch_session=patch("workers.tasks.kmdb_cache.SessionLocal", Session),
        patch_client=patch("workers.tasks.kmdb_cache.KmdbClient", return_value=mock_client),
        patch_cfg=patch("shared.config.settings"),
    )

    # 1회차 — inserted
    with (
        patch("workers.tasks.kmdb_cache.SessionLocal", Session),
        patch("api.meta_core.clients.kmdb_client.KmdbClient", return_value=mock_client),
        patch("shared.config.settings") as s,
    ):
        s.KMDB_API_KEY = "fake"
        backfill_kmdb(year=2022)

    # 2회차 — updated (title 변경으로 changed=True 유도)
    fake_movie_v2 = {**fake_movie, "title": "중복 영화 v2"}
    mock_client.search_year.side_effect = [([fake_movie_v2], 1), ([], 0)]

    with (
        patch("workers.tasks.kmdb_cache.SessionLocal", Session),
        patch("api.meta_core.clients.kmdb_client.KmdbClient", return_value=mock_client),
        patch("shared.config.settings") as s,
    ):
        s.KMDB_API_KEY = "fake"
        backfill_kmdb(year=2022)

    log = _last_log(Session)
    assert log.cache_inserted == 0
    assert log.cache_updated == 1


# ── KOBIS backfill ─────────────────────────────────────────────────────────────

def test_kobis_backfill_cache_inserted(Session):
    """backfill_kobis 실행 시 새로운 캐시 행 수가 cache_inserted 에 기록된다."""
    import httpx
    from workers.tasks.metadata import backfill_kobis

    fake_movie = {
        "movieCd": "20230001",
        "movieNm": "코비스 테스트",
        "openDt": "20230101",
        "prdtYear": "2023",
        "directors": {},
    }
    fake_resp = MagicMock(spec=httpx.Response)
    fake_resp.json.return_value = {
        "movieListResult": {"movieList": [fake_movie], "totCnt": 1}
    }

    with (
        patch("workers.tasks.metadata.SessionLocal", Session),
        patch("workers.tasks.metadata._kobis_rate_allowed", return_value=True),
        patch("httpx.get", return_value=fake_resp),
        patch("shared.config.settings") as s,
    ):
        s.KOBIS_API_KEY = "fake"
        backfill_kobis(year=2023)

    log = _last_log(Session)
    assert log is not None
    assert log.cache_inserted == 1, f"expected cache_inserted=1, got {log.cache_inserted}"
    assert log.cache_updated == 0
