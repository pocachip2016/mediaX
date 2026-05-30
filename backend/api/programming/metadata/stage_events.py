"""Stage event helpers — ADR-006 record_stage_event / derive_status / advance_gate."""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.programming.metadata.models.content import (
    Content, ContentStatus,
    PipelineStage, IntakeChannel, StageEventType, FailureCode,
)
from api.programming.metadata.models.stage_event import StageEvent

logger = logging.getLogger(__name__)

_PAYLOAD_MAX_BYTES = 4096


def _truncate_payload(payload: dict) -> dict:
    raw = json.dumps(payload, ensure_ascii=False)
    if len(raw.encode()) <= _PAYLOAD_MAX_BYTES:
        return payload
    # 핵심 키만 보존 + _truncated flag
    keys = list(payload.keys())[:8]
    return {k: payload[k] for k in keys} | {"_truncated": True}


def record_stage_event(
    db: Session,
    content_id: int,
    stage: PipelineStage,
    event_type: StageEventType,
    *,
    source: Optional[str] = None,
    payload: Optional[dict] = None,
    error: Optional[str] = None,
    actor: str = "system",
    latency_ms: Optional[int] = None,
) -> StageEvent:
    """StageEvent 1건 삽입 + content.current_stage 갱신."""
    safe_payload = _truncate_payload(payload) if payload else None
    event = StageEvent(
        content_id=content_id,
        stage=stage,
        event_type=event_type,
        source=source,
        started_at=datetime.now(timezone.utc),
        latency_ms=latency_ms,
        payload_json=safe_payload,
        error_text=error,
        actor=actor,
    )
    db.add(event)

    # current_stage + status 동기 갱신
    content = db.get(Content, content_id)
    if content:
        content.current_stage = stage
        new_status = derive_status_from_stage(stage)
        if new_status and event_type in (StageEventType.ENTERED, StageEventType.COMPLETED, StageEventType.ADVANCED):
            content.status = new_status
        if event_type == StageEventType.FAILED and error:
            content.failure_code = FailureCode.SYSTEM_ERROR

    db.flush()
    return event


# S3 이후 stage는 status를 바꾸지 않는 것이 많으므로 None 반환
_STAGE_TO_STATUS: dict[PipelineStage, Optional[ContentStatus]] = {
    PipelineStage.S1_INTAKE:         ContentStatus.raw,
    PipelineStage.S2_NORMALIZE:      ContentStatus.enriched,
    PipelineStage.S3_SOURCE_MATCH:   ContentStatus.enriched,
    PipelineStage.S4_GAP_DETECT:     ContentStatus.enriched,
    PipelineStage.S5_WEBSEARCH_FILL: ContentStatus.enriched,
    PipelineStage.S6_LLM_EXTRACT:    ContentStatus.ai,    # ADR-007: S6(WebSearch) 이후 실행
    PipelineStage.S7_STAGING:        ContentStatus.ai,
    PipelineStage.S8_REVIEW:         ContentStatus.review,
    PipelineStage.S9_PUBLISH:        ContentStatus.approved,
}


def derive_status_from_stage(stage: PipelineStage) -> Optional[ContentStatus]:
    """Stage → ContentStatus 단방향 매핑 (D3 SSOT)."""
    return _STAGE_TO_STATUS.get(stage)


def advance_gate(
    db: Session,
    gate_id: str,
    content_ids: list[int],
    *,
    simulate: bool = False,
    actor: str = "system",
) -> dict:
    """Gate 수동 진행 — GATE_1~6 매핑으로 다음 stage 이동 (Step 4에서 완성)."""
    # stub: gate_id → next_stage 매핑은 Step 4(board-api)에서 구현
    _GATE_NEXT: dict[str, PipelineStage] = {
        "GATE_1": PipelineStage.S2_NORMALIZE,
        "GATE_2": PipelineStage.S3_SOURCE_MATCH,
        "GATE_3": PipelineStage.S5_WEBSEARCH_FILL,
        "GATE_4": PipelineStage.S7_STAGING,
        "GATE_5": PipelineStage.S8_REVIEW,
        "GATE_6": PipelineStage.S9_PUBLISH,
    }
    next_stage = _GATE_NEXT.get(gate_id)
    if not next_stage:
        return {"error": f"unknown gate_id {gate_id}", "advanced": 0}
    if simulate:
        return {"simulated": True, "gate_id": gate_id, "next_stage": next_stage.value, "count": len(content_ids)}

    advanced = 0
    for cid in content_ids:
        record_stage_event(db, cid, next_stage, StageEventType.GATE_OPENED, actor=actor)
        record_stage_event(db, cid, next_stage, StageEventType.ADVANCED, actor=actor)
        advanced += 1
    db.commit()
    return {"advanced": advanced, "next_stage": next_stage.value}


def get_gate_pending(db: Session, gate_id: str) -> list[Content]:
    """Gate 대기 중 Content 목록 (Step 4에서 board API와 연결)."""
    _GATE_STAGE: dict[str, PipelineStage] = {
        "GATE_1": PipelineStage.S1_INTAKE,
        "GATE_2": PipelineStage.S6_LLM_EXTRACT,
        "GATE_3": PipelineStage.S4_GAP_DETECT,
        "GATE_4": PipelineStage.S5_WEBSEARCH_FILL,
        "GATE_5": PipelineStage.S7_STAGING,
        "GATE_6": PipelineStage.S8_REVIEW,
    }
    stage = _GATE_STAGE.get(gate_id)
    if not stage:
        return []
    return (
        db.query(Content)
        .filter(Content.current_stage == stage, Content.is_deleted == False)  # noqa: E712
        .all()
    )
