"""Step 3 검증: advance_one / approve_one 멱등 전이 (ADR-010).

선조건 재확인 → 이미 이동 시 no-op, 실제 전이만 StageEvent.
auto_hold=True인 콘텐츠는 claim/advance/approve 모두 차단.
"""
import pytest
from sqlalchemy.orm import Session
from shared.database import engine
from api.programming.metadata.models.content import (
    Content, ContentStatus, PipelineStage,
)
from api.programming.metadata.models.stage_event import StageEvent
from api.test.pipeline_auto_service import advance_one, approve_one, claim_bucket


def _make_content(db: Session, title: str, stage=None, status=ContentStatus.raw) -> Content:
    c = Content(
        title=title,
        content_type="movie",
        status=status,
        current_stage=stage,
        cp_name="AUTO_TEST",
        is_deleted=False,
        auto_hold=False,
    )
    db.add(c)
    db.flush()
    return c


@pytest.fixture
def db():
    with Session(engine) as session:
        yield session
        session.rollback()  # 테스트 후 롤백 — DB 오염 방지


def test_advance_once_records_single_event(db):
    """advance_one → StageEvent 1건, status/stage 정상 전이."""
    c = _make_content(db, "멱등테스트A")
    before_events = db.query(StageEvent).filter(StageEvent.content_id == c.id).count()

    r = advance_one(db, c.id, actor="test")
    assert r["result"] == "ok"

    after_events = db.query(StageEvent).filter(StageEvent.content_id == c.id).count()
    assert after_events == before_events + 1
    db.refresh(c)
    assert c.current_stage == PipelineStage.S2_NORMALIZE


def test_advance_sequential_two_steps(db):
    """순차 advance 2회 → bucket 1→2→3으로 각각 정확히 이동, StageEvent 2건."""
    c = _make_content(db, "멱등테스트B")

    r1 = advance_one(db, c.id, actor="test")
    assert r1["result"] == "ok"
    db.refresh(c)
    assert c.current_stage == PipelineStage.S2_NORMALIZE  # bucket 2 진입

    r2 = advance_one(db, c.id, actor="test")
    assert r2["result"] == "ok"
    db.refresh(c)
    assert c.current_stage == PipelineStage.S6_LLM_EXTRACT  # bucket 3 진입

    events = db.query(StageEvent).filter(StageEvent.content_id == c.id).count()
    assert events == 2  # 전이마다 정확히 1건


def test_advance_hold_blocks_auto_only(db):
    """auto_hold=True: AUTO 워커(actor=auto)는 차단, 수동(user)은 hold 해제하고 진행."""
    # 1) actor="auto" → hold 차단 (워커는 진행 안 함)
    c1 = _make_content(db, "멱등테스트C-auto")
    c1.auto_hold = True
    db.flush()
    r1 = advance_one(db, c1.id, actor="auto")
    assert r1["result"] == "hold"
    db.refresh(c1)
    assert c1.current_stage is None  # 변경 없음

    # 2) actor="user" → hold 해제하고 advance (운영자 수동 진행)
    c2 = _make_content(db, "멱등테스트C-user")
    c2.auto_hold = True
    db.flush()
    r2 = advance_one(db, c2.id, actor="user")
    assert r2["result"] == "ok"
    db.refresh(c2)
    assert c2.auto_hold is False           # hold 해제됨
    assert c2.current_stage == PipelineStage.S2_NORMALIZE


def test_approve_once_ok(db):
    """approve_one → S8_REVIEW bucket 콘텐츠 → ok."""
    c = _make_content(db, "멱등테스트D",
                      stage=PipelineStage.S8_REVIEW, status=ContentStatus.ai)
    r = approve_one(db, c.id, actor="test")
    assert r["result"] == "ok"
    db.refresh(c)
    assert c.status == ContentStatus.approved


def test_approve_twice_already_approved(db):
    """approve_one 2회 → 두 번째는 already_approved."""
    c = _make_content(db, "멱등테스트E",
                      stage=PipelineStage.S8_REVIEW, status=ContentStatus.ai)
    r1 = approve_one(db, c.id, actor="test")
    assert r1["result"] == "ok"

    r2 = approve_one(db, c.id, actor="test")
    assert r2["result"] == "already_approved"


def test_approve_wrong_bucket(db):
    """bucket 4가 아닌 콘텐츠 approve_one → not_in_review."""
    c = _make_content(db, "멱등테스트F",
                      stage=PipelineStage.S2_NORMALIZE, status=ContentStatus.raw)
    r = approve_one(db, c.id, actor="test")
    assert r["result"] == "not_in_review"


def test_claim_excludes_held(db):
    """claim_bucket → auto_hold=True 콘텐츠는 제외."""
    c = _make_content(db, "멱등테스트G")
    c.auto_hold = True
    db.flush()

    claimed = claim_bucket(db, bucket=1, batch_size=50, visibility_timeout=600)
    claimed_ids = [x.id for x in claimed]
    assert c.id not in claimed_ids
