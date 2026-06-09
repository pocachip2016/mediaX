"""auto_service.py — 자동편성 파이프라인 코어 서비스 (ADR-012).

엔드포인트와 Celery Beat 양쪽에서 호출되는 순수 비즈니스 로직.
- claim_bucket: FOR UPDATE SKIP LOCKED + auto_hold 필터 + visibility_timeout 재claim
- advance_one: 멱등 P-stage 전이 + per-stage 실행 + SchedulingStageEvent 기록
- run_to_stable: 더 진행 불가/검수 잔류까지 반복 advance (온디맨드·Beat 공용)
- recompute_schedule_score: 편성 완성도 0~100
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import TypedDict

from sqlalchemy.orm import Session

from .models import (
    AutoEventType,
    AutoStage,
    ProgrammingLink,
    ProgrammingNode,
    ProgrammingNodeSet,
    ScheduleAutoPolicy,
    SchedulingStageEvent,
    LinkStatus,
)

logger = logging.getLogger(__name__)

# ── 버킷 / 전이 매핑 ──────────────────────────────────────────────────────────

_STAGE_BUCKET: dict[str, int] = {
    AutoStage.P1_DEFINE.value:      1,
    AutoStage.P2_CANDIDATE.value:   2,
    AutoStage.P3_MATCH.value:       2,
    AutoStage.P4_AUTOCONFIRM.value: 3,
    AutoStage.P5_CONFLICT.value:    4,
    AutoStage.P6_PUBLISH.value:     5,
}

_BUCKET_NEXT_STAGE: dict[int, AutoStage] = {
    1: AutoStage.P2_CANDIDATE,
    2: AutoStage.P4_AUTOCONFIRM,
    3: AutoStage.P5_CONFLICT,
    4: AutoStage.P6_PUBLISH,
}

# claim 시 허용 버킷 4는 auto_skipped_at 없는 것만
_TERMINAL_BUCKET = 5


def node_bucket(node: ProgrammingNode) -> int:
    """노드 → 버킷 번호."""
    return _STAGE_BUCKET.get(node.auto_stage.value if node.auto_stage else "", 1)


# ── 정책 헬퍼 ─────────────────────────────────────────────────────────────────

def get_policy(db: Session) -> ScheduleAutoPolicy:
    """ScheduleAutoPolicy 싱글톤 반환. 없으면 id=1 행 생성."""
    policy = db.get(ScheduleAutoPolicy, 1)
    if policy is None:
        policy = ScheduleAutoPolicy(id=1)
        db.add(policy)
        db.flush()
    return policy


# ── 이벤트 기록 ───────────────────────────────────────────────────────────────

def _record_event(
    db: Session,
    node_id: int,
    stage: AutoStage,
    event_type: AutoEventType,
    *,
    actor: str = "system",
    source: str | None = None,
    payload_json: dict | None = None,
    error_text: str | None = None,
) -> None:
    ev = SchedulingStageEvent(
        node_id=node_id,
        stage=stage,
        event_type=event_type,
        source=source,
        started_at=datetime.now(timezone.utc),
        actor=actor,
        payload_json=payload_json,
        error_text=error_text,
    )
    db.add(ev)
    db.flush()


# ── claim_bucket ──────────────────────────────────────────────────────────────

def claim_bucket(
    db: Session,
    bucket: int,
    batch_size: int,
    visibility_timeout: int,
) -> list[ProgrammingNode]:
    """버킷 내 처리 가능 노드를 최대 batch_size 건 claim하여 반환.

    조건:
    - auto_enabled=True
    - auto_hold=False
    - bucket 일치 (auto_stage 기준; None → bucket 1)
    - auto_claimed_at 없거나 visibility_timeout 초과 (stuck 재claim)
    - bucket 4(P5): auto_skipped_at 없는 것만
    - SELECT FOR UPDATE SKIP LOCKED — 동시 워커 중복 방지
    """
    from sqlalchemy import or_

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=visibility_timeout)

    stages_in_bucket = [
        stage for stage, b in _STAGE_BUCKET.items() if b == bucket
    ]
    include_null_stage = (bucket == 1)

    q = db.query(ProgrammingNode).filter(
        ProgrammingNode.auto_enabled.is_(True),
        ProgrammingNode.auto_hold.is_(False),
    )

    if include_null_stage:
        q = q.filter(
            or_(
                ProgrammingNode.auto_stage.is_(None),
                ProgrammingNode.auto_stage.in_(stages_in_bucket),
            )
        )
    else:
        q = q.filter(ProgrammingNode.auto_stage.in_(stages_in_bucket))

    q = q.filter(
        or_(
            ProgrammingNode.auto_claimed_at.is_(None),
            ProgrammingNode.auto_claimed_at < cutoff,
        )
    )

    # bucket 4(검수): 이미 임계값 미달 잔류 판정된 노드 제외
    if bucket == 4:
        q = q.filter(ProgrammingNode.auto_skipped_at.is_(None))

    # SQLite는 SKIP LOCKED 미지원 — 테스트/개발 환경 방어
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        rows = q.with_for_update(skip_locked=True).limit(batch_size).all()
    else:
        rows = q.limit(batch_size).all()

    for node in rows:
        node.auto_claimed_at = now
    db.flush()

    return rows


def _release_claim(db: Session, node: ProgrammingNode) -> None:
    node.auto_claimed_at = None
    db.flush()


# ── advance_one (멱등) ────────────────────────────────────────────────────────

class AdvanceResult(TypedDict):
    node_id: int
    result: str  # "ok" | "not_found" | "terminal" | "hold" | "already_moved" | "skipped"


def advance_one(
    db: Session,
    node_id: int,
    actor: str = "auto",
) -> AdvanceResult:
    """단건 멱등 advance.

    반환 result:
    - "ok": 정상 전이
    - "not_found": 노드 없음
    - "terminal": 이미 P6 또는 terminal bucket
    - "hold": auto_hold=True (AUTO 워커 차단)
    - "already_moved": 다른 actor가 이미 이동
    - "skipped": P4 잔류 마킹됨 (임계값 미달)
    """
    node = (
        db.query(ProgrammingNode)
        .filter(ProgrammingNode.id == node_id)
        .with_for_update()
        .first()
    )
    if node is None:
        return AdvanceResult(node_id=node_id, result="not_found")

    if node.auto_hold:
        if actor == "auto":
            return AdvanceResult(node_id=node_id, result="hold")
        node.auto_hold = False  # 운영자 수동 진행 → hold 해제

    cur_bucket = _STAGE_BUCKET.get(node.auto_stage.value if node.auto_stage else "", 1)

    if cur_bucket >= _TERMINAL_BUCKET:
        return AdvanceResult(node_id=node_id, result="terminal")

    next_stage = _BUCKET_NEXT_STAGE.get(cur_bucket)
    if next_stage is None:
        return AdvanceResult(node_id=node_id, result="terminal")

    # per-stage 실행
    try:
        _execute_stage(db, node, next_stage, actor=actor)
    except Exception as exc:
        _record_event(
            db, node_id, next_stage, AutoEventType.FAILED,
            actor=actor, error_text=str(exc),
        )
        _release_claim(db, node)
        raise

    # P4에서 auto_skipped_at 마킹된 경우 → 전이 없이 잔류
    if next_stage == AutoStage.P4_AUTOCONFIRM and node.auto_skipped_at is not None:
        _release_claim(db, node)
        return AdvanceResult(node_id=node_id, result="skipped")

    node.auto_stage = next_stage
    _record_event(db, node_id, next_stage, AutoEventType.ADVANCED, actor=actor)
    _release_claim(db, node)
    db.flush()
    return AdvanceResult(node_id=node_id, result="ok")


def _execute_stage(
    db: Session,
    node: ProgrammingNode,
    stage: AutoStage,
    actor: str,
) -> None:
    """각 P-stage 진입 시 실행되는 로직."""

    if stage == AutoStage.P2_CANDIDATE:
        _exec_p2_candidate(db, node, actor)

    elif stage == AutoStage.P3_MATCH:
        _exec_p3_match(db, node, actor)

    elif stage == AutoStage.P4_AUTOCONFIRM:
        _exec_p4_autoconfirm(db, node, actor)

    elif stage == AutoStage.P5_CONFLICT:
        _exec_p5_conflict(db, node, actor)

    elif stage == AutoStage.P6_PUBLISH:
        _exec_p6_publish(db, node, actor)


def _exec_p2_candidate(db: Session, node: ProgrammingNode, actor: str) -> None:
    """P2: Tier0 규칙으로 후보 콘텐츠 수 산출 (read-time, 저장 안 함)."""
    from .rule_engine import apply_rule_query

    rule_query = node.rule_query or {}
    candidates = apply_rule_query(db, rule_query)
    _record_event(
        db, node.id, AutoStage.P2_CANDIDATE, AutoEventType.COMPLETED,
        actor=actor,
        payload_json={"candidate_count": len(candidates)},
    )


def _exec_p3_match(db: Session, node: ProgrammingNode, actor: str) -> None:
    """P3: Tier1 의도해석(headline_copy 있으면) + Tier2 의미매칭 → suggested 링크 저장."""
    from .intent_service import interpret_intent, apply_intent_to_node
    from .suggest_service import suggest_links

    policy = get_policy(db)

    # Tier1: headline_copy → rule_query + facets 갱신
    if node.headline_copy and node.headline_copy.strip():
        try:
            intent_result = asyncio.run(interpret_intent(node.headline_copy))
            apply_intent_to_node(node, intent_result)
            db.flush()
        except Exception as exc:
            logger.warning("[auto_service] P3 intent 해석 실패 (Tier0 폴백): node_id=%d err=%s", node.id, exc)

    # Tier2: suggest_links
    result = suggest_links(db, node, threshold=policy.confidence_threshold)
    _record_event(
        db, node.id, AutoStage.P3_MATCH, AutoEventType.COMPLETED,
        actor=actor,
        payload_json={
            "suggested_saved": len(result.saved),
            "skipped_below_threshold": result.skipped_count,
        },
    )


def _exec_p4_autoconfirm(db: Session, node: ProgrammingNode, actor: str) -> None:
    """P4: confidence ≥ threshold suggested → active. 미달 1건↑ 존재 시 auto_skipped_at 마킹."""
    from .suggest_service import confirm_link

    policy = get_policy(db)
    threshold = policy.confidence_threshold

    suggested_links = (
        db.query(ProgrammingLink)
        .filter(
            ProgrammingLink.parent_node_id == node.id,
            ProgrammingLink.status == LinkStatus.suggested,
        )
        .all()
    )

    confirmed = 0
    residual = 0
    for lnk in suggested_links:
        if (lnk.confidence or 0.0) >= threshold:
            confirm_link(db, lnk.id)
            confirmed += 1
        else:
            residual += 1

    if residual > 0:
        # 임계값 미달 링크 잔류 → 검수 대기 마킹 (자동 재진입 차단)
        node.auto_skipped_at = datetime.now(timezone.utc)
        db.flush()

    recompute_schedule_score(db, node)
    _record_event(
        db, node.id, AutoStage.P4_AUTOCONFIRM, AutoEventType.COMPLETED,
        actor=actor,
        payload_json={
            "confirmed": confirmed,
            "residual_below_threshold": residual,
            "auto_skipped": residual > 0,
        },
    )


def _exec_p5_conflict(db: Session, node: ProgrammingNode, actor: str) -> None:
    """P5: set 내 노출 window 충돌 검사. blocking 충돌 있으면 auto_hold=True."""
    from .conflict_service import detect_conflicts

    if node.set_id is None:
        recompute_schedule_score(db, node)
        _record_event(
            db, node.id, AutoStage.P5_CONFLICT, AutoEventType.COMPLETED,
            actor=actor,
            payload_json={"conflict_count": 0, "blocking_count": 0},
        )
        return

    report = detect_conflicts(db, node.set_id)
    if report["blocking_count"] > 0:
        node.auto_hold = True
        db.flush()

    recompute_schedule_score(db, node)
    _record_event(
        db, node.id, AutoStage.P5_CONFLICT, AutoEventType.COMPLETED,
        actor=actor,
        payload_json={
            "conflict_count": report["conflict_count"],
            "blocking_count": report["blocking_count"],
            "window_overlap_count": report["window_overlap_count"],
            "duplicate_content_count": report["duplicate_content_count"],
            "held": report["blocking_count"] > 0,
        },
    )


def _exec_p6_publish(db: Session, node: ProgrammingNode, actor: str) -> None:
    """P6: blocking 충돌 없을 때만 NodeSet 발행. 충돌 있으면 hold."""
    from .node_service import publish_node_set
    from .conflict_service import detect_conflicts

    if node.set_id is not None:
        report = detect_conflicts(db, node.set_id)
        if report["blocking_count"] > 0:
            node.auto_hold = True
            db.flush()
            _record_event(
                db, node.id, AutoStage.P6_PUBLISH, AutoEventType.SKIPPED,
                actor=actor,
                payload_json={
                    "reason": "blocking_conflicts",
                    "blocking_count": report["blocking_count"],
                    "published": False,
                },
            )
            return

    ns = db.get(ProgrammingNodeSet, node.set_id)
    if ns is not None and ns.status != "published":
        publish_node_set(db, node.set_id)

    _record_event(
        db, node.id, AutoStage.P6_PUBLISH, AutoEventType.COMPLETED,
        actor=actor,
        payload_json={"set_id": node.set_id, "published": True},
    )


# ── run_to_stable ─────────────────────────────────────────────────────────────

class RunResult(TypedDict):
    node_id: int
    stages_advanced: int
    final_result: str  # 마지막 advance_one result


def run_to_stable(
    db: Session,
    node_id: int,
    *,
    actor: str = "user",
    max_steps: int = 10,
) -> RunResult:
    """P-stage 가 terminal/잔류/hold/오류에 도달할 때까지 advance_one 반복.

    온디맨드(콘솔 run-to-stable 버튼) + Beat tick 공용.
    max_steps: 무한루프 방지 안전장치.
    """
    advanced = 0
    last_result = "not_found"

    for _ in range(max_steps):
        result = advance_one(db, node_id, actor=actor)
        last_result = result["result"]

        if last_result == "ok":
            advanced += 1
            db.commit()
            continue

        # terminal / hold / skipped / not_found → 안정점 도달
        break

    return RunResult(node_id=node_id, stages_advanced=advanced, final_result=last_result)


# ── recompute_schedule_score ──────────────────────────────────────────────────

def recompute_schedule_score(db: Session, node: ProgrammingNode) -> float:
    """편성 완성도 0~100. P5/P4 진입 시 갱신.

    기준:
    - rule_query 또는 headline_copy 정의 여부 (30점)
    - window_start/end 정의 여부 (20점)
    - active 링크 수: 1건=10, 5건=20, 10건+=30점 (상한 30점)
    - schedule_score에 기록
    """
    score = 0.0

    if node.rule_query or (node.headline_copy and node.headline_copy.strip()):
        score += 30.0

    if node.window_start and node.window_end:
        score += 20.0

    active_count = (
        db.query(ProgrammingLink)
        .filter(
            ProgrammingLink.parent_node_id == node.id,
            ProgrammingLink.status == LinkStatus.active,
        )
        .count()
    )
    if active_count >= 10:
        score += 30.0
    elif active_count >= 5:
        score += 20.0
    elif active_count >= 1:
        score += 10.0

    node.schedule_score = min(score, 100.0)
    db.flush()
    return node.schedule_score
