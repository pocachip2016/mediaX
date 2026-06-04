"""Step 5 검증: revert/reject/re-review → auto_hold set, resume-auto → 해제,
임계값 변경 → auto_review_skipped_at clear (ADR-010).
"""
import pytest
from fastapi.testclient import TestClient
from main import app
from shared.database import SessionLocal
from api.programming.metadata.models.content import Content, ContentStatus, PipelineStage

client = TestClient(app, headers={"x-pipeline-test-token": "test"})


def _seed_one(stage=PipelineStage.S8_REVIEW, status=ContentStatus.ai) -> int:
    with SessionLocal() as db:
        c = Content(
            title="hold테스트",
            content_type="movie",
            status=status,
            current_stage=stage,
            cp_name="AUTO_TEST",
            is_deleted=False,
            auto_hold=False,
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        return c.id


def _get(content_id: int):
    with SessionLocal() as db:
        c = db.get(Content, content_id)
        return {"auto_hold": c.auto_hold, "status": c.status.value if c.status else None,
                "auto_review_skipped_at": c.auto_review_skipped_at,
                "auto_claimed_at": c.auto_claimed_at}


def _cleanup(*ids):
    with SessionLocal() as db:
        for cid in ids:
            c = db.get(Content, cid)
            if c:
                c.is_deleted = True
        db.commit()


# ── revert → auto_hold ────────────────────────────────────────────────────────

def test_revert_sets_auto_hold():
    cid = _seed_one(stage=PipelineStage.S8_REVIEW, status=ContentStatus.ai)
    try:
        r = client.post("/api/test/pipeline/revert", json={"ids": [cid]})
        assert r.status_code == 200, r.text
        state = _get(cid)
        assert state["auto_hold"] is True, f"revert 후 auto_hold 미설정: {state}"
        assert state["auto_claimed_at"] is None
    finally:
        _cleanup(cid)


# ── reject → auto_hold ────────────────────────────────────────────────────────

def test_reject_sets_auto_hold():
    cid = _seed_one(stage=PipelineStage.S8_REVIEW, status=ContentStatus.ai)
    try:
        r = client.post("/api/test/pipeline/reject", json={"ids": [cid]})
        assert r.status_code == 200, r.text
        state = _get(cid)
        assert state["auto_hold"] is True
        assert state["status"] == "rejected"
    finally:
        _cleanup(cid)


# ── re-review → auto_hold ─────────────────────────────────────────────────────

def test_re_review_sets_auto_hold():
    cid = _seed_one(stage=PipelineStage.S8_REVIEW, status=ContentStatus.rejected)
    try:
        r = client.post("/api/test/pipeline/re-review", json={"ids": [cid]})
        assert r.status_code == 200, r.text
        state = _get(cid)
        assert state["auto_hold"] is True
    finally:
        _cleanup(cid)


# ── resume-auto → hold 해제 ───────────────────────────────────────────────────

def test_resume_auto_clears_hold():
    cid = _seed_one()
    with SessionLocal() as db:
        c = db.get(Content, cid)
        c.auto_hold = True
        db.commit()
    try:
        r = client.post("/api/test/pipeline/resume-auto", json={"ids": [cid]})
        assert r.status_code == 200, r.text
        state = _get(cid)
        assert state["auto_hold"] is False
    finally:
        _cleanup(cid)


# ── 임계값 변경 → auto_review_skipped_at clear ──────────────────────────────

def test_threshold_change_clears_skipped_at():
    cid = _seed_one(stage=PipelineStage.S8_REVIEW, status=ContentStatus.ai)
    from datetime import datetime, timezone
    with SessionLocal() as db:
        c = db.get(Content, cid)
        c.auto_review_skipped_at = datetime.now(timezone.utc)
        db.commit()

    try:
        # 현재 임계값 조회
        cur = client.get("/api/programming/metadata/ai-tasks/stage-auto-policy").json()
        new_val = (cur.get("s4_quality_threshold") or 90.0) + 5.0
        r = client.patch("/api/programming/metadata/ai-tasks/stage-auto-policy",
                         json={"s4_quality_threshold": new_val})
        assert r.status_code == 200, r.text

        state = _get(cid)
        assert state["auto_review_skipped_at"] is None, "임계값 변경 후 skipped_at 미초기화"
    finally:
        # 임계값 복원
        client.patch("/api/programming/metadata/ai-tasks/stage-auto-policy",
                     json={"s4_quality_threshold": cur.get("s4_quality_threshold") or 90.0})
        _cleanup(cid)
