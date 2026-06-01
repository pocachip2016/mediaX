"""
dev-s4-review-cleanup — S4 검수 승인/반려/재검수 회귀 테스트

핵심 가드:
  - /approve : COMPLETED@S9_PUBLISH → status=approved
  - /reject  : REJECTED 이벤트 + status=rejected, 위치 유지
  - /re-review: 반려건 → RETRIED 이벤트 + status=ai 복귀
  - not_found: 없는 id → results[id]="not_found", skipped 카운트

pytest tests/test_s4_review_actions.py -q
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
from api.programming.metadata.models.stage_event import StageEvent
from api.programming.metadata.models.content import StageEventType, PipelineStage


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


def _make(db, status=ContentStatus.ai, stage=PipelineStage.S8_REVIEW, title="테스트"):
    c = Content(title=title, content_type=ContentType.movie, cp_name="TEST_S4",
                status=status, current_stage=stage)
    db.add(c); db.flush()
    db.add(ContentMetadata(content_id=c.id, quality_score=0.0)); db.flush()
    return c


# ── approve ─────────────────────────────────────────────────────────────────

def test_approve_sets_status_approved(client, db):
    """approve: status=approved, COMPLETED@S9_PUBLISH 기록."""
    c = _make(db, status=ContentStatus.ai)
    db.commit()

    res = client.post("/api/test/pipeline/approve", json={"ids": [c.id]})
    assert res.status_code == 200
    data = res.json()
    assert data["processed"] == 1
    assert data["skipped"] == 0
    assert data["results"][str(c.id)] == "approved"

    db.expire(c)
    assert c.status == ContentStatus.approved

    event = (db.query(StageEvent)
             .filter(StageEvent.content_id == c.id, StageEvent.stage == PipelineStage.S9_PUBLISH)
             .order_by(StageEvent.id.desc()).first())
    assert event is not None
    assert event.event_type == StageEventType.COMPLETED


# ── reject ──────────────────────────────────────────────────────────────────

def test_reject_sets_status_rejected(client, db):
    """reject: status=rejected, REJECTED 이벤트 기록, current_stage 유지."""
    c = _make(db, status=ContentStatus.ai, stage=PipelineStage.S8_REVIEW)
    db.commit()

    res = client.post("/api/test/pipeline/reject", json={"ids": [c.id]})
    assert res.status_code == 200
    data = res.json()
    assert data["processed"] == 1
    assert data["results"][str(c.id)] == "rejected"

    db.expire(c)
    assert c.status == ContentStatus.rejected

    event = (db.query(StageEvent)
             .filter(StageEvent.content_id == c.id, StageEvent.event_type == StageEventType.REJECTED)
             .order_by(StageEvent.id.desc()).first())
    assert event is not None
    assert event.stage == PipelineStage.S8_REVIEW


def test_reject_uses_current_stage_when_set(client, db):
    """reject: current_stage가 있으면 그 위치에 REJECTED 기록."""
    c = _make(db, status=ContentStatus.ai, stage=PipelineStage.S7_STAGING)
    db.commit()

    client.post("/api/test/pipeline/reject", json={"ids": [c.id]})

    event = (db.query(StageEvent)
             .filter(StageEvent.content_id == c.id, StageEvent.event_type == StageEventType.REJECTED)
             .order_by(StageEvent.id.desc()).first())
    assert event is not None
    assert event.stage == PipelineStage.S7_STAGING


# ── re-review ────────────────────────────────────────────────────────────────

def test_re_review_restores_ai_status(client, db):
    """re-review: rejected → status=ai, RETRIED@S8_REVIEW 기록."""
    c = _make(db, status=ContentStatus.rejected, stage=PipelineStage.S8_REVIEW)
    db.commit()

    res = client.post("/api/test/pipeline/re-review", json={"ids": [c.id]})
    assert res.status_code == 200
    data = res.json()
    assert data["processed"] == 1
    assert data["results"][str(c.id)] == "re_reviewed"

    db.expire(c)
    assert c.status == ContentStatus.ai

    event = (db.query(StageEvent)
             .filter(StageEvent.content_id == c.id, StageEvent.event_type == StageEventType.RETRIED)
             .order_by(StageEvent.id.desc()).first())
    assert event is not None
    assert event.stage == PipelineStage.S8_REVIEW


# ── not_found / skipped ─────────────────────────────────────────────────────

def test_approve_not_found_id(client, db):
    """not_found id → results에 not_found, processed=0, skipped=1."""
    res = client.post("/api/test/pipeline/approve", json={"ids": [999999]})
    assert res.status_code == 200
    data = res.json()
    assert data["processed"] == 0
    assert data["skipped"] == 1
    assert data["results"]["999999"] == "not_found"


def test_reject_not_found_id(client, db):
    res = client.post("/api/test/pipeline/reject", json={"ids": [999998]})
    assert res.status_code == 200
    data = res.json()
    assert data["results"]["999998"] == "not_found"
    assert data["skipped"] == 1


def test_re_review_not_found_id(client, db):
    res = client.post("/api/test/pipeline/re-review", json={"ids": [999997]})
    assert res.status_code == 200
    data = res.json()
    assert data["results"]["999997"] == "not_found"
    assert data["skipped"] == 1
