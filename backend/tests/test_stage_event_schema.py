"""ADR-006 dpf-schema Step 1 검증 — enum / StageEvent CRUD / Content 컬럼 / 인덱스."""

import pytest
from sqlalchemy import inspect

from api.programming.metadata.models.content import (
    Content, ContentStatus, ContentType,
    PipelineStage, IntakeChannel, StageEventType, FailureCode,
)
from api.programming.metadata.models.stage_event import StageEvent


# ── 1. enum value 매핑 ──────────────────────────────────────────────────────

def test_enum_values():
    assert PipelineStage.S1_INTAKE.value    == "s1_intake"
    assert PipelineStage.S9_PUBLISH.value   == "s9_publish"
    assert len(PipelineStage)               == 9

    assert IntakeChannel.EMAIL_POLL.value   == "email_poll"
    assert IntakeChannel.DAM_WEBHOOK.value  == "dam_webhook"
    assert len(IntakeChannel)               == 4

    assert StageEventType.GATE_OPENED.value == "gate_opened"
    assert StageEventType.ADVANCED.value    == "advanced"
    assert len(StageEventType)              == 7

    assert FailureCode.NONE.value           == "none"
    assert FailureCode.SYSTEM_ERROR.value   == "system_error"
    assert len(FailureCode)                 == 7


# ── 2. StageEvent CRUD ──────────────────────────────────────────────────────

def test_stage_event_crud(db):
    content = Content(
        title="테스트 영화",
        content_type=ContentType.movie,
        status=ContentStatus.processing,
    )
    db.add(content)
    db.flush()

    event = StageEvent(
        content_id=content.id,
        stage=PipelineStage.S3_LLM_EXTRACT,
        event_type=StageEventType.ENTERED,
        source="ollama",
        actor="system",
    )
    db.add(event)
    db.commit()

    fetched = db.query(StageEvent).filter_by(content_id=content.id).first()
    assert fetched is not None
    assert fetched.stage      == PipelineStage.S3_LLM_EXTRACT
    assert fetched.event_type == StageEventType.ENTERED
    assert fetched.source     == "ollama"
    assert fetched.actor      == "system"


# ── 3. Content 신규 컬럼 nullable 동작 ──────────────────────────────────────

def test_content_new_columns_nullable(db):
    content = Content(
        title="nullable 컬럼 테스트",
        content_type=ContentType.movie,
        status=ContentStatus.waiting,
    )
    db.add(content)
    db.commit()
    db.refresh(content)

    # intake_channel, current_stage, gate_overrides 는 nullable
    assert content.intake_channel is None
    assert content.current_stage  is None
    assert content.gate_overrides is None
    # failure_code 는 default="none"
    assert content.failure_code == FailureCode.NONE


# ── 4. backfill 매핑 정확성 ─────────────────────────────────────────────────

@pytest.mark.parametrize("status,expected_stage", [
    (ContentStatus.waiting,    PipelineStage.S1_INTAKE),
    (ContentStatus.processing, PipelineStage.S3_LLM_EXTRACT),
    (ContentStatus.staging,    PipelineStage.S7_STAGING),
    (ContentStatus.review,     PipelineStage.S8_REVIEW),
    (ContentStatus.approved,   PipelineStage.S8_REVIEW),
    (ContentStatus.rejected,   PipelineStage.S8_REVIEW),
])
def test_backfill_stage_mapping(db, status, expected_stage):
    # migration backfill 로직을 Python 레벨에서 재현
    STATUS_TO_STAGE = {
        ContentStatus.waiting:    PipelineStage.S1_INTAKE,
        ContentStatus.processing: PipelineStage.S3_LLM_EXTRACT,
        ContentStatus.staging:    PipelineStage.S7_STAGING,
        ContentStatus.review:     PipelineStage.S8_REVIEW,
        ContentStatus.approved:   PipelineStage.S8_REVIEW,
        ContentStatus.rejected:   PipelineStage.S8_REVIEW,
    }
    content = Content(
        title=f"backfill test {status.value}",
        content_type=ContentType.movie,
        status=status,
    )
    db.add(content)
    db.flush()
    content.current_stage = STATUS_TO_STAGE.get(status)
    db.commit()
    db.refresh(content)
    assert content.current_stage == expected_stage


# ── 5. stage_event 인덱스 존재 확인 ─────────────────────────────────────────

def test_stage_event_indexes(db):
    inspector = inspect(db.bind)
    indexes = {idx["name"] for idx in inspector.get_indexes("stage_event")}
    assert "ix_stage_event_content_stage"  in indexes
    assert "ix_stage_event_event_started"  in indexes
