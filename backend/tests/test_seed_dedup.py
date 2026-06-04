"""
dev-seed-dedup — 시드 중복 입력 방지 회귀 테스트

핵심 가드:
  - 연속 2회 시드 → 2회차 신규 생성 0건, 전부 skip
  - approved 동명 콘텐츠 사전 존재 → skipped_registered
  - in-pipeline(status!=approved) 동명 콘텐츠 → skipped_in_pipeline
  - 시리즈 루트 중복 시 시즌/에피소드 cascade 미생성

모든 precondition은 API client만으로 구성 — db fixture session 혼용 없음.

pytest tests/test_seed_dedup.py -q
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api.programming.metadata.models          # noqa: F401
import api.meta_core.models                     # noqa: F401
import api.meta_core.public_api.models          # noqa: F401
import api.distribution.models                  # noqa: F401
from shared.database import Base, get_db
from main import app


_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
_Session = sessionmaker(bind=_engine)


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(_engine)
    def override():
        d = _Session()
        try: yield d
        finally: d.close()
    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(_engine)


def _seed(client) -> dict:
    res = client.post("/api/test/pipeline/seed")
    assert res.status_code == 200, res.text
    return res.json()


def _cleanup(client):
    res = client.post("/api/test/pipeline/cleanup")
    assert res.status_code == 200


def _advance(client, ids: list) -> dict:
    res = client.post("/api/test/pipeline/advance", json={"ids": ids})
    assert res.status_code == 200
    return res.json()


def _approve(client, ids: list) -> dict:
    res = client.post("/api/test/pipeline/approve", json={"ids": ids})
    assert res.status_code == 200
    return res.json()


def _list_by_title(client, title: str) -> list:
    res = client.get(f"/api/programming/metadata/contents?title={title}&size=10")
    if res.status_code != 200:
        return []
    return res.json().get("items", [])


# ── 멱등성: 연속 2회 시드 ──────────────────────────────────────────────────

def test_double_seed_idempotent(client):
    """clean 없이 재시드하면 신규 생성 0, 전부 skip."""
    _cleanup(client)
    r1 = _seed(client)
    created = (r1["movie_complete"] + r1["movie_incomplete"]
               + r1["series_complete"] + r1["series_incomplete"] + r1["conflict"])
    assert created > 0
    assert r1["skipped_in_pipeline"] == 0
    assert r1["skipped_registered"] == 0

    r2 = _seed(client)
    assert r2["movie_complete"] == 0
    assert r2["movie_incomplete"] == 0
    assert r2["series_complete"] == 0
    assert r2["series_incomplete"] == 0
    assert r2["conflict"] == 0
    assert r2["skipped_in_pipeline"] + r2["skipped_registered"] == created

    _cleanup(client)


# ── approved 콘텐츠 → skipped_registered ─────────────────────────────────

def test_approved_movie_skipped_registered(client):
    """TEST_PIPELINE 내 approved 동명 영화가 있으면 재시드 시 skipped_registered."""
    _cleanup(client)
    # 기생충(완전영화-0)을 만들고 S9 승인까지 advance
    r1 = _seed(client)
    assert r1["movie_complete"] >= 1

    # 기생충 조회
    items = _list_by_title(client, "기생충")
    assert items, "기생충 콘텐츠 조회 실패"
    parasite_id = items[0]["id"]

    # advance 4단계(raw→enriched→ai→review→approved) + approve
    for _ in range(4):
        _advance(client, [parasite_id])
    _approve(client, [parasite_id])

    # 재시드 — 기생충은 approved라 skipped_registered 증가
    r2 = _seed(client)
    assert r2["skipped_registered"] >= 1, f"기생충 approved 인데 skipped_registered=0: {r2}"
    assert r2["movie_complete"] == 0  # 기생충 제외한 나머지는 이미 in-pipeline이므로 0

    _cleanup(client)


# ── in-pipeline 콘텐츠 → skipped_in_pipeline ─────────────────────────────

def test_in_pipeline_movie_skipped_in_pipeline(client):
    """TEST_PIPELINE 내 진행중(!=approved) 동명 영화 있으면 재시드 시 skipped_in_pipeline."""
    _cleanup(client)
    r1 = _seed(client)
    created = (r1["movie_complete"] + r1["movie_incomplete"]
               + r1["series_complete"] + r1["series_incomplete"] + r1["conflict"])
    assert created > 0
    assert r1["skipped_in_pipeline"] == 0

    # 재시드 — 모두 raw/in-pipeline 상태이므로 skipped_in_pipeline
    r2 = _seed(client)
    assert r2["skipped_in_pipeline"] >= created
    assert r2["movie_complete"] == 0

    _cleanup(client)


# ── 시리즈 루트 중복 → cascade skip ──────────────────────────────────────

def test_series_root_cascade_skips_children(client):
    """시리즈 루트 중복 시 시즌·에피소드 전체가 생성되지 않음."""
    _cleanup(client)
    r1 = _seed(client)
    assert r1["series_complete"] == 2, f"1회차: series_complete={r1['series_complete']}"

    # 2회차 — 시리즈 루트 중복이므로 cascade skip
    r2 = _seed(client)
    assert r2["series_complete"] == 0
    assert r2["series_incomplete"] == 0
    assert r2["skipped_in_pipeline"] + r2["skipped_registered"] >= 2

    _cleanup(client)
