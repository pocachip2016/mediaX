"""
Pipeline Test Console API — dev 전용

가드:
  1. settings.ENABLE_PIPELINE_TEST == True (운영 배포 시 미설정 → 자동 404)
  2. X-Pipeline-Test-Token 헤더 == settings.PIPELINE_TEST_ADMIN_KEY
     (PIPELINE_TEST_ADMIN_KEY 가 비어있으면 토큰 검증 생략 — 로컬 개발 편의)

엔드포인트:
  POST /test/pipeline/seed      — 15건 시드 실행
  POST /test/pipeline/cleanup   — TEST_PIPELINE 데이터 삭제
  GET  /test/pipeline/summary   — 현황 조회
  GET  /test/pipeline/events    — StageEvent 이벤트 로그 (content_id 필터)
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from shared.database import get_db
from shared.config import settings
from api.programming.metadata.models import Content, ContentType, ContentStatus
from api.programming.metadata.models.stage_event import StageEvent

router = APIRouter(prefix="/pipeline", tags=["Pipeline Test (dev)"])


# ── Guard dependency ──────────────────────────────────────────────────────────

def require_pipeline_test(x_pipeline_test_token: str = Header(default="")):
    if not settings.ENABLE_PIPELINE_TEST:
        raise HTTPException(status_code=404, detail="Not found")
    if settings.PIPELINE_TEST_ADMIN_KEY and x_pipeline_test_token != settings.PIPELINE_TEST_ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Invalid pipeline test token")


# ── Schemas ───────────────────────────────────────────────────────────────────

class SeedResponse(BaseModel):
    movie_complete: int
    movie_incomplete: int
    series_complete: int
    series_incomplete: int
    conflict: int
    total_root: int
    skipped_in_pipeline: int = 0
    skipped_registered: int = 0


class CleanupResponse(BaseModel):
    deleted: int
    dry_run: bool


class StageCleanupRequest(BaseModel):
    ids: list[int]


class RevertRequest(BaseModel):
    ids: list[int]


class RevertResponse(BaseModel):
    reverted: int
    skipped: int
    results: dict[int, str]


class StageSummary(BaseModel):
    by_status: dict[str, int]
    by_stage: dict[str, int]   # 위치(bucket) 기준 카운트 — 카드 표시용
    by_type: dict[str, int]
    total: int
    last_seeded_at: str | None


class StageEventOut(BaseModel):
    id: int
    content_id: int
    stage: str
    event_type: str
    source: Optional[str]
    started_at: datetime
    ended_at: Optional[datetime]
    latency_ms: Optional[int]
    error_text: Optional[str]
    actor: str

    model_config = {"from_attributes": True}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/seed", response_model=SeedResponse,
             dependencies=[Depends(require_pipeline_test)])
def seed_pipeline(db: Session = Depends(get_db)):
    """TEST_PIPELINE 시드 데이터 15건 생성."""
    from scripts.seed_pipeline_test import seed_pipeline_test
    counts = seed_pipeline_test(db)
    root_total = db.query(Content).filter(
        Content.cp_name == "TEST_PIPELINE", Content.parent_id.is_(None)
    ).count()
    return SeedResponse(**counts, total_root=root_total)


@router.post("/cleanup", response_model=CleanupResponse,
             dependencies=[Depends(require_pipeline_test)])
def cleanup_pipeline(dry_run: bool = False, db: Session = Depends(get_db)):
    """TEST_PIPELINE 데이터 삭제. dry_run=true 시 건수만 반환."""
    from scripts.seed_pipeline_test import clean_pipeline_test
    deleted = clean_pipeline_test(db, dry_run=dry_run)
    return CleanupResponse(deleted=deleted, dry_run=dry_run)


@router.post("/cleanup-stage", response_model=CleanupResponse,
             dependencies=[Depends(require_pipeline_test)])
def cleanup_stage_contents(
    req: StageCleanupRequest,
    dry_run: bool = False,
    db: Session = Depends(get_db),
):
    """해당 단계 콘텐츠 삭제 — FE에서 stage-filtered IDs 전달. CP 무관.
    dry_run=true 시 건수만 반환."""
    from scripts.seed_pipeline_test import clean_by_ids
    deleted = clean_by_ids(db, req.ids, dry_run=dry_run)
    return CleanupResponse(deleted=deleted, dry_run=dry_run)


@router.post("/revert", response_model=RevertResponse,
             dependencies=[Depends(require_pipeline_test)])
def revert_stage(req: RevertRequest, db: Session = Depends(get_db)):
    """[이전단계로] — 현재 bucket에서 이전 bucket으로 되돌림. status + current_stage 역진.
    bucket 1(생성): terminal — skip.
    bucket 6(반려): S8_REVIEW + status=ai (re-review와 동일).
    컨테이너(시리즈/시즌)의 경우 같은 bucket에 있는 자손(시즌·에피)도 함께 되돌림."""
    from api.programming.metadata.stage_events import record_stage_event
    from api.programming.metadata.models.content import PipelineStage, StageEventType
    from api.test.pipeline_auto_service import expand_same_bucket_descendants

    _STAGE_BUCKET: dict[str, int] = {
        PipelineStage.S1_INTAKE.value:         1,
        PipelineStage.S2_NORMALIZE.value:      2,
        PipelineStage.S3_SOURCE_MATCH.value:   2,
        PipelineStage.S4_GAP_DETECT.value:     2,
        PipelineStage.S5_WEBSEARCH_FILL.value: 2,
        PipelineStage.S6_LLM_EXTRACT.value:    3,
        PipelineStage.S7_STAGING.value:        3,
        PipelineStage.S8_REVIEW.value:         4,
        PipelineStage.S9_PUBLISH.value:        5,
    }

    # bucket N → 이전 bucket 진입 (stage, status)
    _BUCKET_PREV: dict[int, tuple] = {
        2: (PipelineStage.S1_INTAKE,      ContentStatus.raw),       # Enrich → 생성
        3: (PipelineStage.S2_NORMALIZE,   ContentStatus.raw),       # AI → Enrich
        4: (PipelineStage.S6_LLM_EXTRACT, ContentStatus.enriched),  # 검수 → AI
        5: (PipelineStage.S8_REVIEW,      ContentStatus.ai),        # 승인 → 검수
        6: (PipelineStage.S8_REVIEW,      ContentStatus.ai),        # 반려 → 검수
    }

    expanded = expand_same_bucket_descendants(db, req.ids)
    results: dict[int, str] = {}
    reverted = 0
    for cid in expanded:
        c = db.query(Content).filter(Content.id == cid, Content.is_deleted.is_(False)).first()
        if not c:
            results[cid] = "not_found"
            continue

        # rejected 항목은 bucket 6으로 분기
        if c.status == ContentStatus.rejected:
            cur_bucket = 6
        else:
            cur_bucket = _STAGE_BUCKET.get(c.current_stage.value if c.current_stage else "", 1)

        prev = _BUCKET_PREV.get(cur_bucket)
        if prev is None:
            results[cid] = "terminal_prev"  # bucket 1은 이전단계 없음
            continue

        prev_stage, prev_status = prev
        record_stage_event(db, cid, prev_stage, StageEventType.RETRIED, actor="user")
        c.status = prev_status
        c.auto_hold = True          # 역방향 후 AUTO 자동 재진행 차단 (ADR-010)
        c.auto_claimed_at = None    # claim 마킹 해제
        results[cid] = f"bucket_{cur_bucket - 1 if cur_bucket != 6 else 4}"
        reverted += 1

    db.commit()
    return RevertResponse(reverted=reverted, skipped=len(expanded) - reverted, results=results)


@router.get("/auto-log", dependencies=[Depends(require_pipeline_test)])
def get_auto_log(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    """워커 처리건별 로그 — 최근 StageEvent를 title과 함께 최신순 반환.
    FE는 event_type+stage로 한국어 라벨을 구성해 스크롤 로그로 표시."""
    rows = (
        db.query(StageEvent, Content.title)
        .join(Content, StageEvent.content_id == Content.id)
        .filter(Content.is_deleted.is_(False))
        .order_by(StageEvent.started_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "events": [
            {
                "id": ev.id,
                "content_id": ev.content_id,
                "title": title,
                "stage": ev.stage.value if ev.stage else None,
                "event_type": ev.event_type.value if ev.event_type else None,
                "actor": ev.actor,
                "at": ev.started_at.isoformat() if ev.started_at else None,
            }
            for ev, title in rows
        ]
    }


@router.get("/auto-status", dependencies=[Depends(require_pipeline_test)])
def get_auto_status(db: Session = Depends(get_db)):
    """AUTO 워커 현황 — bucket별 pending(대기)/in-flight(처리중)/skipped(잔류) 건수.
    in-flight = auto_claimed_at 있고 visibility_timeout 미초과 건.
    pending = 미claim 또는 stuck(timeout 초과) 건 — 다음 tick 처리 대상.
    skipped = auto_review_skipped_at 있는 건 (S4 잔류).
    """
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import or_
    from api.programming.metadata.models.external import StageAutoPolicy
    from api.test.pipeline_auto_service import _STAGE_BUCKET

    policy = db.query(StageAutoPolicy).filter(StageAutoPolicy.id == 1).first()
    visibility_timeout = (policy.ai_visibility_timeout if policy else None) or 600
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=visibility_timeout)

    def bucket_stats(bucket: int) -> dict:
        stages = [s for s, b in _STAGE_BUCKET.items() if b == bucket]
        base = db.query(Content).filter(
            Content.is_deleted.is_(False),
            Content.status != ContentStatus.rejected,
        )
        if bucket == 1:
            base = base.filter(
                or_(Content.current_stage.is_(None), Content.current_stage.in_(stages))
            )
        else:
            base = base.filter(Content.current_stage.in_(stages))

        in_flight = base.filter(
            Content.auto_claimed_at.isnot(None),
            Content.auto_claimed_at >= cutoff,
        ).count()

        pending_q = base.filter(
            Content.auto_hold.is_(False),
            or_(Content.auto_claimed_at.is_(None), Content.auto_claimed_at < cutoff),
        )
        # bucket 4: 잔류 판정 건은 pending에서 제외 (claim 대상 아님)
        if bucket == 4:
            pending_q = pending_q.filter(Content.auto_review_skipped_at.is_(None))
        pending = pending_q.count()

        held = base.filter(Content.auto_hold.is_(True)).count()

        skipped = base.filter(Content.auto_review_skipped_at.isnot(None)).count() if bucket == 4 else 0

        return {"pending": pending, "in_flight": in_flight, "held": held, "skipped": skipped}

    buckets = {str(b): bucket_stats(b) for b in (1, 2, 3, 4)}

    return {
        "tick_enabled": policy.auto_tick_enabled if policy else True,
        "s1_auto": policy.s1_auto if policy else False,
        "s2_auto": policy.s2_auto if policy else False,
        "s3_auto": policy.s3_auto if policy else False,
        "s4_auto": policy.s4_auto if policy else False,
        "buckets": buckets,
    }


@router.get("/summary", response_model=StageSummary,
            dependencies=[Depends(require_pipeline_test)])
def pipeline_summary(db: Session = Depends(get_db)):
    """파이프라인 단계별 현황.
    - by_stage: **CP 무관** 전체 콘텐츠의 위치(stage) 카운트 — 카드 표시용.
      시드/BULK/개별 등 어떤 경로로 들어왔든 현재 stage에 있으면 모두 집계.
    - by_status/by_type/total/last_seeded_at: 시드 패널 관리용으로 TEST_PIPELINE 한정.
    """
    from api.programming.metadata.models.content import PipelineStage

    # current_stage → 콘솔 카드 번호(bucket)
    _STAGE_BUCKET: dict[str, int] = {
        PipelineStage.S1_INTAKE.value:         1,
        PipelineStage.S2_NORMALIZE.value:      2,
        PipelineStage.S3_SOURCE_MATCH.value:   2,
        PipelineStage.S4_GAP_DETECT.value:     2,
        PipelineStage.S5_WEBSEARCH_FILL.value: 2,
        PipelineStage.S6_LLM_EXTRACT.value:    3,
        PipelineStage.S7_STAGING.value:        3,
        PipelineStage.S8_REVIEW.value:         4,
        PipelineStage.S9_PUBLISH.value:        5,
    }

    # ── 카드 카운트(by_stage): CP 무관 전체 (소프트 삭제 제외) ──
    # rejected 항목은 위치(current_stage)와 무관하게 bucket 6(반려/실패)으로 분기.
    by_stage: dict[str, int] = {}
    stage_rows = (
        db.query(Content.current_stage, Content.status, func.count())
        .filter(Content.is_deleted.is_(False))
        .group_by(Content.current_stage, Content.status)
        .all()
    )
    for cur_stage, status, cnt in stage_rows:
        if status == ContentStatus.rejected:
            bucket = 6
        else:
            # current_stage 없으면(시드 직후/레거시) → bucket 1
            bucket = _STAGE_BUCKET.get(cur_stage.value if cur_stage else "", 1)
        by_stage[str(bucket)] = by_stage.get(str(bucket), 0) + cnt

    # ── 시드 패널용(by_status/by_type/total): TEST_PIPELINE 한정 ──
    rows = db.query(Content).filter(
        Content.cp_name == "TEST_PIPELINE", Content.is_deleted.is_(False)
    ).all()

    by_status: dict[str, int] = {}
    by_type: dict[str, int] = {}
    last_created = None

    for r in rows:
        key_s = r.status.value if r.status else "unknown"
        key_t = r.content_type.value if r.content_type else "unknown"
        by_status[key_s] = by_status.get(key_s, 0) + 1
        by_type[key_t] = by_type.get(key_t, 0) + 1
        if r.created_at and (last_created is None or r.created_at > last_created):
            last_created = r.created_at

    return StageSummary(
        by_status=by_status,
        by_stage=by_stage,
        by_type=by_type,
        total=len(rows),
        last_seeded_at=last_created.isoformat() if last_created else None,
    )


@router.get("/events", response_model=list[StageEventOut],
            dependencies=[Depends(require_pipeline_test)])
def get_pipeline_events(
    content_id: Optional[int] = Query(None),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """StageEvent 이벤트 로그. content_id 지정 시 해당 콘텐츠만 반환 (최신순)."""
    q = db.query(StageEvent)
    if content_id is not None:
        q = q.filter(StageEvent.content_id == content_id)
    else:
        # content_id 없으면 TEST_PIPELINE 콘텐츠만 (소프트 삭제 제외)
        test_ids = [
            r.id for r in db.query(Content.id).filter(
                Content.cp_name == "TEST_PIPELINE", Content.is_deleted.is_(False)
            ).all()
        ]
        if test_ids:
            q = q.filter(StageEvent.content_id.in_(test_ids))
    events = q.order_by(StageEvent.started_at.desc()).limit(limit).all()
    return events


# ── ADR-009: 내부처리/다음단계 분리 엔드포인트 ───────────────────────────────

_ADVANCE_NEXT = {
    ContentStatus.raw:      ContentStatus.enriched,
    ContentStatus.enriched: ContentStatus.ai,
    ContentStatus.ai:       ContentStatus.review,
    ContentStatus.review:   ContentStatus.approved,
}

_STATUS_STAGE_MAP = {
    ContentStatus.enriched: "s2_normalize",
    ContentStatus.ai:       "s6_llm_extract",
    ContentStatus.review:   "s8_review",
    ContentStatus.approved: "s9_publish",
}


class AdvanceRequest(BaseModel):
    ids: list[int]


class AdvanceResponse(BaseModel):
    advanced: int
    skipped: int
    results: dict[int, str]


class ReviewActionRequest(BaseModel):
    ids: list[int]


class ReviewActionResponse(BaseModel):
    processed: int
    skipped: int
    results: dict[int, str]


class EnrichSourceRequest(BaseModel):
    content_id: int
    source: str


class EnrichSourceResponse(BaseModel):
    content_id: int
    source: str
    candidates_upserted: int
    suggestions_created: int
    sources_hit: list[str]
    sources_skipped: list[str]
    status_unchanged: str


class AiTaskRequest(BaseModel):
    content_id: int
    task_name: str


class AiTaskResponse(BaseModel):
    content_id: int
    task_name: str
    status: str
    engine: Optional[str]
    result_preview: Optional[str]
    status_unchanged: str


@router.post("/advance", response_model=AdvanceResponse,
             dependencies=[Depends(require_pipeline_test)])
def advance_stage(req: AdvanceRequest, db: Session = Depends(get_db)):
    """[다음단계로] — 현재 단계를 완료하고 다음 bucket 진입 stage로 이동.
    컨테이너(시리즈/시즌)의 경우 같은 bucket에 있는 자손(시즌·에피)도 함께 이동."""
    from api.test.pipeline_auto_service import advance_one, expand_same_bucket_descendants

    expanded = expand_same_bucket_descendants(db, req.ids)
    results: dict[int, str] = {}
    advanced = 0
    for cid in expanded:
        r = advance_one(db, cid, actor="user")
        results[cid] = r["result"]
        if r["result"] == "ok":
            advanced += 1

    db.commit()
    return AdvanceResponse(advanced=advanced, skipped=len(expanded) - advanced, results=results)


@router.post("/approve", response_model=ReviewActionResponse,
             dependencies=[Depends(require_pipeline_test)])
def approve_review(req: ReviewActionRequest, db: Session = Depends(get_db)):
    """[승인] — 검수 통과. status=approved 확정. 멱등(이미 approved면 no-op)."""
    from api.test.pipeline_auto_service import approve_one

    results: dict[int, str] = {}
    processed = 0
    for cid in req.ids:
        r = approve_one(db, cid, actor="user")
        results[cid] = r["result"]
        if r["result"] == "ok":
            processed += 1

    db.commit()
    return ReviewActionResponse(processed=processed, skipped=len(req.ids) - processed, results=results)


@router.post("/reject", response_model=ReviewActionResponse,
             dependencies=[Depends(require_pipeline_test)])
def reject_review(req: ReviewActionRequest, db: Session = Depends(get_db)):
    """[반려] — status=rejected(bucket 6). 수동 반려는 auto_hold 설정(재검수 복귀 시 AUTO 차단).
    반려된 콘텐츠는 [재검수]로 복귀 가능."""
    from api.test.pipeline_auto_service import reject_one

    results: dict[int, str] = {}
    processed = 0
    for cid in req.ids:
        r = reject_one(db, cid, actor="user", set_hold=True)
        results[cid] = "rejected" if r["result"] == "ok" else r["result"]
        if r["result"] == "ok":
            processed += 1

    db.commit()
    return ReviewActionResponse(processed=processed, skipped=len(req.ids) - processed, results=results)


@router.post("/re-review", response_model=ReviewActionResponse,
             dependencies=[Depends(require_pipeline_test)])
def re_review(req: ReviewActionRequest, db: Session = Depends(get_db)):
    """[재검수] — 반려 콘텐츠를 검수 가능 상태(status=ai)로 복귀, 위치=검수. StageEvent RETRIED 기록."""
    from api.programming.metadata.stage_events import record_stage_event
    from api.programming.metadata.models.content import PipelineStage, StageEventType

    results: dict[int, str] = {}
    processed = 0
    for cid in req.ids:
        c = db.query(Content).filter(Content.id == cid, Content.is_deleted.is_(False)).first()
        if not c:
            results[cid] = "not_found"
            continue
        record_stage_event(db, cid, PipelineStage.S8_REVIEW, StageEventType.RETRIED, actor="user")
        c.status = ContentStatus.ai
        c.auto_hold = True          # 재검수 복귀 후 AUTO 자동 재진행 차단 (ADR-010)
        c.auto_claimed_at = None
        results[cid] = "re_reviewed"
        processed += 1

    db.commit()
    return ReviewActionResponse(processed=processed, skipped=len(req.ids) - processed, results=results)


# ── AUTO hold 해제 (ADR-010) ──────────────────────────────────────────────────

class ResumeAutoRequest(BaseModel):
    ids: list[int]


class ResumeAutoResponse(BaseModel):
    resumed: int
    results: dict[int, str]


@router.post("/resume-auto", response_model=ResumeAutoResponse,
             dependencies=[Depends(require_pipeline_test)])
def resume_auto(req: ResumeAutoRequest, db: Session = Depends(get_db)):
    """auto_hold 해제 — 다음 tick부터 자동 진행 재개."""
    results: dict[int, str] = {}
    resumed = 0
    for cid in req.ids:
        c = db.query(Content).filter(Content.id == cid, Content.is_deleted.is_(False)).first()
        if not c:
            results[cid] = "not_found"
            continue
        c.auto_hold = False
        c.auto_claimed_at = None
        results[cid] = "resumed"
        resumed += 1
    db.commit()
    return ResumeAutoResponse(resumed=resumed, results=results)


@router.post("/enrich-source", response_model=EnrichSourceResponse,
             dependencies=[Depends(require_pipeline_test)])
def enrich_single_source(req: EnrichSourceRequest, db: Session = Depends(get_db)):
    """보완 내부처리 sub-step — TMDB/KMDB 단일 소스 회수. status 불변."""
    from api.meta_core.enrich import enrich_content

    source = req.source.lower().strip()
    if source not in ("tmdb", "kmdb"):
        raise HTTPException(status_code=422, detail="source must be 'tmdb' or 'kmdb'")

    c = db.query(Content).filter(Content.id == req.content_id, Content.is_deleted.is_(False)).first()
    if not c:
        raise HTTPException(status_code=404, detail="content not found")

    before_status = c.status.value if c.status else ""
    result = enrich_content(req.content_id, db, only_sources={source})
    db.commit()
    db.refresh(c)
    return EnrichSourceResponse(
        content_id=req.content_id,
        source=source,
        candidates_upserted=result.candidates_upserted,
        suggestions_created=result.suggestions_created,
        sources_hit=result.sources_hit,
        sources_skipped=result.sources_skipped,
        status_unchanged=c.status.value if c.status else before_status,
    )


@router.post("/run-ai-task", response_model=AiTaskResponse,
             dependencies=[Depends(require_pipeline_test)])
async def run_single_ai_task_endpoint(req: AiTaskRequest, db: Session = Depends(get_db)):
    """AI 내부처리 sub-step — registry 단일 태스크 실행. status 불변."""
    from api.programming.metadata.ai_tasks import AI_TASK_REGISTRY
    from api.programming.metadata.ai_tasks.runner import run_single_ai_task

    valid = list(AI_TASK_REGISTRY.keys())
    if req.task_name not in valid:
        raise HTTPException(status_code=422, detail=f"unknown task_name. valid: {valid}")

    c = db.query(Content).filter(Content.id == req.content_id, Content.is_deleted.is_(False)).first()
    if not c:
        raise HTTPException(status_code=404, detail="content not found")

    result = await run_single_ai_task(req.content_id, req.task_name, db)
    db.refresh(c)
    return AiTaskResponse(
        content_id=req.content_id,
        task_name=result["task_name"],
        status=result["status"],
        engine=result["engine"],
        result_preview=result["result_preview"],
        status_unchanged=c.status.value if c.status else "",
    )


class EnrichAutofillRequest(BaseModel):
    content_id: int


class EnrichAutofillResponse(BaseModel):
    content_id: int
    enriched_sources: list[str]   # enrich_content가 hit한 소스
    filled_fields: list[str]      # 비어있어 채운 필드
    skipped_fields: list[str]     # 추천값 있으나 이미 값 있어 건너뛴 필드
    status_unchanged: str


@router.post("/enrich-autofill", response_model=EnrichAutofillResponse,
             dependencies=[Depends(require_pipeline_test)])
def enrich_autofill(req: EnrichAutofillRequest, db: Session = Depends(get_db)):
    """S2 AUTO — enrich(tmdb+kmdb) 후 **빈 필드에만** auto_fill 추천값 적용. status 불변."""
    from api.test.pipeline_auto_service import enrich_autofill_one

    c = db.query(Content).filter(Content.id == req.content_id, Content.is_deleted.is_(False)).first()
    if not c:
        raise HTTPException(status_code=404, detail="content not found")

    r = enrich_autofill_one(db, req.content_id)
    return EnrichAutofillResponse(**r)


class AiAutofillRequest(BaseModel):
    content_id: int


class AiAutofillResponse(BaseModel):
    content_id: int
    rag_sources: list[str]       # reference_extract sources_hit (wikidata/wikipedia)
    ai_tasks: dict[str, str]     # {task_name: ok|cached|skip|error}
    filled_fields: list[str]     # 비어있어 채운 필드
    skipped_fields: list[str]    # 추천/팩트 있으나 이미 값 있어 건너뛴 필드
    status_unchanged: str


@router.post("/ai-autofill", response_model=AiAutofillResponse,
             dependencies=[Depends(require_pipeline_test)])
def ai_autofill(req: AiAutofillRequest, db: Session = Depends(get_db)):
    """S3 AUTO — RAG+AI태스크 후 **빈 필드에만** 보완값 적용. status 불변."""
    from api.test.pipeline_auto_service import ai_autofill_one

    c = db.query(Content).filter(Content.id == req.content_id, Content.is_deleted.is_(False)).first()
    if not c:
        raise HTTPException(status_code=404, detail="content not found")

    r = ai_autofill_one(db, req.content_id)
    return AiAutofillResponse(**r)



@router.get("/ai-tasks", dependencies=[Depends(require_pipeline_test)])
def list_ai_tasks():
    """사용 가능한 AI task 목록."""
    from api.programming.metadata.ai_tasks import AI_TASK_REGISTRY
    return {"tasks": list(AI_TASK_REGISTRY.keys())}


# ── RAG Reference Extract ─────────────────────────────────────────────────────

class ReferenceExtractRequest(BaseModel):
    content_id: int


class ReferenceExtractResponse(BaseModel):
    content_id: int
    title_used: str
    year_used: Optional[int]
    wikidata_facts: dict
    wikidata_url: Optional[str]
    wikipedia_text: Optional[str]
    wikipedia_url: Optional[str]
    wikipedia_lang: Optional[str]
    sources_hit: list[str]
    sources_skipped: list[str]


@router.post("/reference-extract", response_model=ReferenceExtractResponse,
             dependencies=[Depends(require_pipeline_test)])
def reference_extract_endpoint(req: ReferenceExtractRequest, db: Session = Depends(get_db)):
    """Wikidata + Wikipedia RAG 조회 — 빈 필드 보강 후보 수집. status 불변.

    wikidata_facts: 구조화 fact (directors/cast/country/genres/runtime/production_year)
    wikipedia_text: intro 텍스트 (CC BY-SA — FE에서 LLM 요약 후 사용, 직접 저장 금지)
    """
    from api.meta_core.reference_extract import reference_extract

    c = db.query(Content).filter(Content.id == req.content_id, Content.is_deleted.is_(False)).first()
    if not c:
        raise HTTPException(status_code=404, detail="content not found")

    result = reference_extract(req.content_id, db)
    return ReferenceExtractResponse(
        content_id=result.content_id,
        title_used=result.title_used,
        year_used=result.year_used,
        wikidata_facts=result.wikidata_facts,
        wikidata_url=result.wikidata_url,
        wikipedia_text=result.wikipedia_text,
        wikipedia_url=result.wikipedia_url,
        wikipedia_lang=result.wikipedia_lang,
        sources_hit=result.sources_hit,
        sources_skipped=result.sources_skipped,
    )
