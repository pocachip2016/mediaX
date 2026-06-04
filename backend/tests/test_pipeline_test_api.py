"""
/api/test/pipeline/* 엔드포인트 테스트

확인:
  - ENABLE_PIPELINE_TEST=False → POST /seed 404
  - ENABLE_PIPELINE_TEST=True, 토큰 없음(PIPELINE_TEST_ADMIN_KEY="") → 통과
  - ENABLE_PIPELINE_TEST=True, 토큰 불일치 → 403
  - POST /seed → SeedResponse 15건
  - POST /cleanup → CleanupResponse
  - GET /summary → StageSummary
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api.programming.metadata.models  # noqa
import api.meta_core.models             # noqa
import api.meta_core.public_api.models  # noqa
import api.distribution.models          # noqa
from shared.database import Base, get_db
from shared.config import settings
from main import app


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    app.dependency_overrides[get_db] = lambda: session
    yield session

    session.close()
    Base.metadata.drop_all(engine)
    app.dependency_overrides.clear()


@pytest.fixture
def client(test_db):
    return TestClient(app, raise_server_exceptions=True)


# ── Guard tests ───────────────────────────────────────────────────────────────

def test_seed_blocked_when_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_PIPELINE_TEST", False)
    res = client.post("/api/test/pipeline/seed")
    assert res.status_code == 404


def test_seed_blocked_wrong_token(client, monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_PIPELINE_TEST", True)
    monkeypatch.setattr(settings, "PIPELINE_TEST_ADMIN_KEY", "secret123")
    res = client.post("/api/test/pipeline/seed",
                      headers={"X-Pipeline-Test-Token": "wrong"})
    assert res.status_code == 403


def test_seed_passes_no_token_when_key_empty(client, monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_PIPELINE_TEST", True)
    monkeypatch.setattr(settings, "PIPELINE_TEST_ADMIN_KEY", "")
    res = client.post("/api/test/pipeline/seed")
    assert res.status_code == 200
    data = res.json()
    assert data["total_root"] == 15


def test_seed_passes_correct_token(client, monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_PIPELINE_TEST", True)
    monkeypatch.setattr(settings, "PIPELINE_TEST_ADMIN_KEY", "mykey")
    res = client.post("/api/test/pipeline/seed",
                      headers={"X-Pipeline-Test-Token": "mykey"})
    assert res.status_code == 200
    data = res.json()
    assert data["movie_complete"] == 3
    assert data["movie_incomplete"] == 5
    assert data["series_complete"] == 2
    assert data["series_incomplete"] == 3
    assert data["conflict"] == 2


# ── Functional tests ──────────────────────────────────────────────────────────

@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_PIPELINE_TEST", True)
    monkeypatch.setattr(settings, "PIPELINE_TEST_ADMIN_KEY", "")


def test_summary_empty_before_seed(client, enabled):
    res = client.get("/api/test/pipeline/summary")
    assert res.status_code == 200
    assert res.json()["total"] == 0


def test_cleanup_after_seed(client, enabled):
    client.post("/api/test/pipeline/seed")
    res = client.post("/api/test/pipeline/cleanup")
    assert res.status_code == 200
    data = res.json()
    assert data["deleted"] >= 15
    assert data["dry_run"] is False


def test_cleanup_dry_run(client, enabled):
    client.post("/api/test/pipeline/seed")
    res = client.post("/api/test/pipeline/cleanup?dry_run=true")
    assert res.status_code == 200
    data = res.json()
    assert data["deleted"] >= 15
    assert data["dry_run"] is True
    # dry_run: 실제 삭제 안 됨
    summary = client.get("/api/test/pipeline/summary").json()
    assert summary["total"] > 0


def test_summary_after_seed(client, enabled):
    client.post("/api/test/pipeline/seed")
    res = client.get("/api/test/pipeline/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 15
    assert len(data["by_status"]) > 0  # by_status 값 존재 확인 (status enum은 DB 따라 변동)
    assert "movie" in data["by_type"]
    assert data["last_seeded_at"] is not None
