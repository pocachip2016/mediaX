"""link_*_cache_to_contents 태스크가 올바른 source enum 으로 sync_log를 생성하는지 검증."""
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


@pytest.fixture(autouse=True)
def patch_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with patch("workers.tasks.metadata.SessionLocal", Session):
        yield Session


def _last_sync_log(Session):
    from api.programming.metadata.models import TmdbSyncLog
    db = Session()
    try:
        return db.query(TmdbSyncLog).order_by(TmdbSyncLog.id.desc()).first()
    finally:
        db.close()


def test_link_kmdb_uses_kmdb_link_enum(patch_session):
    """link_kmdb_cache_to_contents 가 kmdb_link enum으로 sync_log를 생성해야 한다."""
    from api.programming.metadata.models import TmdbSyncSource
    from workers.tasks.metadata import link_kmdb_cache_to_contents

    with patch("workers.tasks.metadata.SessionLocal", patch_session):
        link_kmdb_cache_to_contents()

    log = _last_sync_log(patch_session)
    assert log is not None
    assert log.source == TmdbSyncSource.kmdb_link, (
        f"expected kmdb_link, got {log.source}"
    )


def test_link_kobis_uses_kobis_link_enum(patch_session):
    """link_kobis_cache_to_contents 가 kobis_link enum으로 sync_log를 생성해야 한다."""
    from api.programming.metadata.models import TmdbSyncSource
    from workers.tasks.metadata import link_kobis_cache_to_contents

    with patch("workers.tasks.metadata.SessionLocal", patch_session):
        link_kobis_cache_to_contents()

    log = _last_sync_log(patch_session)
    assert log is not None
    assert log.source == TmdbSyncSource.kobis_link, (
        f"expected kobis_link, got {log.source}"
    )


def test_link_tmdb_uses_tmdb_link_enum(patch_session):
    """link_tmdb_cache_to_contents 가 tmdb_link enum으로 sync_log를 생성해야 한다."""
    from api.programming.metadata.models import TmdbSyncSource
    from workers.tasks.metadata import link_tmdb_cache_to_contents

    with patch("workers.tasks.metadata.SessionLocal", patch_session):
        link_tmdb_cache_to_contents()

    log = _last_sync_log(patch_session)
    assert log is not None
    assert log.source == TmdbSyncSource.tmdb_link, (
        f"expected tmdb_link, got {log.source}"
    )


def test_kmdb_link_not_in_kmdb_backfill():
    """kmdb_link enum 값이 실제로 존재하고 kmdb_backfill과 다름을 확인."""
    from api.programming.metadata.models import TmdbSyncSource

    assert TmdbSyncSource.kmdb_link.value == "kmdb_link"
    assert TmdbSyncSource.kmdb_link != TmdbSyncSource.kmdb_backfill
