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


class CleanupResponse(BaseModel):
    deleted: int
    dry_run: bool


class StageSummary(BaseModel):
    by_status: dict[str, int]
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


@router.get("/summary", response_model=StageSummary,
            dependencies=[Depends(require_pipeline_test)])
def pipeline_summary(db: Session = Depends(get_db)):
    """TEST_PIPELINE 콘텐츠의 단계별 현황."""
    rows = db.query(Content).filter(Content.cp_name == "TEST_PIPELINE").all()

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
        # content_id 없으면 TEST_PIPELINE 콘텐츠만
        test_ids = [
            r.id for r in db.query(Content.id).filter(Content.cp_name == "TEST_PIPELINE").all()
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
    """[다음단계로] — 내부처리 없이 status 1칸 진행 + StageEvent(ADVANCED) 기록."""
    from api.programming.metadata.models.content import StageEventType
    from api.programming.metadata.models.stage_event import StageEvent as SE
    from api.programming.metadata.stage_events import record_stage_event
    from api.programming.metadata.models.content import PipelineStage

    _STATUS_STAGE = {
        ContentStatus.enriched: PipelineStage.S2_NORMALIZE,
        ContentStatus.ai:       PipelineStage.S6_LLM_EXTRACT,
        ContentStatus.review:   PipelineStage.S8_REVIEW,
        ContentStatus.approved: PipelineStage.S9_PUBLISH,
    }

    results: dict[int, str] = {}
    advanced = 0
    for cid in req.ids:
        c = db.query(Content).filter(Content.id == cid, Content.is_deleted.is_(False)).first()
        if not c:
            results[cid] = "not_found"
            continue
        nxt = _ADVANCE_NEXT.get(c.status)
        if nxt is None:
            results[cid] = "terminal"
            continue
        record_stage_event(db, cid, _STATUS_STAGE[nxt], StageEventType.ADVANCED, actor="user")
        results[cid] = nxt.value
        advanced += 1

    db.commit()
    return AdvanceResponse(advanced=advanced, skipped=len(req.ids) - advanced, results=results)


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


@router.get("/ai-tasks", dependencies=[Depends(require_pipeline_test)])
def list_ai_tasks():
    """사용 가능한 AI task 목록."""
    from api.programming.metadata.ai_tasks import AI_TASK_REGISTRY
    return {"tasks": list(AI_TASK_REGISTRY.keys())}
