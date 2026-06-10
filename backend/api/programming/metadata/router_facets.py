"""MediSearch facet 배치 진행률/트리거 API.

엔드포인트 prefix: /api/programming/metadata/facets

  POST /batch          — 배치 수동 트리거 (실행 중 409, 아니면 202)
  GET  /batch          — 최근 run 20건
  GET  /batch/{run_id} — 단건 상세 (카운트, error_log, ETA)
  GET  /coverage       — 전체 커버리지 통계
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from shared.database import get_db
from shared.config import settings

router = APIRouter()

_ETA_SECONDS_PER_ITEM = 120  # 콘텐츠 1건당 예상 소요 시간


# ── 스키마 ────────────────────────────────────────────────────────────────────

class BatchTriggerRequest(BaseModel):
    limit: Optional[int] = None
    content_ids: Optional[list[int]] = None
    force: bool = False


class FacetBatchRunOut(BaseModel):
    id: int
    status: str
    trigger: str
    total_count: int
    success_count: int
    failed_count: int
    skipped_count: int
    error_log: Optional[list] = None
    params: Optional[dict] = None
    created_at: datetime
    finished_at: Optional[datetime] = None
    eta_seconds: Optional[int] = None

    class Config:
        from_attributes = True


class CoverageOut(BaseModel):
    movies_total: int
    with_final_facet: int
    stale: int
    pending: int


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def _run_to_out(run) -> FacetBatchRunOut:
    remaining = max(run.total_count - run.success_count - run.failed_count, 0)
    eta = remaining * _ETA_SECONDS_PER_ITEM if run.status == "running" else None
    return FacetBatchRunOut(
        id=run.id,
        status=run.status,
        trigger=run.trigger,
        total_count=run.total_count,
        success_count=run.success_count,
        failed_count=run.failed_count,
        skipped_count=run.skipped_count,
        error_log=run.error_log,
        params=run.params,
        created_at=run.created_at,
        finished_at=run.finished_at,
        eta_seconds=eta,
    )


# ── 엔드포인트 ────────────────────────────────────────────────────────────────

@router.post("/batch", status_code=202)
def trigger_batch(req: BatchTriggerRequest, db: Session = Depends(get_db)):
    """배치 수동 트리거. 실행 중인 run 있으면 409."""
    from api.programming.metadata.models.external import FacetBatchRun
    from workers.tasks.facet_tasks import dispatch_facet_batch

    running = (
        db.query(FacetBatchRun)
        .filter(FacetBatchRun.status == "running")
        .first()
    )
    if running:
        raise HTTPException(
            status_code=409,
            detail=f"run {running.id} already in progress (started {running.created_at})",
        )

    dispatch_facet_batch.delay(
        limit=req.limit,
        content_ids=req.content_ids,
        force=req.force,
        trigger="manual",
    )
    return {"queued": True}


@router.get("/batch", response_model=list[FacetBatchRunOut])
def list_batch_runs(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """최근 run 목록 (최신순)."""
    from api.programming.metadata.models.external import FacetBatchRun

    runs = (
        db.query(FacetBatchRun)
        .order_by(FacetBatchRun.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_run_to_out(r) for r in runs]


@router.get("/batch/{run_id}", response_model=FacetBatchRunOut)
def get_batch_run(run_id: int, db: Session = Depends(get_db)):
    """단건 run 상세."""
    from api.programming.metadata.models.external import FacetBatchRun

    run = db.query(FacetBatchRun).filter(FacetBatchRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return _run_to_out(run)


@router.get("/coverage", response_model=CoverageOut)
def get_coverage(db: Session = Depends(get_db)):
    """영화 콘텐츠 facet 커버리지 통계."""
    from sqlalchemy import exists, func
    from api.programming.metadata.models import (
        ContentAIResult, AITaskType, ExternalMetaSource, ExternalSourceType,
    )
    from api.programming.metadata.models.content import Content, ContentType

    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.FACET_STALENESS_DAYS)

    # 전체 영화 수
    movies_total = (
        db.query(func.count(Content.id))
        .filter(Content.content_type == ContentType.movie)
        .scalar()
    )

    # final facet 보유 수
    with_final_facet = (
        db.query(func.count(func.distinct(ContentAIResult.content_id)))
        .filter(
            ContentAIResult.task_type == AITaskType.facet_analysis,
            ContentAIResult.is_final.is_(True),
        )
        .scalar()
    )

    # stale: final facet이 staleness 기준 초과
    stale = (
        db.query(func.count(func.distinct(ContentAIResult.content_id)))
        .filter(
            ContentAIResult.task_type == AITaskType.facet_analysis,
            ContentAIResult.is_final.is_(True),
            ContentAIResult.processed_at < cutoff,
        )
        .scalar()
    )

    # pending: 외부소스 있는 영화 중 final facet 없는 수
    has_external = exists().where(
        ExternalMetaSource.content_id == Content.id,
        ExternalMetaSource.source_type.in_([
            ExternalSourceType.tmdb,
            ExternalSourceType.kmdb,
            ExternalSourceType.kobis,
        ]),
    )
    has_final_facet = exists().where(
        ContentAIResult.content_id == Content.id,
        ContentAIResult.task_type == AITaskType.facet_analysis,
        ContentAIResult.is_final.is_(True),
    )
    pending = (
        db.query(func.count(Content.id))
        .filter(
            Content.content_type == ContentType.movie,
            has_external,
            ~has_final_facet,
        )
        .scalar()
    )

    return CoverageOut(
        movies_total=movies_total,
        with_final_facet=with_final_facet,
        stale=stale,
        pending=pending,
    )
