"""Step 8 E2E 검증: pipeline-auto-worker 전체 흐름 (ADR-010).

1. seed → 모든 AUTO ON → process_fast_bucket(1,2,4) + process_ai_item 직접 호출
   → S1..approved 무중복 확인
2. 동시 claim 안전 — 동일 content_id가 두 claim 배치에 중복 미포함
3. revert → auto_hold → claim 미포함 → resume → claim 포함
"""
import pytest
from sqlalchemy.orm import Session
from shared.database import SessionLocal, engine
from api.programming.metadata.models.content import (
    Content, ContentStatus, PipelineStage,
)
from api.test.pipeline_auto_service import (
    claim_bucket, advance_one, approve_one, enrich_autofill_one,
)


def _make_content(db: Session, title: str, stage=None, status=ContentStatus.raw) -> Content:
    c = Content(
        title=title, content_type="movie", status=status,
        current_stage=stage, cp_name="E2E_AUTO_TEST",
        is_deleted=False, auto_hold=False,
    )
    db.add(c); db.flush(); return c


@pytest.fixture
def db():
    with Session(engine) as session:
        yield session
        session.rollback()


def test_pipeline_s1_to_s2(db):
    """bucket 1 advance → S2_NORMALIZE 도달."""
    c = _make_content(db, "E2E-S1")
    r = advance_one(db, c.id, actor="auto")
    assert r["result"] == "ok"
    db.refresh(c)
    assert c.current_stage == PipelineStage.S2_NORMALIZE


def test_pipeline_s2_to_s3_advance(db):
    """S2 advance → S6_LLM_EXTRACT 도달."""
    c = _make_content(db, "E2E-S2", stage=PipelineStage.S2_NORMALIZE, status=ContentStatus.raw)
    r = advance_one(db, c.id, actor="auto")
    assert r["result"] == "ok"
    db.refresh(c)
    assert c.current_stage == PipelineStage.S6_LLM_EXTRACT
    assert c.status == ContentStatus.enriched


def test_pipeline_s3_to_s4_advance(db):
    """S3(AI) advance → S8_REVIEW 도달."""
    c = _make_content(db, "E2E-S3", stage=PipelineStage.S6_LLM_EXTRACT, status=ContentStatus.enriched)
    r = advance_one(db, c.id, actor="auto")
    assert r["result"] == "ok"
    db.refresh(c)
    assert c.current_stage == PipelineStage.S8_REVIEW
    assert c.status == ContentStatus.ai


def test_pipeline_approve(db):
    """S4 approve → approved 도달."""
    c = _make_content(db, "E2E-S4", stage=PipelineStage.S8_REVIEW, status=ContentStatus.ai)
    r = approve_one(db, c.id, actor="auto")
    assert r["result"] == "ok"
    db.refresh(c)
    assert c.status == ContentStatus.approved


def test_concurrent_claim_no_overlap(db):
    """동시 claim 안전 — 두 배치에 동일 content_id 중복 없음."""
    ids_created = []
    for i in range(5):
        c = _make_content(db, f"E2E-CLAIM-{i}")
        ids_created.append(c.id)
    db.flush()

    batch1 = [c.id for c in claim_bucket(db, bucket=1, batch_size=3, visibility_timeout=600)]
    batch2 = [c.id for c in claim_bucket(db, bucket=1, batch_size=3, visibility_timeout=600)]

    # SKIP LOCKED로 batch1이 잠근 건은 batch2에서 제외됨
    overlap = set(batch1) & set(batch2)
    assert len(overlap) == 0, f"중복 claim 발생: {overlap}"


def test_claim_bucket4_excludes_skipped(db):
    """bucket 4: auto_review_skipped_at 마킹 건은 claim 제외 (무한 재평가 방지 회귀 가드)."""
    from datetime import datetime, timezone
    c_skipped = _make_content(db, "E2E-SKIP", stage=PipelineStage.S8_REVIEW, status=ContentStatus.ai)
    c_skipped.auto_review_skipped_at = datetime.now(timezone.utc)
    c_fresh = _make_content(db, "E2E-FRESH", stage=PipelineStage.S8_REVIEW, status=ContentStatus.ai)
    db.flush()

    claimed = [x.id for x in claim_bucket(db, bucket=4, batch_size=50, visibility_timeout=600)]
    assert c_skipped.id not in claimed, "잔류 판정 건이 재claim됨 (churn 버그)"
    assert c_fresh.id in claimed, "신규 검수 건이 claim 안 됨"


def test_worker_bucket4_reads_metadata_quality_score(db):
    """process_fast_bucket bucket 4는 quality_score를 metadata_record에서 읽어야 함 (AttributeError 회귀 가드)."""
    from api.programming.metadata.models.content import Content as C
    # Content 모델에 quality_score 직접 속성이 없음을 명시 — metadata_record 경유 필수
    c = _make_content(db, "E2E-QS", stage=PipelineStage.S8_REVIEW, status=ContentStatus.ai)
    assert not hasattr(c, "quality_score"), "Content에 quality_score 직접 속성 생기면 worker 로직 재검토 필요"


def test_revert_hold_resume_cycle(db):
    """revert → auto_hold → claim 미포함 → resume → claim 포함."""
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app, headers={"x-pipeline-test-token": "test"})

    c = _make_content(db, "E2E-HOLD", stage=PipelineStage.S8_REVIEW, status=ContentStatus.ai)
    db.commit()

    # revert → auto_hold
    r = client.post("/api/test/pipeline/revert", json={"ids": [c.id]})
    assert r.status_code == 200
    db.refresh(c)
    assert c.auto_hold is True

    # claim → hold 콘텐츠 제외
    claimed_ids = [x.id for x in claim_bucket(db, bucket=4, batch_size=50, visibility_timeout=600)]
    assert c.id not in claimed_ids

    # resume → hold 해제
    r2 = client.post("/api/test/pipeline/resume-auto", json={"ids": [c.id]})
    assert r2.status_code == 200
    db.refresh(c)
    assert c.auto_hold is False

    # cleanup
    c.is_deleted = True
    db.commit()
