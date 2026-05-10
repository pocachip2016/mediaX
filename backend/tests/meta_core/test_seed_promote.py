"""
promote_seed 단위 테스트

SQLite in-memory DB. Celery enqueue는 mock.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shared.database import Base
import api.meta_core.models  # noqa
import api.programming.metadata.models  # noqa

from api.meta_core.discovery.promote import (
    promote_seed,
    SeedNotFound, SeedAlreadyProcessed, SeedLockedByOther, PossibleDuplicate,
)
from api.meta_core.models.seed import ContentSeed
from api.programming.metadata.models.content import Content
from api.programming.metadata.models.external import ExternalMetaSource


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _seed(db, title="기생충", year=2019, source_type="tmdb", external_id="496243",
          status="candidate", locked_by=None, locked_at=None) -> ContentSeed:
    seed = ContentSeed(
        source_type=source_type,
        external_id=external_id,
        title=title,
        content_type="movie",
        production_year=year,
        status=status,
        locked_by=locked_by,
        locked_at=locked_at,
        raw_payload={},
    )
    db.add(seed)
    db.flush()
    return seed


def _content(db, title="기생충", year=2019) -> Content:
    c = Content(title=title, production_year=year, content_type="movie", status="approved")
    db.add(c)
    db.flush()
    return c


# ── 1. 정상 승격 ──────────────────────────────────────────────────────────────

def test_promote_creates_content(db):
    seed = _seed(db)
    with patch("api.meta_core.discovery.promote._enqueue_aggregate") as mock_enq:
        content = promote_seed(db, seed.id, actor="admin")
    assert content.title == "기생충"
    assert content.production_year == 2019
    assert db.query(Content).count() == 1
    mock_enq.assert_called_once_with(content.id)


def test_promote_creates_external_meta_source(db):
    seed = _seed(db)
    with patch("api.meta_core.discovery.promote._enqueue_aggregate"):
        content = promote_seed(db, seed.id, actor="admin")
    ext = db.query(ExternalMetaSource).filter_by(content_id=content.id).first()
    assert ext is not None
    assert ext.external_id == "496243"
    assert ext.match_confidence == 1.0


def test_promote_seed_status_accepted(db):
    seed = _seed(db)
    with patch("api.meta_core.discovery.promote._enqueue_aggregate"):
        content = promote_seed(db, seed.id, actor="admin")
    db.refresh(seed)
    assert seed.status == "accepted"
    assert seed.promoted_to_content_id == content.id
    assert seed.locked_by is None


# ── 2. 존재하지 않는 seed_id ──────────────────────────────────────────────────

def test_promote_not_found(db):
    with pytest.raises(SeedNotFound):
        promote_seed(db, 9999, actor="admin")


# ── 3. 이미 accepted → SeedAlreadyProcessed ──────────────────────────────────

def test_promote_already_accepted(db):
    seed = _seed(db, status="accepted")
    with pytest.raises(SeedAlreadyProcessed):
        promote_seed(db, seed.id, actor="admin")


def test_promote_already_rejected(db):
    seed = _seed(db, status="rejected")
    with pytest.raises(SeedAlreadyProcessed):
        promote_seed(db, seed.id, actor="admin")


# ── 4. lock 보유 다른 사용자 → SeedLockedByOther ──────────────────────────────

def test_promote_locked_by_other(db):
    locked_at = datetime.now(tz=timezone.utc) - timedelta(minutes=5)  # TTL 내
    seed = _seed(db, locked_by="other_user", locked_at=locked_at)
    with pytest.raises(SeedLockedByOther) as exc_info:
        promote_seed(db, seed.id, actor="admin")
    assert exc_info.value.locked_by == "other_user"


# ── 5. lock TTL 만료 → 진행 ───────────────────────────────────────────────────

def test_promote_expired_lock_proceeds(db):
    locked_at = datetime.now(tz=timezone.utc) - timedelta(minutes=20)  # TTL 초과
    seed = _seed(db, locked_by="other_user", locked_at=locked_at)
    with patch("api.meta_core.discovery.promote._enqueue_aggregate"):
        content = promote_seed(db, seed.id, actor="admin")
    assert content is not None


# ── 6. dedup 재확인 — 기존 Content 감지 → PossibleDuplicate ──────────────────

def test_promote_possible_duplicate(db):
    _content(db, title="기생충", year=2019)
    db.flush()
    seed = _seed(db, title="기생충", year=2019)
    with pytest.raises(PossibleDuplicate) as exc_info:
        promote_seed(db, seed.id, actor="admin")
    assert exc_info.value.score >= 0.85


# ── 7. override_dup=True → 강제 승격 ─────────────────────────────────────────

def test_promote_override_dup(db):
    _content(db, title="기생충", year=2019)
    db.flush()
    seed = _seed(db, title="기생충", year=2019, source_type="kobis", external_id="20190001")
    with patch("api.meta_core.discovery.promote._enqueue_aggregate"):
        content = promote_seed(db, seed.id, actor="admin", override_dup=True)
    assert content is not None
    assert db.query(Content).count() == 2  # 기존 + 신규
