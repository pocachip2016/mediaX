"""
Content CRUD / Review Queue / Dashboard / Staging / Pipeline status service.

service.py 분할 과정에서 추출 (dev-service-module-split Step 5).
"""

from datetime import datetime, date, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from api.programming.metadata.models import (
    Content, ContentMetadata, ContentBatchJob,
    ContentStatus, ContentType,
    ExternalMetaSource,
    ContentGenre, ContentCredit,
    ContentImage,
)
from api.programming.metadata.schemas import (
    ContentCreate, ContentUpdate, MetadataReviewAction, DashboardStats,
    StagingItem, BulkActionRequest, PipelineStatus,
    ExternalSourceOut,
)


# ── Content CRUD ──────────────────────────────────────────

def create_content(db: Session, data: ContentCreate) -> Content:
    from api.programming.metadata.models.content import IntakeChannel, PipelineStage, StageEventType
    from api.programming.metadata.stage_events import record_stage_event
    content_type = ContentType(data.content_type or "movie")
    if content_type in {ContentType.season, ContentType.episode} and not data.parent_id:
        raise ValueError(f"parent_id required for {content_type.value}")

    content = Content(**data.model_dump())
    if not content.intake_channel:
        content.intake_channel = IntakeChannel.MANUAL
    db.add(content)
    db.flush()
    record_stage_event(db, content.id, PipelineStage.S1_INTAKE, StageEventType.ENTERED,
                       source="manual", actor="user")
    meta = ContentMetadata(content_id=content.id, quality_score=0.0)
    db.add(meta)
    db.commit()
    db.refresh(content)
    return content


def update_content(db: Session, content_id: int, data: ContentUpdate) -> Content:
    """
    수동 수정 — 입력 필드를 manual source(콘텐츠당 1개)에 머지 저장 후 resolve_metadata 재실행.
    manual 우선순위(100)가 최고이므로 기존 tmdb/kobis 값보다 우선.
    cp_name은 Content 직접 필드라 manual source 미경유.
    directors/cast/genres 수정 시 기존 manual 관계 레코드는 먼저 삭제 (중복 방지).
    """
    from api.programming.metadata.models.external import ExternalSourceType
    from api.programming.metadata.models.person import ContentCredit, CreditRole
    from api.programming.metadata.models.taxonomy import ContentGenre
    from api.programming.metadata.service_recommendations import resolve_metadata

    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise ValueError(f"Content {content_id} not found")

    if hasattr(data, 'content_type') and data.content_type and data.content_type != content.content_type.value:
        children_count = db.query(Content).filter(Content.parent_id == content_id).count()
        if children_count > 0:
            raise ValueError(f"Cannot change content_type: {children_count} children exist")

    payload = {k: v for k, v in data.model_dump().items() if v is not None}

    if "cp_name" in payload:
        content.cp_name = payload.pop("cp_name")
        db.add(content)

    if payload:
        if "directors" in payload or "cast" in payload:
            existing_credits = db.query(ContentCredit).filter(
                ContentCredit.content_id == content_id,
                ContentCredit.source == "manual"
            ).all()
            for cc in existing_credits:
                if ("directors" in payload and cc.role == CreditRole.director) or \
                   ("cast" in payload and cc.role == CreditRole.actor):
                    db.delete(cc)
            db.flush()

        if "genres" in payload:
            db.query(ContentGenre).filter(
                ContentGenre.content_id == content_id,
                ContentGenre.source == "manual",
            ).delete()
            db.flush()

        manual_src = (
            db.query(ExternalMetaSource)
            .filter(
                ExternalMetaSource.content_id == content_id,
                ExternalMetaSource.source_type == ExternalSourceType.manual,
            )
            .first()
        )
        if not manual_src:
            manual_src = ExternalMetaSource(
                content_id=content_id,
                source_type=ExternalSourceType.manual,
                raw_json={},
                matched_at=datetime.utcnow(),
            )
            db.add(manual_src)
            db.flush()

        merged = dict(manual_src.raw_json or {})
        merged.update({k: v for k, v in payload.items() if v is not None})
        manual_src.raw_json = merged
        manual_src.matched_at = datetime.utcnow()
        db.flush()

        resolve_metadata(db, content_id)

    db.commit()
    db.refresh(content)
    return content


def get_content(db: Session, content_id: int) -> Optional[Content]:
    return (
        db.query(Content)
        .options(
            joinedload(Content.metadata_record),
            selectinload(Content.genres).joinedload(ContentGenre.genre),
            selectinload(Content.credits).joinedload(ContentCredit.person),
            selectinload(Content.external_sources),
            selectinload(Content.images),
        )
        .filter(Content.id == content_id)
        .first()
    )


def _primary_poster_url(content: Content) -> Optional[str]:
    from api.programming.metadata.models import ImageType
    posters = [img for img in content.images if img.image_type == ImageType.poster]
    if not posters:
        return None
    primary = next((p for p in posters if p.is_primary), None)
    return (primary or min(posters, key=lambda p: p.created_at)).url


def list_contents(
    db: Session,
    status: Optional[ContentStatus] = None,
    cp_name: Optional[str] = None,
    title: Optional[str] = None,
    content_type: Optional[ContentType] = None,
    production_year: Optional[int] = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[Content], int]:
    q = db.query(Content).options(
        joinedload(Content.metadata_record),
        selectinload(Content.images),
    )
    q = q.filter(Content.is_deleted == False)  # noqa: E712
    if status:
        q = q.filter(Content.status == status)
    if cp_name:
        q = q.filter(Content.cp_name.ilike(f"%{cp_name}%"))
    if title:
        q = q.filter(Content.title.ilike(f"%{title}%"))
    if content_type:
        q = q.filter(Content.content_type == content_type)
    if production_year:
        q = q.filter(Content.production_year == production_year)
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

    avg_score = db.query(func.avg(ContentMetadata.quality_score)).scalar() or 0.0

    score_dist = {
        "90+": db.query(ContentMetadata).filter(ContentMetadata.quality_score >= 90).count(),
        "70-89": db.query(ContentMetadata).filter(
            ContentMetadata.quality_score >= 70,
            ContentMetadata.quality_score < 90,
        ).count(),
        "~70": db.query(ContentMetadata).filter(ContentMetadata.quality_score < 70).count(),
    }

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


def trigger_enrichment(content_id: int) -> str:
    """에이전틱 검색 태스크 큐 등록"""
    from workers.tasks.metadata import enrich_content_metadata
    task = enrich_content_metadata.delay(content_id)
    return task.id


# ── Staging 대기풀 ─────────────────────────────────────────

def _build_diff(meta: Optional[ContentMetadata]) -> dict:
    """CP 원본 vs AI 생성 필드 비교 결과 생성"""
    if not meta:
        return {}
    diff = {}
    if meta.cp_synopsis and meta.ai_synopsis:
        diff["synopsis"] = {"cp": meta.cp_synopsis, "ai": meta.ai_synopsis}
    elif meta.ai_synopsis:
        diff["synopsis"] = {"cp": None, "ai": meta.ai_synopsis}
    if meta.cp_genre and meta.ai_genre_primary:
        diff["genre"] = {"cp": meta.cp_genre, "ai": meta.ai_genre_primary}
    if meta.cp_tags and meta.ai_mood_tags:
        diff["tags"] = {"cp": meta.cp_tags, "ai": meta.ai_mood_tags}
    return diff


def _content_to_staging_item(content: Content, db: Optional[Session] = None) -> StagingItem:
    from api.programming.metadata.schemas import ContentOut, MetadataOut
    meta = content.metadata_record
    ext_sources = [
        ExternalSourceOut(
            id=s.id,
            source_type=s.source_type.value if hasattr(s.source_type, "value") else s.source_type,
            external_id=s.external_id,
            matched_at=s.matched_at,
        )
        for s in (content.external_sources or [])
    ]
    children = []
    for child in (content.children or []):
        if child.content_type in (ContentType.season, ContentType.episode):
            children.append(_content_to_staging_item(child, db))

    inherited_meta = None
    if db is not None and content.content_type in (ContentType.season, ContentType.episode):
        from api.programming.metadata.inheritance import resolve_inherited_metadata
        inherited_meta = resolve_inherited_metadata(content, db)

    return StagingItem(
        content=ContentOut.model_validate(content),
        metadata=MetadataOut.model_validate(meta) if meta else None,
        diff=_build_diff(meta),
        external_sources=ext_sources,
        children=children,
        inherited_meta=inherited_meta,
    )


def get_staging_queue(
    db: Session,
    content_type: Optional[str] = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[StagingItem], int]:
    """staging 상태 콘텐츠 목록 (최상위 콘텐츠만, 계층은 children에 포함)"""
    q = (
        db.query(Content)
        .options(
            joinedload(Content.metadata_record),
            joinedload(Content.external_sources),
            joinedload(Content.children).joinedload(Content.metadata_record),
        )
        .filter(Content.status == ContentStatus.staging)
        .filter(Content.parent_id.is_(None))
    )
    if content_type:
        try:
            q = q.filter(Content.content_type == ContentType(content_type))
        except ValueError:
            pass
    total = q.count()
    contents = (
        q.order_by(ContentMetadata.quality_score.desc())
        .outerjoin(ContentMetadata)
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    items = [_content_to_staging_item(c) for c in contents]
    return items, total


def bulk_approve_staging(db: Session, req: BulkActionRequest) -> dict:
    """벌크 승인: staging → approved"""
    contents = (
        db.query(Content)
        .filter(Content.id.in_(req.content_ids))
        .filter(Content.status == ContentStatus.staging)
        .all()
    )
    approved_ids = []
    for c in contents:
        c.status = ContentStatus.approved
        meta = c.metadata_record
        if meta:
            meta.reviewed_by = req.reviewer
            meta.reviewed_at = datetime.utcnow()
            if not meta.final_synopsis:
                meta.final_synopsis = meta.ai_synopsis or meta.cp_synopsis
            if not meta.final_genre:
                meta.final_genre = meta.ai_genre_primary or meta.cp_genre
            if not meta.final_tags:
                meta.final_tags = meta.ai_mood_tags or meta.cp_tags
        approved_ids.append(c.id)
    db.commit()
    return {"approved": len(approved_ids), "ids": approved_ids}


def bulk_reject_staging(db: Session, req: BulkActionRequest) -> dict:
    """벌크 반려: staging → rejected"""
    contents = (
        db.query(Content)
        .filter(Content.id.in_(req.content_ids))
        .filter(Content.status == ContentStatus.staging)
        .all()
    )
    rejected_ids = []
    for c in contents:
        c.status = ContentStatus.rejected
        rejected_ids.append(c.id)
    db.commit()
    return {"rejected": len(rejected_ids), "ids": rejected_ids}


def get_content_hierarchy(db: Session, content_id: int) -> Optional[StagingItem]:
    """시리즈 계층 트리 반환"""
    content = (
        db.query(Content)
        .options(
            joinedload(Content.metadata_record),
            joinedload(Content.external_sources),
            joinedload(Content.children)
                .joinedload(Content.children)
                .joinedload(Content.metadata_record),
        )
        .filter(Content.id == content_id)
        .first()
    )
    if not content:
        return None
    return _content_to_staging_item(content, db)


# ── 파이프라인 현황 ────────────────────────────────────────

def get_pipeline_status(db: Session) -> PipelineStatus:
    """파이프라인 현황 집계"""
    def _count(status: ContentStatus) -> int:
        return db.query(Content).filter(Content.status == status).count()

    cutoff = datetime.utcnow() - timedelta(hours=6)
    failed_enrichment = (
        db.query(Content)
        .filter(
            Content.status == ContentStatus.processing,
            Content.updated_at < cutoff,
        )
        .count()
    )

    avg_score = db.query(func.avg(ContentMetadata.quality_score)).scalar() or 0.0

    return PipelineStatus(
        waiting_count=_count(ContentStatus.waiting),
        processing_count=_count(ContentStatus.processing),
        staging_count=_count(ContentStatus.staging),
        review_count=_count(ContentStatus.review),
        approved_count=_count(ContentStatus.approved),
        rejected_count=_count(ContentStatus.rejected),
        failed_enrichment_count=failed_enrichment,
        avg_quality_score=round(float(avg_score), 1),
    )
