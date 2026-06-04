"""
D1 — pipeline-console-controls E2E 검증 (ADR-007)

핵심 회귀 가드:
  - auto_chain=False → status가 ai에서 정지 (review/approved로 안 넘어감)
  - auto_chain=True, score≥90 → approved 자동 전이
  - auto_chain=True, score<90 → review 전이
  - StageEvent S6_LLM_EXTRACT ENTERED/COMPLETED 기록
  - ContentAIResult is_final=True 기록

LLM은 monkeypatch로 mock — 실제 Ollama/Gemini/Groq 미호출.
"""
import asyncio
import pytest

from api.programming.metadata.models import (
    Content, ContentMetadata, ContentStatus, ContentType,
    ContentAIResult, AITaskType,
)
from api.programming.metadata.models.content import PipelineStage, StageEventType
from api.programming.metadata.models.stage_event import StageEvent
from api.programming.metadata.schemas import AIGenerateResponse


# ── 픽스처 ────────────────────────────────────────────────────────────────────

def _make_content(db, *, status=ContentStatus.enriched, title="테스트 영화"):
    c = Content(
        title=title,
        content_type=ContentType.movie,
        cp_name="TEST_E2E",
        status=status,
    )
    db.add(c)
    db.flush()
    meta = ContentMetadata(content_id=c.id, cp_synopsis="테스트 시놉시스")
    db.add(meta)
    db.flush()
    return c


def _fake_result(quality_score: float) -> tuple[AIGenerateResponse, str]:
    return AIGenerateResponse(
        synopsis="가짜 시놉시스입니다.",
        genre_primary="드라마",
        genre_secondary=None,
        mood_tags=["감동", "가족"],
        rating_suggestion="15세이상관람가",
        quality_score=quality_score,
    ), "mock_engine"


def _mock_generate(score: float):
    async def _inner(req, db_):
        return _fake_result(score)
    return _inner


# ── 테스트 ────────────────────────────────────────────────────────────────────

def test_auto_chain_false_stops_at_ai(db, monkeypatch):
    """핵심 회귀: auto_chain=False 이면 enriched→ai 에서 정지해야 한다."""
    import api.programming.metadata.ai_engine as engine_mod
    monkeypatch.setattr(engine_mod, "_generate_metadata_with_engine", _mock_generate(95.0))

    content = _make_content(db)
    asyncio.run(engine_mod.process_content_ai(content.id, db, auto_chain=False))

    db.refresh(content)
    assert content.status == ContentStatus.ai, (
        f"auto_chain=False인데 status={content.status} — enriched→ai에서 정지해야 함"
    )


def test_auto_chain_true_high_score_approves(db, monkeypatch):
    """auto_chain=True + score≥90 → approved."""
    import api.programming.metadata.ai_engine as engine_mod
    monkeypatch.setattr(engine_mod, "_generate_metadata_with_engine", _mock_generate(95.0))

    content = _make_content(db)
    asyncio.run(engine_mod.process_content_ai(content.id, db, auto_chain=True, score_threshold=90))

    db.refresh(content)
    assert content.status == ContentStatus.approved, (
        f"score=95, threshold=90, auto_chain=True → approved 기대, 실제={content.status}"
    )


def test_auto_chain_true_low_score_goes_review(db, monkeypatch):
    """auto_chain=True + score<90 → review."""
    import api.programming.metadata.ai_engine as engine_mod
    monkeypatch.setattr(engine_mod, "_generate_metadata_with_engine", _mock_generate(75.0))

    content = _make_content(db)
    asyncio.run(engine_mod.process_content_ai(content.id, db, auto_chain=True, score_threshold=90))

    db.refresh(content)
    assert content.status == ContentStatus.review, (
        f"score=75, threshold=90, auto_chain=True → review 기대, 실제={content.status}"
    )


def test_stage_event_s6_recorded(db, monkeypatch):
    """S6_LLM_EXTRACT ENTERED/COMPLETED 이벤트가 기록되어야 한다."""
    import api.programming.metadata.ai_engine as engine_mod
    monkeypatch.setattr(engine_mod, "_generate_metadata_with_engine", _mock_generate(80.0))

    content = _make_content(db)
    asyncio.run(engine_mod.process_content_ai(content.id, db, auto_chain=False))

    events = (
        db.query(StageEvent)
        .filter(StageEvent.content_id == content.id, StageEvent.stage == PipelineStage.S6_LLM_EXTRACT)
        .all()
    )
    types = {e.event_type for e in events}
    assert StageEventType.ENTERED in types, "S6 ENTERED 이벤트 없음"
    assert StageEventType.COMPLETED in types, "S6 COMPLETED 이벤트 없음"


def test_content_ai_result_is_final(db, monkeypatch):
    """process_content_ai 실행 후 ContentAIResult is_final=True 레코드가 생성되어야 한다."""
    import api.programming.metadata.ai_engine as engine_mod
    monkeypatch.setattr(engine_mod, "_generate_metadata_with_engine", _mock_generate(88.0))

    content = _make_content(db)
    asyncio.run(engine_mod.process_content_ai(content.id, db, auto_chain=False))

    result = (
        db.query(ContentAIResult)
        .filter(ContentAIResult.content_id == content.id, ContentAIResult.is_final.is_(True))
        .first()
    )
    assert result is not None, "ContentAIResult is_final=True 레코드 없음"
    assert result.engine == "mock_engine"
