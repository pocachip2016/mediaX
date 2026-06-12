"""MediSearch facet 배치 진행률/트리거 API.

엔드포인트 prefix: /api/programming/metadata/facets

  POST  /batch          — 배치 수동 트리거 (실행 중 409, 아니면 202)
  GET   /batch          — 최근 run 20건
  GET   /batch/{run_id} — 단건 상세 (카운트, error_log, ETA)
  GET   /coverage       — 전체 커버리지 통계
  GET   /results        — facet 평가 결과 목록 (status/search/페이지네이션)
  GET   /events         — since-id 커서 실시간 이벤트 폴링
  GET   /policy         — 로깅 정책 조회
  PATCH /policy         — 로깅 정책 변경
  GET   /daily          — 날짜별 배치 통계
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
    tmdb_ids: Optional[list[int]] = None
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
    movies_total: int   # tmdb_movie_cache 모집단 (개봉작 + vote_count 필터)
    with_final_facet: int  # status=success 수
    stale: int          # success 중 staleness 초과
    pending: int        # movies_total - success - skipped
    skipped: int = 0    # 나무위키 부재 등 영구 제외


class FacetResultOut(BaseModel):
    tmdb_id: int
    title: str
    original_title: Optional[str] = None
    status: str  # success | skipped | failed
    confidence: Optional[float] = None
    source_count: Optional[int] = None
    attempt_count: int
    evaluated_at: Optional[datetime] = None
    last_error: Optional[str] = None
    facet_json: Optional[dict] = None  # 전체 facet 분석 필드

    class Config:
        from_attributes = True


class FacetResultsPage(BaseModel):
    items: list[FacetResultOut]
    total: int
    page: int
    size: int


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

    # 동기 호출 (celery broker 우회)
    result = dispatch_facet_batch(
        limit=req.limit,
        tmdb_ids=req.tmdb_ids,
        force=req.force,
        trigger="manual",
    )
    return {"queued": True, "run_id": result.get("run_id")}


@router.post("/batch/stop")
def stop_batch(db: Session = Depends(get_db)):
    """실행 중인 배치 중지 — running run을 cancelled로 마킹.

    잔여 enqueue된 evaluate 태스크는 진입 guard에서 no-op 처리되어 빠르게 소진되고,
    연속 디스패치 체인이 끊긴다. (평가 진행 중인 1건만 자연 완료.)
    """
    from api.programming.metadata.models.external import FacetBatchRun
    from workers.tasks.facet_tasks import _emit_event

    running = (
        db.query(FacetBatchRun)
        .filter(FacetBatchRun.status == "running")
        .first()
    )
    if not running:
        raise HTTPException(status_code=404, detail="no running batch")

    running.status = "cancelled"
    running.finished_at = datetime.now(timezone.utc)
    db.commit()

    _emit_event(running.id, None, "batch_cancelled", "운영자 중지")
    return {"stopped": True, "run_id": running.id}


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
    """TMDB 캐시 모집단(개봉작 + vote_count 필터) 기준 facet 커버리지 통계."""
    from datetime import date
    from sqlalchemy import func, or_
    from api.programming.metadata.models.tmdb_cache import TmdbMovieCache, TmdbMovieFacet

    today = date.today()
    freshness_cutoff = datetime.now(timezone.utc) - timedelta(days=settings.FACET_STALENESS_DAYS)

    # 모집단: 개봉작 중 한국영화(vote 무관) OR 해외영화(vote>=N)
    population_filter = or_(
        TmdbMovieCache.original_language == "ko",
        TmdbMovieCache.vote_count >= settings.FACET_MIN_VOTE_COUNT,
    )
    movies_total = (
        db.query(func.count(TmdbMovieCache.id))
        .filter(
            TmdbMovieCache.release_date.isnot(None),
            TmdbMovieCache.release_date <= today,
            population_filter,
        )
        .scalar()
    ) or 0

    # status별 집계
    counts = dict(
        db.query(TmdbMovieFacet.status, func.count(TmdbMovieFacet.tmdb_id))
        .group_by(TmdbMovieFacet.status)
        .all()
    )
    success_total = counts.get("success", 0)
    skipped_total = counts.get("skipped", 0)

    # stale: success 중 staleness 기준 초과
    stale = (
        db.query(func.count(TmdbMovieFacet.tmdb_id))
        .filter(
            TmdbMovieFacet.status == "success",
            TmdbMovieFacet.evaluated_at < freshness_cutoff,
        )
        .scalar()
    ) or 0

    pending = max(movies_total - success_total - skipped_total, 0)

    return CoverageOut(
        movies_total=movies_total,
        with_final_facet=success_total,
        stale=stale,
        pending=pending,
        skipped=skipped_total,
    )


# ── 이벤트 스트림 (since-id 커서) ─────────────────────────────────────────────

class FacetEventOut(BaseModel):
    id: int
    run_id: int
    content_id: Optional[int] = None
    content_title: Optional[str] = None
    event_type: str
    message: Optional[str] = None
    detail: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class FacetEventsPage(BaseModel):
    items: list[FacetEventOut]
    next_cursor: int
    total: int


@router.get("/results", response_model=FacetResultsPage)
def get_facet_results(
    status: str = Query("success", regex="^(success|skipped|failed)$"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """facet 평가 결과 목록. status/search/페이지네이션 지원."""
    from api.programming.metadata.models.tmdb_cache import TmdbMovieCache, TmdbMovieFacet

    q = (
        db.query(
            TmdbMovieFacet.tmdb_id,
            TmdbMovieCache.title,
            TmdbMovieCache.original_title,
            TmdbMovieFacet.status,
            TmdbMovieFacet.confidence,
            TmdbMovieFacet.source_count,
            TmdbMovieFacet.attempt_count,
            TmdbMovieFacet.evaluated_at,
            TmdbMovieFacet.last_error,
            TmdbMovieFacet.facet_json,
        )
        .join(TmdbMovieCache, TmdbMovieCache.id == TmdbMovieFacet.tmdb_id)
        .filter(TmdbMovieFacet.status == status)
    )

    if search:
        q = q.filter(TmdbMovieCache.title.ilike(f"%{search}%"))

    total = q.count()
    offset = (page - 1) * size

    rows = q.order_by(TmdbMovieFacet.evaluated_at.desc()).offset(offset).limit(size).all()

    items = []
    for row in rows:
        items.append(
            FacetResultOut(
                tmdb_id=row.tmdb_id,
                title=row.title,
                original_title=row.original_title,
                status=row.status,
                confidence=row.confidence,
                source_count=row.source_count,
                attempt_count=row.attempt_count,
                evaluated_at=row.evaluated_at,
                last_error=row.last_error,
                facet_json=row.facet_json or None,
            )
        )

    return FacetResultsPage(items=items, total=total, page=page, size=size)


@router.get("/events", response_model=FacetEventsPage)
def list_events(
    since: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    run_id: Optional[int] = Query(None),
    tail: bool = Query(False, description="True면 최신 limit건부터 (라이브 로그 초기 로드용)"),
    db: Session = Depends(get_db),
):
    """since-id 커서 폴링 — 실시간 로그 FE 폴링용.

    tail=True: 최신 limit건을 시간순(asc)으로 반환 — 라이브 로그 초기 로드용.
               next_cursor=최대 id 이므로 이후 폴링은 새 이벤트만 받음(idle 시 정지).
    tail=False: since-id 이후 오래된 순 페이징.
    """
    from api.programming.metadata.models.external import FacetEvent
    from api.programming.metadata.models.tmdb_cache import TmdbMovieCache

    base = db.query(FacetEvent)
    if run_id is not None:
        base = base.filter(FacetEvent.run_id == run_id)

    if tail:
        # 최신 limit건을 desc로 뽑은 뒤 asc로 뒤집어 반환
        items = base.order_by(FacetEvent.id.desc()).limit(limit).all()
        items.reverse()
    else:
        items = base.filter(FacetEvent.id > since).order_by(FacetEvent.id.asc()).limit(limit).all()

    next_cursor = items[-1].id if items else since
    total = base.count()

    # content_id(=tmdb_id) → title 일괄 조회 (N+1 방지)
    cids = {e.content_id for e in items if e.content_id is not None}
    title_map: dict[int, str] = {}
    if cids:
        rows = db.query(TmdbMovieCache.id, TmdbMovieCache.title).filter(TmdbMovieCache.id.in_(cids)).all()
        title_map = {cid: title for cid, title in rows}

    out = []
    for e in items:
        dto = FacetEventOut.model_validate(e)
        if e.content_id is not None:
            dto.content_title = title_map.get(e.content_id)
        out.append(dto)

    return FacetEventsPage(items=out, next_cursor=next_cursor, total=total)


# ── 정책 조회/변경 ──────────────────────────────────────────────────────────

class FacetPolicyOut(BaseModel):
    id: int
    log_enabled: bool
    updated_at: datetime

    class Config:
        from_attributes = True


class FacetPolicyPatch(BaseModel):
    log_enabled: bool


def _get_or_create_policy(db: Session):
    from api.programming.metadata.models.external import FacetPolicy
    policy = db.query(FacetPolicy).filter(FacetPolicy.id == 1).first()
    if not policy:
        policy = FacetPolicy(id=1, log_enabled=False)
        db.add(policy)
        db.commit()
        db.refresh(policy)
    return policy


@router.get("/policy", response_model=FacetPolicyOut)
def get_policy(db: Session = Depends(get_db)):
    """로깅 정책 조회."""
    return _get_or_create_policy(db)


@router.patch("/policy", response_model=FacetPolicyOut)
def update_policy(req: FacetPolicyPatch, db: Session = Depends(get_db)):
    """로깅 정책 변경."""
    policy = _get_or_create_policy(db)
    policy.log_enabled = req.log_enabled
    policy.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(policy)
    return policy


# ── 일별 배치 통계 ──────────────────────────────────────────────────────────

class FacetDailyPoint(BaseModel):
    date: str
    runs: int
    total: int
    success: int
    failed: int


@router.get("/daily", response_model=list[FacetDailyPoint])
def get_daily_stats(
    days: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db),
):
    """최근 N일 날짜별 배치 실행 통계."""
    from sqlalchemy import func
    from api.programming.metadata.models.external import FacetBatchRun

    since = datetime.now(timezone.utc) - timedelta(days=days)
    date_col = func.date(FacetBatchRun.created_at)

    rows = (
        db.query(
            date_col.label("date"),
            func.count(FacetBatchRun.id).label("runs"),
            func.coalesce(func.sum(FacetBatchRun.total_count), 0).label("total"),
            func.coalesce(func.sum(FacetBatchRun.success_count), 0).label("success"),
            func.coalesce(func.sum(FacetBatchRun.failed_count), 0).label("failed"),
        )
        .filter(FacetBatchRun.created_at >= since)
        .group_by(date_col)
        .order_by(date_col.asc())
        .all()
    )

    return [
        FacetDailyPoint(
            date=str(r.date),
            runs=r.runs,
            total=r.total,
            success=r.success,
            failed=r.failed,
        )
        for r in rows
    ]
