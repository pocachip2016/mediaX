"""
1.1 메타데이터 API 라우터

엔드포인트 (기존):
  GET    /dashboard              - 오늘 통계
  GET    /contents               - 콘텐츠 목록 (페이징·필터)
  POST   /contents               - 콘텐츠 수동 등록
  GET    /contents/{id}          - 콘텐츠 상세
  POST   /contents/{id}/process  - AI 처리 트리거
  GET    /queue                  - 검수 큐 (70~89점)
  POST   /queue/{id}/action      - 검수 액션 (승인/수정/반려)
  POST   /generate               - 실시간 메타 AI 생성
  GET    /emails                 - CP 이메일 수신 이력

신규 엔드포인트 (파이프라인):
  GET    /staging                    - 검토 대기풀 목록
  POST   /staging/bulk-approve       - 벌크 승인
  POST   /staging/bulk-reject        - 벌크 반려
  POST   /contents/{id}/enrich       - 에이전틱 검색 수동 트리거
  GET    /contents/{id}/hierarchy    - 시리즈 계층 트리
  GET    /pipeline/status            - 파이프라인 현황
  POST   /upload/batch               - CSV/엑셀 배치 업로드
  GET    /upload/batch/{job_id}      - 배치 작업 상태 조회

신규 엔드포인트 (3분류 메타):
  GET    /text                       - 글자메타 목록 (시리즈 계층 포함)
  GET    /text/{id}                  - 특정 콘텐츠 글자메타
  PUT    /text/{id}                  - 글자메타 수정
  POST   /text/bulk-complete         - 글자메타 일괄 완료
  GET    /image                      - 이미지메타 목록
  GET    /image/{id}                 - 특정 콘텐츠 이미지 목록
  GET    /video                      - 영상메타 목록
  GET    /video/{id}                 - 특정 콘텐츠 영상메타
  PUT    /video/{id}                 - 영상메타 수정
  POST   /video/bulk-complete        - 영상메타 일괄 완료
  GET    /service-readiness          - 서비스 준비 현황 통계
"""

import io
import csv
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session

from shared.database import get_db
from api.programming.metadata import service
from api.programming.metadata.models import ContentStatus, ContentType, ContentBatchJob
from api.programming.metadata.schemas import (
    ContentCreate, ContentOut, ContentDetail, PaginatedContents,
    MetadataReviewAction, AIGenerateRequest, AIGenerateResponse,
    DashboardStats, CpEmailLogOut,
    PaginatedStagingItems, StagingItem, BulkActionRequest, PipelineStatus,
    BatchJobOut,
    TextMetaOut, TextMetaUpdate, TextMetaBulkCompleteRequest,
    ImageMetaOut,
    VideoMetaOut, VideoMetaUpdate, VideoBulkCompleteRequest,
    ServiceReadinessStats,
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
    title: str | None = Query(None),
    content_type: ContentType | None = Query(None),
    production_year: int | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    items, total = service.list_contents(
        db,
        status=status,
        cp_name=cp_name,
        title=title,
        content_type=content_type,
        production_year=production_year,
        page=page,
        size=size,
    )
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


# ── Staging 대기풀 엔드포인트 ─────────────────────────────

@router.get("/staging", response_model=PaginatedStagingItems)
def get_staging_queue(
    content_type: Optional[str] = Query(None, description="movie | series | season | episode"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """운영자 검토 대기풀 목록 (staging 상태, 최상위 콘텐츠 + 계층 포함)"""
    items, total = service.get_staging_queue(db, content_type=content_type, page=page, size=size)
    return PaginatedStagingItems(items=items, total=total, page=page, size=size)


@router.post("/staging/bulk-approve")
def bulk_approve(req: BulkActionRequest, db: Session = Depends(get_db)):
    """선택 항목 일괄 승인 (staging → approved)"""
    return service.bulk_approve_staging(db, req)


@router.post("/staging/bulk-reject")
def bulk_reject(req: BulkActionRequest, db: Session = Depends(get_db)):
    """선택 항목 일괄 반려 (staging → rejected)"""
    return service.bulk_reject_staging(db, req)


# ── 에이전틱 검색 수동 트리거 ─────────────────────────────

@router.post("/contents/{content_id}/enrich")
def trigger_enrichment(content_id: int, db: Session = Depends(get_db)):
    """에이전틱 멀티소스 검색 수동 트리거 (TMDB + KOBIS)"""
    content = service.get_content(db, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    task_id = service.trigger_enrichment(content_id)
    return {"task_id": task_id, "message": "에이전틱 검색 큐에 등록되었습니다"}


@router.get("/contents/{content_id}/hierarchy", response_model=StagingItem)
def get_content_hierarchy(content_id: int, db: Session = Depends(get_db)):
    """시리즈 계층 트리 반환 (시리즈 > 시즌 > 에피소드)"""
    item = service.get_content_hierarchy(db, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
    return item


# ── 파이프라인 현황 ────────────────────────────────────────

@router.get("/pipeline/status", response_model=PipelineStatus)
def get_pipeline_status(db: Session = Depends(get_db)):
    """파이프라인 현황: 상태별 콘텐츠 수, 평균 품질, 실패 항목"""
    return service.get_pipeline_status(db)


# ── 배치 업로드 ───────────────────────────────────────────

@router.post("/upload/batch", response_model=BatchJobOut, status_code=201)
async def batch_upload(
    file: UploadFile = File(..., description="CSV 또는 Excel 파일"),
    cp_name: Optional[str] = Form(None),
    created_by: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """CSV/엑셀 배치 업로드 → 파싱 후 Content(waiting) 생성 + AI 처리 큐 등록"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="파일명이 없습니다")

    allowed_extensions = (".csv", ".xlsx", ".xls")
    if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
        raise HTTPException(status_code=400, detail="CSV 또는 Excel 파일만 허용됩니다")

    content_bytes = await file.read()
    file_size = len(content_bytes)
    if file_size > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(status_code=400, detail="파일 크기가 10MB를 초과합니다")

    # 배치 작업 생성
    job = service.create_batch_job(
        db, file_name=file.filename, cp_name=cp_name,
        created_by=created_by, file_size=file_size,
    )

    # CSV 파싱 (Excel은 추후 openpyxl 연동)
    rows = []
    try:
        if file.filename.lower().endswith(".csv"):
            text = content_bytes.decode("utf-8-sig", errors="replace")
            reader = csv.DictReader(io.StringIO(text))
            for row in reader:
                rows.append({
                    "title": row.get("title") or row.get("제목") or "",
                    "production_year": _safe_int(row.get("production_year") or row.get("제작연도")),
                    "content_type": _normalize_content_type(
                        row.get("content_type") or row.get("타입") or "movie"
                    ),
                    "cp_name": row.get("cp_name") or row.get("CP사") or cp_name,
                    "cp_synopsis": row.get("synopsis") or row.get("시놉시스") or "",
                })
        else:
            # Excel 지원 — openpyxl 없으면 에러 메시지 반환
            try:
                import openpyxl
                wb = openpyxl.load_workbook(io.BytesIO(content_bytes), data_only=True)
                ws = wb.active
                headers = [str(c.value or "").strip() for c in next(ws.iter_rows(max_row=1))]
                header_map = {h: i for i, h in enumerate(headers)}
                for row_cells in ws.iter_rows(min_row=2, values_only=True):
                    def _get(col_names):
                        for n in col_names:
                            idx = header_map.get(n)
                            if idx is not None and row_cells[idx]:
                                return str(row_cells[idx])
                        return ""
                    rows.append({
                        "title": _get(["title", "제목"]),
                        "production_year": _safe_int(_get(["production_year", "제작연도"])),
                        "content_type": _normalize_content_type(_get(["content_type", "타입"]) or "movie"),
                        "cp_name": _get(["cp_name", "CP사"]) or cp_name,
                        "cp_synopsis": _get(["synopsis", "시놉시스"]),
                    })
            except ImportError:
                raise HTTPException(
                    status_code=422,
                    detail="Excel 파일 처리에 openpyxl이 필요합니다. CSV를 사용하거나 서버에 openpyxl을 설치하세요."
                )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"파일 파싱 실패: {exc}")

    # 비어있는 행 제거
    rows = [r for r in rows if r.get("title")]

    result = service.process_batch_rows(db, job, rows)
    db.refresh(job)
    return BatchJobOut.model_validate(job)


@router.get("/upload/batch/{job_id}", response_model=BatchJobOut)
def get_batch_job(job_id: int, db: Session = Depends(get_db)):
    """배치 작업 상태 조회"""
    job = db.query(ContentBatchJob).filter(ContentBatchJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="배치 작업을 찾을 수 없습니다")
    return BatchJobOut.model_validate(job)


# ── 글자메타 엔드포인트 ───────────────────────────────────────────────────────

@router.get("/text", summary="글자메타 목록 (시리즈 계층 포함)")
def list_text_meta(
    completed: Optional[bool] = Query(None, description="완료 여부 필터 (true/false)"),
    content_type: Optional[str] = Query(None, description="movie | series"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return service.get_text_meta_list(db, completed=completed, content_type_filter=content_type, page=page, size=size)


@router.post("/text/bulk-complete", summary="글자메타 일괄 완료 처리")
def bulk_complete_text_meta(req: TextMetaBulkCompleteRequest, db: Session = Depends(get_db)):
    return service.bulk_complete_text_meta(db, req.content_ids)


@router.get("/text/{content_id}", response_model=TextMetaOut, summary="특정 콘텐츠 글자메타")
def get_text_meta(content_id: int, db: Session = Depends(get_db)):
    result = service.get_text_meta(db, content_id)
    if not result:
        raise HTTPException(status_code=404, detail="콘텐츠를 찾을 수 없습니다")
    return result


@router.put("/text/{content_id}", response_model=TextMetaOut, summary="글자메타 수정")
def update_text_meta(content_id: int, data: TextMetaUpdate, db: Session = Depends(get_db)):
    result = service.update_text_meta(db, content_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="콘텐츠를 찾을 수 없습니다")
    return result


# ── 이미지메타 엔드포인트 ─────────────────────────────────────────────────────

@router.get("/image", summary="이미지메타 목록")
def list_image_meta(
    completed: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return service.get_image_meta_list(db, completed=completed, page=page, size=size)


@router.get("/image/{content_id}", response_model=ImageMetaOut, summary="특정 콘텐츠 이미지 목록")
def get_image_meta(content_id: int, db: Session = Depends(get_db)):
    result = service.get_image_meta(db, content_id)
    if not result:
        raise HTTPException(status_code=404, detail="콘텐츠를 찾을 수 없습니다")
    return result


# ── 영상메타 엔드포인트 ───────────────────────────────────────────────────────

@router.get("/video", summary="영상메타 목록")
def list_video_meta(
    completed: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return service.get_video_meta_list(db, completed=completed, page=page, size=size)


@router.post("/video/bulk-complete", summary="영상메타 일괄 완료 처리")
def bulk_complete_video_meta(req: VideoBulkCompleteRequest, db: Session = Depends(get_db)):
    return service.bulk_complete_video_meta(db, req.content_ids)


@router.get("/video/{content_id}", response_model=VideoMetaOut, summary="특정 콘텐츠 영상메타")
def get_video_meta(content_id: int, db: Session = Depends(get_db)):
    result = service.get_video_meta(db, content_id)
    if not result:
        raise HTTPException(status_code=404, detail="콘텐츠를 찾을 수 없습니다")
    return result


@router.put("/video/{content_id}", response_model=VideoMetaOut, summary="영상메타 수정")
def update_video_meta(content_id: int, data: VideoMetaUpdate, db: Session = Depends(get_db)):
    result = service.update_video_meta(db, content_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="콘텐츠를 찾을 수 없습니다")
    return result


# ── 서비스 준비 현황 ──────────────────────────────────────────────────────────

@router.get("/service-readiness", response_model=ServiceReadinessStats, summary="서비스 준비 현황 통계")
def get_service_readiness(db: Session = Depends(get_db)):
    return service.get_service_readiness(db)


def _safe_int(val) -> Optional[int]:
    try:
        return int(val) if val else None
    except (ValueError, TypeError):
        return None


def _normalize_content_type(val: str) -> str:
    mapping = {
        "영화": "movie", "movie": "movie",
        "시리즈": "series", "series": "series", "드라마": "series",
        "시즌": "season", "season": "season",
        "에피소드": "episode", "episode": "episode",
    }
    return mapping.get(val.strip(), "movie")
