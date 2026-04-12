"""
1.1 메타데이터 — 비즈니스 로직 서비스

담당:
  - 콘텐츠 CRUD
  - AI 처리 트리거 (Celery 큐)
  - 검수 큐 액션 처리
  - 대시보드 통계 집계
"""

from datetime import datetime, date
from typing import Optional

from sqlalchemy import func, case
from sqlalchemy.orm import Session, joinedload

from api.programming.metadata.models import (
    Content, ContentMetadata, CpEmailLog,
    ContentStatus, ContentType,
)
from api.programming.metadata.schemas import (
    ContentCreate, MetadataReviewAction, DashboardStats,
)


# ── Content CRUD ──────────────────────────────────────────

def create_content(db: Session, data: ContentCreate) -> Content:
    content = Content(**data.model_dump())
    db.add(content)
    db.flush()
    # 메타 레코드 초기화
    meta = ContentMetadata(content_id=content.id, quality_score=0.0)
    db.add(meta)
    db.commit()
    db.refresh(content)
    return content


def get_content(db: Session, content_id: int) -> Optional[Content]:
    return (
        db.query(Content)
        .options(joinedload(Content.metadata_record))
        .filter(Content.id == content_id)
        .first()
    )


def list_contents(
    db: Session,
    status: Optional[ContentStatus] = None,
    cp_name: Optional[str] = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[Content], int]:
    q = db.query(Content).options(joinedload(Content.metadata_record))
    if status:
        q = q.filter(Content.status == status)
    if cp_name:
        q = q.filter(Content.cp_name == cp_name)
    total = q.count()
    items = q.order_by(Content.created_at.desc()).offset((page - 1) * size).limit(size).all()
    return items, total


# ── 검수 큐 ───────────────────────────────────────────────

def get_review_queue(
    db: Session, page: int = 1, size: int = 20
) -> tuple[list[Content], int]:
    """70~89점 콘텐츠 목록 (우선순위: 낮은 점수 먼저)"""
    q = (
        db.query(Content)
        .join(ContentMetadata)
        .options(joinedload(Content.metadata_record))
        .filter(Content.status == ContentStatus.review)
        .filter(ContentMetadata.quality_score >= 70)
        .filter(ContentMetadata.quality_score < 90)
        .order_by(ContentMetadata.quality_score.asc())
    )
    total = q.count()
    items = q.offset((page - 1) * size).limit(size).all()
    return items, total


def apply_review_action(
    db: Session, content_id: int, action: MetadataReviewAction
) -> Content:
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise ValueError(f"Content {content_id} not found")

    meta = content.metadata_record

    if action.action == "approve":
        content.status = ContentStatus.approved
        if meta:
            meta.final_synopsis = action.final_synopsis or meta.ai_synopsis
            meta.final_genre = action.final_genre or meta.ai_genre_primary
            meta.final_tags = action.final_tags or meta.ai_mood_tags
            meta.reviewed_by = action.reviewer
            meta.reviewed_at = datetime.utcnow()

    elif action.action == "modify":
        content.status = ContentStatus.approved
        if meta:
            meta.final_synopsis = action.final_synopsis
            meta.final_genre = action.final_genre
            meta.final_tags = action.final_tags
            meta.reviewed_by = action.reviewer
            meta.reviewed_at = datetime.utcnow()

    elif action.action == "reject":
        content.status = ContentStatus.rejected

    db.commit()
    db.refresh(content)
    return content


# ── 대시보드 통계 ──────────────────────────────────────────

def get_dashboard_stats(db: Session, target_date: Optional[date] = None) -> DashboardStats:
    if not target_date:
        target_date = date.today()

    today_start = datetime.combine(target_date, datetime.min.time())
    today_end = datetime.combine(target_date, datetime.max.time())

    base = db.query(Content).filter(
        Content.created_at >= today_start,
        Content.created_at <= today_end,
    )

    total_today = base.count()
    auto_registered = base.filter(Content.status == ContentStatus.approved).count()
    review_pending = base.filter(Content.status == ContentStatus.review).count()
    rejected = base.filter(Content.status == ContentStatus.rejected).count()

    # 평균 품질 스코어
    avg_score = db.query(func.avg(ContentMetadata.quality_score)).scalar() or 0.0

    # 점수 분포
    score_dist = {
        "90+": db.query(ContentMetadata).filter(ContentMetadata.quality_score >= 90).count(),
        "70-89": db.query(ContentMetadata).filter(
            ContentMetadata.quality_score >= 70,
            ContentMetadata.quality_score < 90,
        ).count(),
        "~70": db.query(ContentMetadata).filter(ContentMetadata.quality_score < 70).count(),
    }

    # CP사별 통계
    cp_rows = (
        db.query(Content.cp_name, func.count(Content.id).label("count"))
        .filter(Content.cp_name.isnot(None))
        .group_by(Content.cp_name)
        .order_by(func.count(Content.id).desc())
        .limit(10)
        .all()
    )
    cp_stats = [{"cp_name": r.cp_name, "count": r.count} for r in cp_rows]

    return DashboardStats(
        total_today=total_today,
        auto_registered=auto_registered,
        review_pending=review_pending,
        rejected=rejected,
        avg_quality_score=round(float(avg_score), 1),
        score_distribution=score_dist,
        cp_stats=cp_stats,
    )


# ── AI 처리 트리거 ─────────────────────────────────────────

def trigger_ai_processing(content_id: int) -> str:
    """Celery 태스크 큐에 AI 처리 요청 등록"""
    from workers.tasks.metadata import process_content_metadata
    task = process_content_metadata.delay(content_id)
    return task.id
