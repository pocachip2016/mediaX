"""
1.1 메타데이터 API 라우터

엔드포인트:
  GET    /dashboard              - 오늘 통계
  GET    /contents               - 콘텐츠 목록 (페이징·필터)
  POST   /contents               - 콘텐츠 수동 등록
  GET    /contents/{id}          - 콘텐츠 상세
  POST   /contents/{id}/process  - AI 처리 트리거
  GET    /queue                  - 검수 큐 (70~89점)
  POST   /queue/{id}/action      - 검수 액션 (승인/수정/반려)
  POST   /generate               - 실시간 메타 AI 생성 (화면 3)
  GET    /emails                 - CP 이메일 수신 이력
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from shared.database import get_db
from api.programming.metadata import service
from api.programming.metadata.models import ContentStatus
from api.programming.metadata.schemas import (
    ContentCreate, ContentOut, ContentDetail, PaginatedContents,
    MetadataReviewAction, AIGenerateRequest, AIGenerateResponse,
    DashboardStats, CpEmailLogOut,
)
from api.programming.metadata.models import CpEmailLog

router = APIRouter()


@router.get("/dashboard", response_model=DashboardStats)
def get_dashboard(db: Session = Depends(get_db)):
    return service.get_dashboard_stats(db)


@router.get("/contents", response_model=PaginatedContents)
def list_contents(
    status: ContentStatus | None = Query(None),
    cp_name: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    items, total = service.list_contents(db, status=status, cp_name=cp_name, page=page, size=size)
    # quality_score를 ContentOut에 주입
    result = []
    for c in items:
        out = ContentOut.model_validate(c)
        if c.metadata_record:
            out.quality_score = c.metadata_record.quality_score
        result.append(out)
    return PaginatedContents(items=result, total=total, page=page, size=size)


@router.post("/contents", response_model=ContentOut, status_code=201)
def create_content(data: ContentCreate, db: Session = Depends(get_db)):
    content = service.create_content(db, data)
    return ContentOut.model_validate(content)


@router.get("/contents/{content_id}", response_model=ContentDetail)
def get_content(content_id: int, db: Session = Depends(get_db)):
    content = service.get_content(db, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    return ContentDetail.model_validate(content)


@router.post("/contents/{content_id}/process")
def trigger_processing(content_id: int, db: Session = Depends(get_db)):
    content = service.get_content(db, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    task_id = service.trigger_ai_processing(content_id)
    return {"task_id": task_id, "message": "AI 처리 큐에 등록되었습니다"}


@router.get("/queue", response_model=PaginatedContents)
def get_review_queue(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    items, total = service.get_review_queue(db, page=page, size=size)
    result = []
    for c in items:
        out = ContentOut.model_validate(c)
        if c.metadata_record:
            out.quality_score = c.metadata_record.quality_score
        result.append(out)
    return PaginatedContents(items=result, total=total, page=page, size=size)


@router.post("/queue/{content_id}/action", response_model=ContentOut)
def review_action(
    content_id: int,
    action: MetadataReviewAction,
    db: Session = Depends(get_db),
):
    try:
        content = service.apply_review_action(db, content_id, action)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return ContentOut.model_validate(content)


@router.post("/generate", response_model=AIGenerateResponse)
async def generate_metadata(
    req: AIGenerateRequest,
    db: Session = Depends(get_db),
):
    """실시간 메타 AI 생성 — Ollama llama3.2:3b 호출"""
    from api.programming.metadata.ai_engine import generate_metadata_ollama
    result = await generate_metadata_ollama(req, db)
    return result


@router.get("/emails", response_model=list[CpEmailLogOut])
def list_email_logs(
    processed: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(CpEmailLog)
    if processed is not None:
        q = q.filter(CpEmailLog.processed == processed)
    return q.order_by(CpEmailLog.received_at.desc()).limit(limit).all()
