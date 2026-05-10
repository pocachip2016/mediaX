"""
match_or_create_seed 단위 테스트

SQLite in-memory DB — 실제 API 호출 없음.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shared.database import Base
import api.meta_core.models  # noqa
import api.programming.metadata.models  # noqa

from api.meta_core.discovery.base import DiscoveryResult
from api.meta_core.discovery.dedup import match_or_create_seed
from api.meta_core.discovery.runner import run_discovery
from api.meta_core.models.seed import ContentSeed
from api.meta_core.models.intelligence import MatchEdge, MetadataCandidate
from api.programming.metadata.models.content import Content


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _result(title="기생충", year=2019, source_type="tmdb", external_id="496243",
            content_type="movie") -> DiscoveryResult:
    return DiscoveryResult(
        source_type=source_type,
        external_id=external_id,
        title=title,
        content_type=content_type,
        production_year=year,
    )


def _content(db, title="기생충", year=2019) -> Content:
    c = Content(title=title, production_year=year, content_type="movie", status="approved")
    db.add(c)
    db.flush()
    return c


# ── 1. 신규 발굴 → SEED 생성 ─────────────────────────────────────────────────

def test_new_result_creates_seed(db):
    seed, action = match_or_create_seed(db, _result())
    assert action == "created"
    assert seed is not None
    assert seed.source_type == "tmdb"
    assert seed.external_id == "496243"
    assert seed.status == "candidate"


# ── 2. 동일 source+id 재발굴 → UPDATE (duplicate) ────────────────────────────

def test_duplicate_source_updates_seed(db):
    r = _result()
    seed1, action1 = match_or_create_seed(db, r)
    assert action1 == "created"
    db.flush()

    r2 = _result(title="기생충 (수정)")
    seed2, action2 = match_or_create_seed(db, r2)
    assert action2 == "duplicate"
    assert seed2.id == seed1.id
    assert seed2.title == "기생충 (수정)"
    assert db.query(ContentSeed).count() == 1


# ── 3. 기존 Content 매칭 ≥ 0.85 → SEED 미생성, MatchEdge 추가 ────────────────

def test_matched_content_no_seed(db):
    _content(db, title="기생충", year=2019)
    db.flush()

    _, action = match_or_create_seed(db, _result(title="기생충", year=2019, source_type="kobis", external_id="20190001"))
    assert action == "matched_existing"
    assert db.query(ContentSeed).count() == 0
    assert db.query(MatchEdge).count() == 1


def test_matched_content_edge_score(db):
    _content(db, title="기생충", year=2019)
    db.flush()

    match_or_create_seed(db, _result(title="기생충", year=2019, source_type="kmdb", external_id="KMD001"))
    edge = db.query(MatchEdge).first()
    assert edge.score >= 0.85


# ── 4. production_year ±1 허용 ────────────────────────────────────────────────

def test_year_plus_one_still_matches(db):
    _content(db, title="기생충", year=2019)
    db.flush()

    # year=2020 → 기존 Content year=2019, 차이 1 → 여전히 매칭
    _, action = match_or_create_seed(db, _result(title="기생충", year=2020, source_type="kobis", external_id="X001"))
    assert action == "matched_existing"


def test_year_two_apart_creates_seed(db):
    _content(db, title="기생충", year=2019)
    db.flush()

    # year=2021 → 차이 2 → 매칭 안 됨 → 새 SEED
    _, action = match_or_create_seed(db, _result(title="기생충", year=2021, source_type="kobis", external_id="X002"))
    assert action == "created"


# ── 5. SEED 간 fuzzy match → alt_external_ids 누적 ───────────────────────────

def test_alt_id_added_to_sibling_seed(db):
    # tmdb SEED 먼저 생성
    r_tmdb = _result(title="기생충", year=2019, source_type="tmdb", external_id="496243")
    seed_tmdb, _ = match_or_create_seed(db, r_tmdb)
    db.flush()

    # kobis 동일 제목+연도 → alt_id_added
    r_kobis = _result(title="기생충", year=2019, source_type="kobis", external_id="20190001")
    seed_kobis, action = match_or_create_seed(db, r_kobis)
    assert action == "alt_id_added"
    assert seed_kobis.id == seed_tmdb.id
    assert seed_tmdb.alt_external_ids["kobis"] == "20190001"
    assert db.query(ContentSeed).count() == 1


# ── 6. run_discovery — matched_existing 카운터 검증 ──────────────────────────

def test_run_discovery_matched_existing_counter(db):
    _content(db, title="기생충", year=2019)
    db.flush()

    from unittest.mock import MagicMock
    from api.meta_core.discovery.tmdb_source import TmdbDiscoverySource

    source = TmdbDiscoverySource(api_key="fake")
    source.discover = MagicMock(return_value=iter([
        _result(title="기생충", year=2019, source_type="tmdb", external_id="496243"),
    ]))

    summary = run_discovery(db, source, "trending_day")
    assert summary["matched_existing"] == 1
    assert summary["new_seeds"] == 0
    assert db.query(ContentSeed).count() == 0


# ── 7. 완전히 다른 제목 → 별도 SEED ─────────────────────────────────────────

def test_different_title_creates_new_seed(db):
    r1 = _result(title="기생충", year=2019, source_type="tmdb", external_id="111")
    match_or_create_seed(db, r1)
    db.flush()

    r2 = _result(title="올드보이", year=2003, source_type="tmdb", external_id="222")
    _, action = match_or_create_seed(db, r2)
    assert action == "created"
    assert db.query(ContentSeed).count() == 2
