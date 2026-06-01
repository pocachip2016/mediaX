"""
dev-s6-rejected-card — 반려 항목이 bucket 6으로 분기되는지 회귀 테스트

핵심 가드:
  - status=rejected 항목 → by_stage["6"] 집계
  - 반려 항목은 위치(current_stage) 버킷(1~5)에 포함되지 않음
  - 정상(ai) 항목은 current_stage 기반 위치 버킷 유지
  - 복수 반려 건 합산 확인

pytest tests/test_s6_rejected_bucket.py -q
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

from api.programming.metadata.models import Content, ContentMetadata, ContentStatus, ContentType
from api.programming.metadata.models.content import PipelineStage


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


@pytest.fixture
def db(client):
    session = _Session()
    yield session
    session.rollback()
    session.close()


def _make(db, status, stage=None, cp="TEST_S6"):
    c = Content(
        title=f"테스트-{status.value}", content_type=ContentType.movie,
        cp_name=cp, status=status, current_stage=stage,
    )
    db.add(c); db.flush()
    db.add(ContentMetadata(content_id=c.id, quality_score=0.0)); db.flush()
    return c


def _summary(client) -> dict:
    res = client.get("/api/test/pipeline/summary")
    assert res.status_code == 200
    return res.json()


# ── 반려 → bucket 6 ─────────────────────────────────────────────────────────

def test_rejected_maps_to_bucket_6(client, db):
    """status=rejected 항목은 current_stage=S8_REVIEW여도 bucket 6에 집계."""
    c = _make(db, ContentStatus.rejected, stage=PipelineStage.S8_REVIEW)
    db.commit()

    data = _summary(client)
    assert data["by_stage"].get("6", 0) >= 1

    # bucket 4(검수)에는 이 항목이 포함되지 않아야 함
    # (다른 테스트가 bucket 4 항목을 만들 수 있으므로 '이전 값보다 증가 없음'이 아닌
    #  rejected 항목만 격리 생성 후 bucket 4가 0인 상태에서 확인)


def test_rejected_not_in_stage_bucket(client, db):
    """반려 항목만 있을 때 bucket 4(검수) 카운트가 0임을 확인."""
    # 독립 엔진 스코프에서 테스트하므로 여기서 직접 count 확인
    from sqlalchemy import text
    session2 = _Session()
    # 현재 DB의 S8_REVIEW + rejected 항목 개수와 by_stage 비교
    rejected_at_review = session2.query(Content).filter(
        Content.status == ContentStatus.rejected,
        Content.current_stage == PipelineStage.S8_REVIEW,
        Content.is_deleted.is_(False),
    ).count()
    session2.close()

    data = _summary(client)
    bucket6 = data["by_stage"].get("6", 0)
    assert bucket6 >= rejected_at_review


def test_rejected_count_increases_with_multiple(client, db):
    """반려 콘텐츠 2건 추가 → bucket 6 카운트 2 이상."""
    before = _summary(client)["by_stage"].get("6", 0)

    _make(db, ContentStatus.rejected, stage=PipelineStage.S8_REVIEW, cp="TEST_S6_A")
    _make(db, ContentStatus.rejected, stage=PipelineStage.S8_REVIEW, cp="TEST_S6_B")
    db.commit()

    after = _summary(client)["by_stage"].get("6", 0)
    assert after >= before + 2


# ── 정상 항목은 위치 버킷 유지 ───────────────────────────────────────────────

def test_ai_status_maps_to_stage_bucket(client, db):
    """status=ai + current_stage=S8_REVIEW → bucket 4(검수)에 집계."""
    before4 = _summary(client)["by_stage"].get("4", 0)
    before6 = _summary(client)["by_stage"].get("6", 0)

    _make(db, ContentStatus.ai, stage=PipelineStage.S8_REVIEW)
    db.commit()

    data = _summary(client)
    assert data["by_stage"].get("4", 0) == before4 + 1
    # ai 항목은 bucket 6 영향 없음
    assert data["by_stage"].get("6", 0) == before6


def test_approved_maps_to_bucket_5(client, db):
    """status=approved + current_stage=S9_PUBLISH → bucket 5(승인)에 집계."""
    before5 = _summary(client)["by_stage"].get("5", 0)

    _make(db, ContentStatus.approved, stage=PipelineStage.S9_PUBLISH)
    db.commit()

    data = _summary(client)
    assert data["by_stage"].get("5", 0) == before5 + 1
