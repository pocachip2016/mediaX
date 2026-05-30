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
