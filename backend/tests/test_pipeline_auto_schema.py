"""Step 1 검증: pipeline-auto-worker 스키마 컬럼 존재 확인 (ADR-010)"""
import pytest
from sqlalchemy import inspect
from shared.database import engine


def _cols(table: str) -> set[str]:
    return {c["name"] for c in inspect(engine).get_columns(table)}


def test_contents_auto_columns():
    cols = _cols("contents")
    assert "auto_hold" in cols
    assert "auto_review_skipped_at" in cols
    assert "auto_claimed_at" in cols


def test_stage_auto_policy_worker_columns():
    cols = _cols("stage_auto_policy")
    assert "auto_tick_enabled" in cols
    assert "batch_size" in cols
    assert "ai_concurrency" in cols
    assert "ai_visibility_timeout" in cols


def test_auto_hold_default_false():
    """새 Content의 auto_hold 서버 기본값이 false 임을 확인."""
    from sqlalchemy.orm import Session
    from api.programming.metadata.models.content import Content, ContentStatus

    with Session(engine) as db:
        c = Content(title="schema-default-test", content_type="movie",
                    status=ContentStatus.raw, is_deleted=False)
        db.add(c)
        db.flush()
        db.refresh(c)
        try:
            assert c.auto_hold is False
            assert c.auto_review_skipped_at is None
            assert c.auto_claimed_at is None
        finally:
            db.rollback()


def test_stage_auto_policy_worker_defaults():
    """새 정책 컬럼 기본값 확인."""
    from sqlalchemy.orm import Session
    from api.programming.metadata.models.external import StageAutoPolicy

    with Session(engine) as db:
        row = db.query(StageAutoPolicy).filter(StageAutoPolicy.id == 1).first()
        if row is None:
            pytest.skip("StageAutoPolicy 행 없음")
        assert row.auto_tick_enabled is True
        assert row.batch_size == 20
        assert row.ai_concurrency == 2
        assert row.ai_visibility_timeout == 600
