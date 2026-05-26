"""ADR-006 파이프라인 보드 API — board / gate advance / events / gate mode."""

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from shared.database import get_db
from api.programming.metadata.models import (
    Content, ContentStatus, StageEvent,
    PipelineStage, IntakeChannel, StageEventType, FailureCode,
)
from api.programming.metadata.stage_events import advance_gate, get_gate_pending
from api.programming.metadata.schemas_pipeline import (
    BoardResponse, ChannelStats, StageCount, GateInfo, AlertInfo,
    GateAdvanceRequest, GateAdvanceResponse,
    GateModeRequest,
    StageEventOut, PaginatedStageEvents,
    StageContentItem, StageSourceProgress,
)

router = APIRouter()

# gate 모드 글로벌 기본값 (in-memory MVP — 재시작 시 초기화됨)
_GATE_MODES: dict[str, str] = {f"GATE_{i}": "manual" for i in range(1, 7)}

# gate_id → 해당 gate에서 진입 대기 중인 stage 매핑
_GATE_STAGE: dict[str, str] = {
    "GATE_1": PipelineStage.S1_INTAKE.value,
    "GATE_2": PipelineStage.S3_LLM_EXTRACT.value,
    "GATE_3": PipelineStage.S5_GAP_DETECT.value,
    "GATE_4": PipelineStage.S6_WEBSEARCH_FILL.value,
    "GATE_5": PipelineStage.S7_STAGING.value,
    "GATE_6": PipelineStage.S8_REVIEW.value,
}

# 4개 intake channel 목록
_ALL_CHANNELS = [c.value for c in IntakeChannel]


def _compute_stage_stats(stage: PipelineStage, db: Session, now: datetime) -> dict:
    """해당 stage의 top contents + 평균 체류시간 + 최근 1h 에러 건수 계산.

    Returns:
        {"top_contents": [StageContentItem], "avg_seconds": int|None, "error_count": int}
    """
    # 해당 stage에 있는 콘텐츠
    pending = (
        db.query(Content)
        .filter(Content.current_stage == stage, Content.is_deleted.is_(False))
        .limit(50)
        .all()
    )

    if not pending:
        return {"top_contents": [], "avg_seconds": None, "error_count": 0}

    pending_ids = [c.id for c in pending]

    # 각 content의 해당 stage 최초 ENTERED 시각 조회 (1 query batch)
    entered_rows = (
        db.query(StageEvent.content_id, func.min(StageEvent.started_at).label("entered"))
        .filter(
            StageEvent.content_id.in_(pending_ids),
            StageEvent.stage == stage,
            StageEvent.event_type == StageEventType.ENTERED,
        )
        .group_by(StageEvent.content_id)
        .all()
    )
    entered_map: dict[int, datetime] = {r.content_id: r.entered for r in entered_rows}

    # 콘텐츠를 entered_at 오름차순 정렬 (가장 오래 머문 것부터)
    sorted_pending = sorted(
        pending,
        key=lambda c: entered_map.get(c.id, now),
    )
    top = sorted_pending[:5]

    # top 5의 stage 이벤트로 source 진행상황 집계 (1 query batch)
    top_ids = [c.id for c in top]
    sources_map: dict[int, list[StageSourceProgress]] = {cid: [] for cid in top_ids}

    if top_ids:
        stage_events = (
            db.query(StageEvent)
            .filter(StageEvent.content_id.in_(top_ids), StageEvent.stage == stage)
            .order_by(StageEvent.started_at.asc())
            .all()
        )
        # source별 마지막 이벤트로 result 결정
        per_content: dict[int, dict[str, StageEvent]] = {cid: {} for cid in top_ids}
        for ev in stage_events:
            src = ev.source
            if not src or src == "system":
                continue
            per_content[ev.content_id][src] = ev  # 최신으로 덮어쓰기

        for cid, src_map in per_content.items():
            for src, ev in sorted(src_map.items()):
                if ev.event_type in (StageEventType.COMPLETED, StageEventType.ADVANCED):
                    if stage == PipelineStage.S4_SOURCE_MATCH:
                        result_str = "hit"
                    else:
                        result_str = "ok"
                elif ev.event_type == StageEventType.SKIPPED:
                    result_str = "miss"
                elif ev.event_type == StageEventType.FAILED:
                    result_str = "error"
                else:
                    result_str = "pending"
                sources_map[cid].append(StageSourceProgress(
                    source=src, result=result_str, latency_ms=ev.latency_ms,
                ))

    # top_contents 빌드
    top_contents: list[StageContentItem] = []
    durations = []
    for c in top:
        entered_at = entered_map.get(c.id)
        sec_in_stage = None
        if entered_at:
            # tz-aware 비교를 위해 entered_at이 naive면 utc로 가정
            if entered_at.tzinfo is None:
                from datetime import timezone as _tz
                entered_at = entered_at.replace(tzinfo=_tz.utc)
            sec_in_stage = int((now - entered_at).total_seconds())
            durations.append(sec_in_stage)

        top_contents.append(StageContentItem(
            id=c.id,
            title=c.title or f"#{c.id}",
            entered_at=entered_at,
            seconds_in_stage=sec_in_stage,
            sources=sources_map.get(c.id, []),
        ))

    # 전체 대기 콘텐츠 평균 체류시간 (top 5 기준이 아닌 전체 pending)
    all_durations = []
    for c in pending:
        ea = entered_map.get(c.id)
        if ea:
            if ea.tzinfo is None:
                from datetime import timezone as _tz
                ea = ea.replace(tzinfo=_tz.utc)
            all_durations.append(int((now - ea).total_seconds()))
    avg_seconds = int(sum(all_durations) / len(all_durations)) if all_durations else None

    # 최근 1h FAILED 이벤트
    since_1h = now - timedelta(hours=1)
    error_count = (
        db.query(func.count())
        .filter(
            StageEvent.stage == stage,
            StageEvent.event_type == StageEventType.FAILED,
            StageEvent.started_at >= since_1h,
        )
        .scalar() or 0
    )

    return {
        "top_contents": top_contents,
        "avg_seconds": avg_seconds,
        "error_count": error_count,
    }


@router.get("/board", response_model=BoardResponse)
def get_pipeline_board(db: Session = Depends(get_db)):
    """파이프라인 현황 대시보드 — 24h 입수 채널 + stage count + gate 상태 + 알림."""
    now = datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)

    # ── 1. channels_24h ─────────────────────────────────────────────────────
    rows = (
        db.query(StageEvent.source, func.count().label("cnt"), func.max(StageEvent.started_at).label("last_at"))
        .filter(
            StageEvent.stage == PipelineStage.S1_INTAKE,
            StageEvent.event_type == StageEventType.ENTERED,
            StageEvent.started_at >= since_24h,
        )
        .group_by(StageEvent.source)
        .all()
    )
    source_map = {r.source: (r.cnt, r.last_at) for r in rows}

    channels_24h: dict[str, ChannelStats] = {}
    for ch in _ALL_CHANNELS:
        cnt, last_at = source_map.get(ch, (0, None))
        # stale: 마지막 입수가 1시간 이상 전이면 stale
        status = "ok"
        if last_at and (now - last_at).total_seconds() > 3600:
            status = "stale"
        channels_24h[ch] = ChannelStats(count=cnt, last_at=last_at, status=status)

    # ── 2. stages count ──────────────────────────────────────────────────────
    stage_rows = (
        db.query(Content.current_stage, func.count().label("cnt"))
        .filter(Content.is_deleted.is_(False), Content.current_stage.isnot(None))
        .group_by(Content.current_stage)
        .all()
    )
    stage_map = {r.current_stage.value: r.cnt for r in stage_rows}

    total_published = db.query(func.count()).filter(
        Content.current_stage == PipelineStage.S9_PUBLISH,
        Content.is_deleted.is_(False),
    ).scalar() or 0

    stages: dict[str, StageCount] = {}
    for s in PipelineStage:
        cnt = stage_map.get(s.value, 0)
        stats = _compute_stage_stats(s, db, now) if cnt > 0 else {
            "top_contents": [], "avg_seconds": None, "error_count": 0,
        }
        stages[s.value] = StageCount(
            count=cnt,
            total_published=total_published if s == PipelineStage.S9_PUBLISH else None,
            top_contents=stats["top_contents"],
            avg_seconds=stats["avg_seconds"],
            error_count=stats["error_count"],
        )

    # ── 3. gates ─────────────────────────────────────────────────────────────
    gates: dict[str, GateInfo] = {}
    for gate_id in _GATE_MODES:
        pending_contents = get_gate_pending(db, gate_id)
        gates[gate_id] = GateInfo(
            mode=_GATE_MODES[gate_id],
            pending=len(pending_contents),
        )

    # ── 4. alerts ─────────────────────────────────────────────────────────────
    failed_queue = (
        db.query(func.count())
        .filter(Content.failure_code != FailureCode.NONE, Content.is_deleted.is_(False))
        .scalar() or 0
    )
    rejected_archive = (
        db.query(func.count())
        .filter(Content.status == ContentStatus.rejected, Content.is_deleted.is_(False))
        .scalar() or 0
    )
    # enrichment_blocked: S3에서 멈춘 콘텐츠 (ENTERED 있고 COMPLETED 없음)
    enrichment_blocked = (
        db.query(func.count())
        .filter(Content.current_stage == PipelineStage.S3_LLM_EXTRACT, Content.is_deleted.is_(False))
        .scalar() or 0
    )

    return BoardResponse(
        channels_24h=channels_24h,
        stages=stages,
        gates=gates,
        alerts=AlertInfo(
            failed_queue=failed_queue,
            rejected_archive=rejected_archive,
            enrichment_blocked=enrichment_blocked,
        ),
    )


@router.post("/gate/{gate_id}/advance", response_model=GateAdvanceResponse)
def advance_gate_endpoint(
    gate_id: str,
    req: GateAdvanceRequest,
    db: Session = Depends(get_db),
):
    """Gate advance — GATE_1~6 수동 진행. If-Match로 동시 충돌 방지."""
    if gate_id not in _GATE_MODES:
        raise HTTPException(status_code=400, detail=f"unknown gate_id: {gate_id}")

    # content_ids 비어있으면 gate 대기 전체
    content_ids = req.content_ids
    if not content_ids:
        content_ids = [c.id for c in get_gate_pending(db, gate_id)]

    if not content_ids:
        return GateAdvanceResponse(advanced=0, skipped=0, failed=0, next_stage="", events=[])

    # If-Match 충돌 체크 — 클라이언트 if_match 이후 새 이벤트가 있으면 409
    if req.if_match is not None:
        conflict = (
            db.query(StageEvent)
            .filter(StageEvent.content_id.in_(content_ids), StageEvent.id > req.if_match)
            .first()
        )
        if conflict:
            raise HTTPException(
                status_code=409,
                detail={"message": "Conflict: newer events exist since if_match", "conflict_event_id": conflict.id},
            )

    result = advance_gate(db, gate_id, content_ids, simulate=req.simulate, actor="api")

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    # simulate 응답 처리
    if req.simulate:
        return GateAdvanceResponse(
            advanced=0,
            skipped=0,
            failed=0,
            next_stage=result.get("next_stage", ""),
            events=[{"simulated": True, "count": result.get("count", 0)}],
        )

    return GateAdvanceResponse(
        advanced=result.get("advanced", 0),
        skipped=result.get("skipped", 0),
        failed=result.get("failed", 0),
        next_stage=result.get("next_stage", ""),
        events=[],
    )


@router.get("/events", response_model=PaginatedStageEvents)
def get_pipeline_events(
    since: int = Query(0, description="이 event_id 이후부터 조회"),
    limit: int = Query(50, le=200),
    stage: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """StageEvent 페이징 조회 — Live Log 용."""
    q = db.query(StageEvent).filter(StageEvent.id > since)

    if stage:
        try:
            q = q.filter(StageEvent.stage == PipelineStage(stage))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"unknown stage: {stage}")

    if source:
        q = q.filter(StageEvent.source == source)

    if event_type:
        try:
            q = q.filter(StageEvent.event_type == StageEventType(event_type))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"unknown event_type: {event_type}")

    total = q.count()
    items = q.order_by(StageEvent.id.asc()).limit(limit + 1).all()

    next_cursor = None
    if len(items) > limit:
        next_cursor = items[limit - 1].id
        items = items[:limit]

    return PaginatedStageEvents(
        items=[StageEventOut.model_validate(e) for e in items],
        next_cursor=next_cursor,
        total=total,
    )


@router.post("/gate/{gate_id}/mode")
def set_gate_mode(gate_id: str, req: GateModeRequest):
    """Gate 수동/자동 모드 토글."""
    if gate_id not in _GATE_MODES:
        raise HTTPException(status_code=400, detail=f"unknown gate_id: {gate_id}")
    if req.mode not in ("manual", "auto"):
        raise HTTPException(status_code=400, detail="mode must be 'manual' or 'auto'")
    _GATE_MODES[gate_id] = req.mode
    return {"gate_id": gate_id, "mode": req.mode}
