"""
모니터링 API 단위 테스트

/seeds/discovery-log, /seeds/discovery-stats, /seeds/funnel
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.database import Base, get_db
import api.meta_core.models  # noqa
import api.programming.metadata.models  # noqa

from api.meta_core.intelligence.seed_router import router
from api.meta_core.models.seed import ContentSeed, SeedDiscoveryLog


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    app = FastAPI()
    app.include_router(router)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app), Session()


def _log(db, source_type="tmdb", mode="trending_day",
         total=10, new_seeds=5, matched=3, dup=2, errors=0) -> SeedDiscoveryLog:
    log = SeedDiscoveryLog(
        source_type=source_type,
        discovery_mode=mode,
        total_fetched=total,
        new_seeds=new_seeds,
        matched_existing=matched,
        duplicates=dup,
        errors=errors,
        duration_ms=500,
    )
    db.add(log)
    db.commit()
    return log


_seed_counter = 0

def _seed(db, status="candidate", source_type="tmdb") -> ContentSeed:
    global _seed_counter
    _seed_counter += 1
    s = ContentSeed(
        source_type=source_type, external_id=f"ext-{_seed_counter}",
        title="Test", content_type="movie", status=status, raw_payload={},
    )
    db.add(s)
    db.commit()
    return s


# ── GET /seeds/discovery-log ──────────────────────────────────────────────────

def test_discovery_log_empty(client):
    tc, _ = client
    resp = tc.get("/seeds/discovery-log")
    assert resp.status_code == 200
    assert resp.json() == []


def test_discovery_log_returns_rows(client):
    tc, db = client
    _log(db, source_type="tmdb")
    _log(db, source_type="kobis")
    resp = tc.get("/seeds/discovery-log?limit=10")
    assert len(resp.json()) == 2


def test_discovery_log_filter_source(client):
    tc, db = client
    _log(db, source_type="tmdb")
    _log(db, source_type="kobis")
    resp = tc.get("/seeds/discovery-log?source=kobis")
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["source_type"] == "kobis"


# ── GET /seeds/discovery-stats ────────────────────────────────────────────────

def test_discovery_stats_empty(client):
    tc, _ = client
    resp = tc.get("/seeds/discovery-stats?days=7")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_new_seeds"] == 0


def test_discovery_stats_aggregates(client):
    tc, db = client
    _log(db, source_type="tmdb", new_seeds=5)
    _log(db, source_type="kobis", new_seeds=3)
    resp = tc.get("/seeds/discovery-stats?days=7")
    data = resp.json()
    assert data["total_new_seeds"] == 8
    assert "tmdb" in data["by_source"]
    assert "kobis" in data["by_source"]


# ── GET /seeds/funnel ─────────────────────────────────────────────────────────

def test_funnel_empty(client):
    tc, _ = client
    resp = tc.get("/seeds/funnel")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1   # 0 방지용 기본값
    assert data["acceptance_rate"] == 0.0


def test_funnel_with_seeds(client):
    tc, db = client
    _seed(db, status="candidate")
    _seed(db, status="candidate")
    _seed(db, status="accepted")
    resp = tc.get("/seeds/funnel")
    data = resp.json()
    assert data["total"] == 3
    accepted = next(f for f in data["funnel"] if f["status"] == "accepted")
    assert accepted["count"] == 1
    assert data["acceptance_rate"] == pytest.approx(33.3, abs=0.2)
