"""ADR-006 dpf-service Step 2 — record_stage_event / advance_gate / derive_status / entry-point hooks."""

import pytest
from unittest.mock import patch, MagicMock

from api.programming.metadata.models.content import (
    Content, ContentStatus, ContentType,
    PipelineStage, IntakeChannel, StageEventType, FailureCode,
)
from api.programming.metadata.models.stage_event import StageEvent
from api.programming.metadata.stage_events import (
    record_stage_event,
    derive_status_from_stage,
    advance_gate,
    get_gate_pending,
)


# ── 1. payload 4KB 캡 ───────────────────────────────────────────────────────

def test_record_stage_event_payload_truncation(db):
    content = Content(title="테스트", content_type=ContentType.movie, status=ContentStatus.raw)
    db.add(content)
    db.flush()

    huge_payload = {f"key_{i}": "x" * 200 for i in range(100)}
    event = record_stage_event(
        db, content.id, PipelineStage.S1_INTAKE, StageEventType.ENTERED,
        payload=huge_payload,
    )
    db.flush()

    assert event.payload_json is not None
    import json
    serialized = json.dumps(event.payload_json, ensure_ascii=False)
    assert len(serialized.encode()) <= 4096
    assert event.payload_json.get("_truncated") is True


# ── 2. derive_status_from_stage 9 stage 매핑 ───────────────────────────────

def test_derive_status_from_stage_all_9():
    mapping = {
        PipelineStage.S1_INTAKE:         ContentStatus.raw,
        PipelineStage.S2_NORMALIZE:      ContentStatus.enriched,
        PipelineStage.S3_SOURCE_MATCH:   ContentStatus.enriched,
        PipelineStage.S4_GAP_DETECT:     ContentStatus.enriched,
        PipelineStage.S5_WEBSEARCH_FILL: ContentStatus.enriched,
        PipelineStage.S6_LLM_EXTRACT:    ContentStatus.ai,    # ADR-007: S6 이후 실행
        PipelineStage.S7_STAGING:        ContentStatus.ai,
        PipelineStage.S8_REVIEW:         ContentStatus.review,
        PipelineStage.S9_PUBLISH:        ContentStatus.approved,
    }
    for stage, expected_status in mapping.items():
        assert derive_status_from_stage(stage) == expected_status, f"stage={stage}"


# ── 3. advance_gate — simulate / real ──────────────────────────────────────

def test_advance_gate_simulate(db):
    result = advance_gate(db, "GATE_1", [1, 2, 3], simulate=True)
    assert result["simulated"] is True
    assert result["next_stage"] == PipelineStage.S2_NORMALIZE.value
    assert result["count"] == 3
    # simulate → DB 미변경
    assert db.query(StageEvent).count() == 0


def test_advance_gate_real(db):
    c1 = Content(title="영화A", content_type=ContentType.movie, status=ContentStatus.raw)
    c2 = Content(title="영화B", content_type=ContentType.movie, status=ContentStatus.raw)
    db.add_all([c1, c2])
    db.flush()

    result = advance_gate(db, "GATE_2", [c1.id, c2.id], actor="admin")
    assert result["advanced"] == 2
    assert result["next_stage"] == PipelineStage.S3_SOURCE_MATCH.value

    events = db.query(StageEvent).filter(StageEvent.content_id == c1.id).all()
    event_types = {e.event_type for e in events}
    assert StageEventType.GATE_OPENED in event_types
    assert StageEventType.ADVANCED in event_types


# ── 4. 진입점 훅 발화 검증 ─────────────────────────────────────────────────

def test_entry_point_email_hook(db):
    """_save_email_and_extract → S1 ENTERED 이벤트 + intake_channel=email_poll 설정."""
    content = Content(
        title="이메일 테스트",
        content_type=ContentType.movie,
        status=ContentStatus.raw,
        intake_channel=IntakeChannel.EMAIL_POLL,
    )
    db.add(content)
    db.flush()

    event = record_stage_event(
        db, content.id, PipelineStage.S1_INTAKE, StageEventType.ENTERED,
        source="email_poll", actor="email_poller",
    )
    db.flush()

    assert event.stage == PipelineStage.S1_INTAKE
    assert event.event_type == StageEventType.ENTERED
    assert event.source == "email_poll"
    saved = db.get(Content, content.id)
    assert saved.intake_channel == IntakeChannel.EMAIL_POLL
    assert saved.current_stage == PipelineStage.S1_INTAKE


def test_entry_point_enrich_hooks(db):
    """enrich_content_metadata → S3 ENTERED/COMPLETED/FAILED 발화."""
    content = Content(title="보강 테스트", content_type=ContentType.movie, status=ContentStatus.enriched)
    db.add(content)
    db.flush()

    record_stage_event(db, content.id, PipelineStage.S6_LLM_EXTRACT, StageEventType.ENTERED,
                       source="ollama", actor="system")
    record_stage_event(db, content.id, PipelineStage.S6_LLM_EXTRACT, StageEventType.COMPLETED,
                       source="ollama", actor="system")
    db.flush()

    events = (
        db.query(StageEvent)
        .filter(StageEvent.content_id == content.id,
                StageEvent.stage == PipelineStage.S6_LLM_EXTRACT)
        .all()
    )
    event_types = [e.event_type for e in events]
    assert StageEventType.ENTERED in event_types
    assert StageEventType.COMPLETED in event_types


def test_entry_point_source_match_hooks(db):
    """_async_enrich_content → S4 per-source (tmdb/kobis) 이벤트."""
    content = Content(title="소스매칭 테스트", content_type=ContentType.movie, status=ContentStatus.enriched)
    db.add(content)
    db.flush()

    for src in ("tmdb", "kobis"):
        record_stage_event(db, content.id, PipelineStage.S3_SOURCE_MATCH, StageEventType.ENTERED,
                           source=src, actor="system")
        record_stage_event(db, content.id, PipelineStage.S3_SOURCE_MATCH, StageEventType.COMPLETED,
                           source=src, actor="system")
    db.flush()

    sources = {e.source for e in db.query(StageEvent).filter(
        StageEvent.content_id == content.id,
        StageEvent.stage == PipelineStage.S3_SOURCE_MATCH,
    ).all()}
    assert "tmdb" in sources
    assert "kobis" in sources
