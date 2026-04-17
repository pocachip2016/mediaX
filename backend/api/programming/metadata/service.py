"""
1.1 메타데이터 — 비즈니스 로직 서비스

담당:
  - 콘텐츠 CRUD
  - AI 처리 트리거 (Celery 큐)
  - 검수 큐 액션 처리
  - 대시보드 통계 집계
  - Staging 대기풀 (벌크 승인/반려, diff 생성)
  - 파이프라인 현황
  - 배치 업로드
"""

from datetime import datetime, date, timedelta
from typing import Optional

from sqlalchemy import func, case
from sqlalchemy.orm import Session, joinedload

from api.programming.metadata.models import (
    Content, ContentMetadata, CpEmailLog, ContentBatchJob,
    ContentStatus, ContentType,
    ExternalMetaSource,
)
from api.programming.metadata.schemas import (
    ContentCreate, MetadataReviewAction, DashboardStats,
    StagingItem, BulkActionRequest, PipelineStatus,
    ExternalSourceOut,
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
    title: Optional[str] = None,
    content_type: Optional[ContentType] = None,
    production_year: Optional[int] = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[Content], int]:
    q = db.query(Content).options(joinedload(Content.metadata_record))
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


def _content_to_staging_item(content: Content) -> StagingItem:
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
    # 자식 계층 (시리즈 → 시즌 레벨만, 에피소드는 별도 조회로 lazy 방지)
    children = []
    for child in (content.children or []):
        if child.content_type in (ContentType.season, ContentType.episode):
            children.append(_content_to_staging_item(child))

    return StagingItem(
        content=ContentOut.model_validate(content),
        metadata=MetadataOut.model_validate(meta) if meta else None,
        diff=_build_diff(meta),
        external_sources=ext_sources,
        children=children,
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
        .filter(Content.parent_id.is_(None))   # 최상위만
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
    return _content_to_staging_item(content)


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


# ── 배치 업로드 ───────────────────────────────────────────

def create_batch_job(
    db: Session,
    file_name: str,
    cp_name: Optional[str],
    created_by: Optional[str],
    file_size: Optional[int] = None,
) -> ContentBatchJob:
    job = ContentBatchJob(
        job_name=f"배치업로드_{file_name}",
        cp_name=cp_name,
        file_name=file_name,
        file_size_bytes=file_size,
        status="pending",
        created_by=created_by,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def process_batch_rows(
    db: Session,
    job: ContentBatchJob,
    rows: list[dict],
) -> dict:
    """파싱된 배치 행 → Content(waiting) 생성 + AI 처리 큐 등록"""
    from workers.tasks.metadata import process_content_metadata

    job.status = "processing"
    job.total_count = len(rows)
    db.flush()

    success = 0
    failed = 0
    errors = []

    for i, row in enumerate(rows):
        try:
            title = row.get("title", "").strip()
            if not title:
                raise ValueError("제목 없음")
            content = Content(
                title=title,
                content_type=ContentType(row.get("content_type", "movie")),
                status=ContentStatus.waiting,
                cp_name=row.get("cp_name") or job.cp_name,
                production_year=row.get("production_year"),
            )
            db.add(content)
            db.flush()
            meta = ContentMetadata(
                content_id=content.id,
                cp_synopsis=row.get("cp_synopsis"),
                quality_score=0.0,
            )
            db.add(meta)
            db.flush()
            process_content_metadata.delay(content.id)
            success += 1
        except Exception as exc:
            failed += 1
            errors.append({"row": i + 1, "title": row.get("title", ""), "error": str(exc)})

    job.success_count = success
    job.failed_count = failed
    job.error_log = errors
    job.status = "done"
    job.finished_at = datetime.utcnow()
    job.parsed_count = len(rows)
    db.commit()

    return {"success": success, "failed": failed, "job_id": job.id}


# ── 글자메타 서비스 ────────────────────────────────────────────────────────────

def _build_text_meta_out(content: Content) -> dict:
    """Content → TextMetaOut 딕셔너리 변환 (재귀 없음, 호출자가 children 주입)"""
    meta = content.metadata_record
    synopsis = None
    genre_primary = None
    genre_secondary = None
    mood_tags = None
    rating_suggestion = None
    text_meta_completed = False

    if meta:
        synopsis = meta.final_synopsis or meta.ai_synopsis
        genre_primary = meta.final_genre or meta.ai_genre_primary
        genre_secondary = meta.ai_genre_secondary
        mood_tags = meta.final_tags or meta.ai_mood_tags
        rating_suggestion = meta.ai_rating_suggestion
        text_meta_completed = meta.text_meta_completed or False

    return {
        "id": content.id,
        "title": content.title,
        "content_type": content.content_type,
        "cp_name": content.cp_name,
        "production_year": content.production_year,
        "season_number": content.season_number,
        "episode_number": content.episode_number,
        "parent_id": content.parent_id,
        "synopsis": synopsis,
        "genre_primary": genre_primary,
        "genre_secondary": genre_secondary,
        "mood_tags": mood_tags,
        "rating_suggestion": rating_suggestion,
        "text_meta_completed": text_meta_completed,
        "episode_completed_count": 0,
        "episode_total_count": 0,
        "children": [],
    }


def _collect_all_descendants(content: Content, db: Session) -> list[Content]:
    """content(series/season)의 모든 하위 콘텐츠(season/episode) 수집"""
    result = []
    direct_children = db.query(Content).filter(Content.parent_id == content.id).all()
    for child in direct_children:
        result.append(child)
        result.extend(_collect_all_descendants(child, db))
    return result


def get_text_meta_list(
    db: Session,
    completed: Optional[bool] = None,
    content_type_filter: Optional[str] = None,
    page: int = 1,
    size: int = 20,
):
    """글자메타 목록 반환. 시리즈는 children(시즌>에피소드) 포함."""
    from api.programming.metadata.schemas import TextMetaOut

    # 최상위 콘텐츠만 (parent_id is None)
    q = db.query(Content).options(
        joinedload(Content.metadata_record),
        joinedload(Content.children).joinedload(Content.children).joinedload(Content.metadata_record),
    ).filter(Content.parent_id.is_(None))

    if content_type_filter == "movie":
        q = q.filter(Content.content_type == ContentType.movie)
    elif content_type_filter == "series":
        q = q.filter(Content.content_type == ContentType.series)

    if completed is not None:
        q = q.join(Content.metadata_record).filter(
            ContentMetadata.text_meta_completed == completed
        )

    total = q.count()
    contents = q.offset((page - 1) * size).limit(size).all()

    items = []
    for c in contents:
        item = _build_text_meta_out(c)
        if c.content_type == ContentType.series:
            # 시즌 계층 구성
            seasons = sorted(
                [ch for ch in c.children if ch.content_type == ContentType.season],
                key=lambda x: x.season_number or 0
            )
            season_items = []
            total_eps = 0
            completed_eps = 0
            for season in seasons:
                s_item = _build_text_meta_out(season)
                episodes = sorted(
                    [ep for ep in season.children if ep.content_type == ContentType.episode],
                    key=lambda x: x.episode_number or 0
                )
                ep_items = [_build_text_meta_out(ep) for ep in episodes]
                s_item["children"] = ep_items
                s_item["episode_total_count"] = len(ep_items)
                s_item["episode_completed_count"] = sum(1 for ep in ep_items if ep["text_meta_completed"])
                season_items.append(s_item)
                total_eps += len(ep_items)
                completed_eps += s_item["episode_completed_count"]
            item["children"] = season_items
            item["episode_total_count"] = total_eps
            item["episode_completed_count"] = completed_eps
        items.append(TextMetaOut(**item))

    return {"items": items, "total": total, "page": page, "size": size}


def get_text_meta(db: Session, content_id: int):
    """특정 콘텐츠 글자메타 조회"""
    from api.programming.metadata.schemas import TextMetaOut

    content = db.query(Content).options(joinedload(Content.metadata_record)).filter(
        Content.id == content_id
    ).first()
    if not content:
        return None
    item = _build_text_meta_out(content)
    return TextMetaOut(**item)


def update_text_meta(db: Session, content_id: int, data):
    """글자메타 수정 + 완료 플래그 업데이트"""
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        return None

    meta = content.metadata_record
    if not meta:
        meta = ContentMetadata(content_id=content_id)
        db.add(meta)

    if data.synopsis is not None:
        meta.final_synopsis = data.synopsis
    if data.genre_primary is not None:
        meta.final_genre = data.genre_primary
    if data.mood_tags is not None:
        meta.final_tags = data.mood_tags
    if data.rating_suggestion is not None:
        meta.ai_rating_suggestion = data.rating_suggestion
    meta.text_meta_completed = data.completed
    db.commit()

    # 시리즈/시즌인 경우 상위 자동 업데이트
    _propagate_text_completion(db, content)

    return get_text_meta(db, content_id)


def bulk_complete_text_meta(db: Session, content_ids: list[int]):
    """다중 콘텐츠 글자메타 완료 처리. 시리즈 id 포함 시 하위 전체 처리."""
    processed = set()
    for cid in content_ids:
        content = db.query(Content).options(joinedload(Content.metadata_record)).filter(
            Content.id == cid
        ).first()
        if not content:
            continue
        # 자신 + 모든 하위 콘텐츠
        targets = [content] + _collect_all_descendants(content, db)
        for target in targets:
            if target.id in processed:
                continue
            processed.add(target.id)
            meta = target.metadata_record
            if not meta:
                meta = ContentMetadata(content_id=target.id)
                db.add(meta)
            meta.text_meta_completed = True
    db.commit()
    return {"updated": len(processed)}


def _propagate_text_completion(db: Session, content: Content):
    """에피소드/시즌 완료 시 상위(시즌/시리즈) 자동 완료 여부 업데이트"""
    if not content.parent_id:
        return
    parent = db.query(Content).options(
        joinedload(Content.metadata_record),
        joinedload(Content.children).joinedload(Content.metadata_record),
    ).filter(Content.id == content.parent_id).first()
    if not parent:
        return

    children = db.query(Content).options(joinedload(Content.metadata_record)).filter(
        Content.parent_id == parent.id
    ).all()
    if not children:
        return

    all_done = all(
        (c.metadata_record and c.metadata_record.text_meta_completed)
        for c in children
    )
    meta = parent.metadata_record
    if not meta:
        meta = ContentMetadata(content_id=parent.id)
        db.add(meta)
    meta.text_meta_completed = all_done
    db.commit()
    # 재귀: 상위도 전파
    _propagate_text_completion(db, parent)


# ── 이미지메타 서비스 ──────────────────────────────────────────────────────────

def get_image_meta_list(db: Session, completed: Optional[bool] = None, page: int = 1, size: int = 20):
    """이미지메타 목록 + 5종 이미지 완성도"""
    from api.programming.metadata.schemas import ImageMetaOut, ContentImageOut
    from api.programming.metadata.models import ContentImage

    q = db.query(Content).options(
        joinedload(Content.metadata_record),
        joinedload(Content.images),
    ).filter(Content.parent_id.is_(None))

    if completed is not None:
        q = q.join(Content.metadata_record).filter(
            ContentMetadata.image_meta_completed == completed
        )

    total = q.count()
    contents = q.offset((page - 1) * size).limit(size).all()

    items = []
    for c in contents:
        meta = c.metadata_record
        images = [ContentImageOut.model_validate(img) for img in c.images] if c.images else []
        image_types = {img.image_type for img in c.images} if c.images else set()
        items.append(ImageMetaOut(
            id=c.id,
            title=c.title,
            content_type=c.content_type,
            cp_name=c.cp_name,
            production_year=c.production_year,
            images=images,
            has_poster="poster" in image_types,
            has_thumbnail="thumbnail" in image_types,
            has_stillcut="stillcut" in image_types,
            has_banner="banner" in image_types,
            has_logo="logo" in image_types,
            image_meta_completed=(meta.image_meta_completed if meta else False),
        ))

    return {"items": items, "total": total, "page": page, "size": size}


def get_image_meta(db: Session, content_id: int):
    """특정 콘텐츠 이미지 목록 조회"""
    from api.programming.metadata.schemas import ImageMetaOut, ContentImageOut

    content = db.query(Content).options(
        joinedload(Content.metadata_record),
        joinedload(Content.images),
    ).filter(Content.id == content_id).first()
    if not content:
        return None

    meta = content.metadata_record
    images = [ContentImageOut.model_validate(img) for img in content.images] if content.images else []
    image_types = {img.image_type for img in content.images} if content.images else set()
    return ImageMetaOut(
        id=content.id,
        title=content.title,
        content_type=content.content_type,
        cp_name=content.cp_name,
        production_year=content.production_year,
        images=images,
        has_poster="poster" in image_types,
        has_thumbnail="thumbnail" in image_types,
        has_stillcut="stillcut" in image_types,
        has_banner="banner" in image_types,
        has_logo="logo" in image_types,
        image_meta_completed=(meta.image_meta_completed if meta else False),
    )


def update_image_completion(db: Session, content_id: int):
    """이미지 5종 여부 확인 후 image_meta_completed 자동 업데이트"""
    from api.programming.metadata.models import ContentImage

    content = db.query(Content).options(
        joinedload(Content.metadata_record),
        joinedload(Content.images),
    ).filter(Content.id == content_id).first()
    if not content:
        return

    image_types = {img.image_type for img in content.images} if content.images else set()
    required = {"poster", "thumbnail", "stillcut", "banner", "logo"}
    completed = required.issubset(image_types)

    meta = content.metadata_record
    if not meta:
        meta = ContentMetadata(content_id=content_id)
        db.add(meta)
    meta.image_meta_completed = completed
    db.commit()


# ── 영상메타 서비스 ──────────────────────────────────────────────────────────

def get_video_meta_list(db: Session, completed: Optional[bool] = None, page: int = 1, size: int = 20):
    """영상메타 목록"""
    from api.programming.metadata.schemas import VideoMetaOut

    q = db.query(Content).options(joinedload(Content.metadata_record)).filter(
        Content.parent_id.is_(None)
    )

    if completed is not None:
        q = q.join(Content.metadata_record).filter(
            ContentMetadata.video_meta_completed == completed
        )

    total = q.count()
    contents = q.offset((page - 1) * size).limit(size).all()

    items = []
    for c in contents:
        meta = c.metadata_record
        items.append(VideoMetaOut(
            id=c.id,
            title=c.title,
            content_type=c.content_type,
            cp_name=c.cp_name,
            production_year=c.production_year,
            video_resolution=meta.video_resolution if meta else None,
            video_format=meta.video_format if meta else None,
            codec_video=meta.codec_video if meta else None,
            codec_audio=meta.codec_audio if meta else None,
            video_bitrate_kbps=meta.video_bitrate_kbps if meta else None,
            video_duration_seconds=meta.video_duration_seconds if meta else None,
            subtitle_languages=meta.subtitle_languages if meta else None,
            drm_type=meta.drm_type if meta else None,
            preview_clip_url=meta.preview_clip_url if meta else None,
            video_meta_completed=(meta.video_meta_completed if meta else False),
        ))

    return {"items": items, "total": total, "page": page, "size": size}


def get_video_meta(db: Session, content_id: int):
    """특정 콘텐츠 영상메타 조회"""
    from api.programming.metadata.schemas import VideoMetaOut

    content = db.query(Content).options(joinedload(Content.metadata_record)).filter(
        Content.id == content_id
    ).first()
    if not content:
        return None

    meta = content.metadata_record
    return VideoMetaOut(
        id=content.id,
        title=content.title,
        content_type=content.content_type,
        cp_name=content.cp_name,
        production_year=content.production_year,
        video_resolution=meta.video_resolution if meta else None,
        video_format=meta.video_format if meta else None,
        codec_video=meta.codec_video if meta else None,
        codec_audio=meta.codec_audio if meta else None,
        video_bitrate_kbps=meta.video_bitrate_kbps if meta else None,
        video_duration_seconds=meta.video_duration_seconds if meta else None,
        subtitle_languages=meta.subtitle_languages if meta else None,
        drm_type=meta.drm_type if meta else None,
        preview_clip_url=meta.preview_clip_url if meta else None,
        video_meta_completed=(meta.video_meta_completed if meta else False),
    )


def update_video_meta(db: Session, content_id: int, data):
    """영상메타 수정"""
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        return None

    meta = content.metadata_record
    if not meta:
        meta = ContentMetadata(content_id=content_id)
        db.add(meta)

    if data.video_resolution is not None:
        meta.video_resolution = data.video_resolution
    if data.video_format is not None:
        meta.video_format = data.video_format
    if data.codec_video is not None:
        meta.codec_video = data.codec_video
    if data.codec_audio is not None:
        meta.codec_audio = data.codec_audio
    if data.video_bitrate_kbps is not None:
        meta.video_bitrate_kbps = data.video_bitrate_kbps
    if data.video_duration_seconds is not None:
        meta.video_duration_seconds = data.video_duration_seconds
    if data.subtitle_languages is not None:
        meta.subtitle_languages = data.subtitle_languages
    if data.drm_type is not None:
        meta.drm_type = data.drm_type
    if data.preview_clip_url is not None:
        meta.preview_clip_url = data.preview_clip_url
    meta.video_meta_completed = data.completed
    db.commit()

    return get_video_meta(db, content_id)


def bulk_complete_video_meta(db: Session, content_ids: list[int]):
    """다중 콘텐츠 영상메타 완료 처리. 해상도·코덱 미입력 시 건너뜀."""
    updated = 0
    skipped = []
    for cid in content_ids:
        content = db.query(Content).options(joinedload(Content.metadata_record)).filter(
            Content.id == cid
        ).first()
        if not content:
            continue
        meta = content.metadata_record
        if not meta or not (meta.video_resolution and meta.codec_video):
            skipped.append(cid)
            continue
        meta.video_meta_completed = True
        updated += 1
    db.commit()
    return {"updated": updated, "skipped": skipped}


# ── 서비스 준비 현황 ──────────────────────────────────────────────────────────

def get_service_readiness(db: Session):
    """서비스 준비 현황 통계 반환"""
    from api.programming.metadata.schemas import ServiceReadinessStats

    total = db.query(Content).filter(Content.parent_id.is_(None)).count()

    # metadata_record가 있는 최상위 콘텐츠 기준
    text_completed = db.query(ContentMetadata).join(
        Content, ContentMetadata.content_id == Content.id
    ).filter(
        Content.parent_id.is_(None),
        ContentMetadata.text_meta_completed.is_(True),
    ).count()

    image_completed = db.query(ContentMetadata).join(
        Content, ContentMetadata.content_id == Content.id
    ).filter(
        Content.parent_id.is_(None),
        ContentMetadata.image_meta_completed.is_(True),
    ).count()

    video_completed = db.query(ContentMetadata).join(
        Content, ContentMetadata.content_id == Content.id
    ).filter(
        Content.parent_id.is_(None),
        ContentMetadata.video_meta_completed.is_(True),
    ).count()

    all_completed = db.query(ContentMetadata).join(
        Content, ContentMetadata.content_id == Content.id
    ).filter(
        Content.parent_id.is_(None),
        ContentMetadata.text_meta_completed.is_(True),
        ContentMetadata.image_meta_completed.is_(True),
        ContentMetadata.video_meta_completed.is_(True),
    ).count()

    def _pct(n: int) -> float:
        return round(n / total * 100, 1) if total else 0.0

    return ServiceReadinessStats(
        total=total,
        text_completed=text_completed,
        image_completed=image_completed,
        video_completed=video_completed,
        all_completed=all_completed,
        text_rate=_pct(text_completed),
        image_rate=_pct(image_completed),
        video_rate=_pct(video_completed),
        all_rate=_pct(all_completed),
    )


# ── 이미지 추가 / 벌크 완료 ────────────────────────────────────────────────────

def add_content_image(
    db: Session,
    content_id: int,
    image_type: str,
    url: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    source: str = "manual",
) -> Optional[object]:
    """ContentImage 레코드 추가 후 5종 완료 여부 자동 갱신"""
    from api.programming.metadata.models import ContentImage, ImageType

    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        return None

    try:
        img_type = ImageType(image_type)
    except ValueError:
        raise ValueError(f"유효하지 않은 이미지 타입: {image_type}")

    img = ContentImage(
        content_id=content_id,
        image_type=img_type,
        url=url,
        width=width,
        height=height,
        source=source,
    )
    db.add(img)
    db.commit()
    update_image_completion(db, content_id)   # 5종 완료 자동 갱신
    return get_image_meta(db, content_id)


def bulk_complete_image_meta(db: Session, content_ids: list[int]) -> dict:
    """다중 콘텐츠 이미지메타 완료 처리"""
    updated = 0
    for cid in content_ids:
        content = db.query(Content).options(joinedload(Content.metadata_record)).filter(
            Content.id == cid
        ).first()
        if not content:
            continue
        meta = content.metadata_record
        if not meta:
            meta = ContentMetadata(content_id=cid)
            db.add(meta)
        meta.image_meta_completed = True
        updated += 1
    db.commit()
    return {"updated": updated}


# ── 글자메타 AI 제안 ────────────────────────────────────────────────────────────

def suggest_text_meta(db: Session, content_id: int):
    """TMDB/KOBIS 외부 소스 → 글자메타 제안. 없으면 기존 AI 결과 반환."""
    from api.programming.metadata.models import ExternalMetaSource, ExternalSourceType
    from api.programming.metadata.schemas import TextMetaSuggestion

    content = db.query(Content).options(
        joinedload(Content.metadata_record),
        joinedload(Content.external_sources),
    ).filter(Content.id == content_id).first()
    if not content:
        return None

    # TMDB 우선
    tmdb = next(
        (s for s in (content.external_sources or []) if s.source_type == ExternalSourceType.tmdb),
        None,
    )
    if tmdb and tmdb.raw_json:
        raw = tmdb.raw_json
        overview = raw.get("overview")
        genres = [g.get("name") for g in raw.get("genres", []) if g.get("name")]
        return TextMetaSuggestion(
            source="tmdb",
            synopsis=overview,
            genre_primary=genres[0] if genres else None,
            genre_secondary=genres[1] if len(genres) > 1 else None,
            mood_tags=None,
            rating_suggestion=None,
        )

    # KOBIS 차선
    kobis = next(
        (s for s in (content.external_sources or []) if s.source_type == ExternalSourceType.kobis),
        None,
    )
    if kobis and kobis.raw_json:
        raw = kobis.raw_json
        movie_info = raw.get("movieInfo", raw)
        return TextMetaSuggestion(
            source="kobis",
            synopsis=None,
            genre_primary=movie_info.get("genreAlt") or movie_info.get("genre"),
            genre_secondary=None,
            mood_tags=None,
            rating_suggestion=movie_info.get("watchGradeNm"),
        )

    # 기존 AI 결과 폴백
    meta = content.metadata_record
    if meta and (meta.ai_synopsis or meta.ai_genre_primary):
        return TextMetaSuggestion(
            source="ai",
            synopsis=meta.ai_synopsis,
            genre_primary=meta.ai_genre_primary,
            genre_secondary=meta.ai_genre_secondary,
            mood_tags=meta.ai_mood_tags,
            rating_suggestion=meta.ai_rating_suggestion,
        )

    return None


# ── 이미지메타 TMDB 제안 ─────────────────────────────────────────────────────────

def suggest_image_meta(db: Session, content_id: int):
    """TMDB 외부 소스에서 누락 이미지 타입별 URL 제안"""
    from api.programming.metadata.models import ExternalMetaSource, ExternalSourceType
    from api.programming.metadata.schemas import ImageMetaSuggestions, ImageSuggestion

    content = db.query(Content).options(
        joinedload(Content.images),
        joinedload(Content.external_sources),
    ).filter(Content.id == content_id).first()
    if not content:
        return None

    existing_types = {img.image_type.value for img in (content.images or [])}

    tmdb = next(
        (s for s in (content.external_sources or []) if s.source_type == ExternalSourceType.tmdb),
        None,
    )
    if not tmdb or not tmdb.raw_json:
        return ImageMetaSuggestions(content_id=content_id, suggestions=[])

    raw = tmdb.raw_json
    TMDB_W500 = "https://image.tmdb.org/t/p/w500"
    TMDB_W1280 = "https://image.tmdb.org/t/p/w1280"

    suggestions = []
    if "poster" not in existing_types and raw.get("poster_path"):
        suggestions.append(ImageSuggestion(
            source="tmdb", image_type="poster",
            url=f"{TMDB_W500}{raw['poster_path']}", width=500, height=750,
        ))
    backdrop = raw.get("backdrop_path")
    if backdrop:
        if "thumbnail" not in existing_types:
            suggestions.append(ImageSuggestion(
                source="tmdb", image_type="thumbnail",
                url=f"{TMDB_W1280}{backdrop}", width=1280, height=720,
            ))
        if "banner" not in existing_types:
            suggestions.append(ImageSuggestion(
                source="tmdb", image_type="banner",
                url=f"{TMDB_W1280}{backdrop}", width=2560, height=480,
            ))

    return ImageMetaSuggestions(content_id=content_id, suggestions=suggestions)


# ── TMDB 동기화 결과 목록 ───────────────────────────────────────────────────────

def list_tmdb_synced(
    db: Session,
    content_type: str | None = None,
    search: str | None = None,
    page: int = 1,
    size: int = 20,
):
    """TMDB ExternalMetaSource가 있는 최상위 콘텐츠 목록"""
    from api.programming.metadata.models import ExternalMetaSource, ExternalSourceType
    from api.programming.metadata.schemas import TmdbSyncedItem

    TMDB_IMG = "https://image.tmdb.org/t/p/w300"

    q = (
        db.query(Content, ExternalMetaSource, ContentMetadata)
        .join(
            ExternalMetaSource,
            (ExternalMetaSource.content_id == Content.id)
            & (ExternalMetaSource.source_type == ExternalSourceType.tmdb),
        )
        .outerjoin(ContentMetadata, ContentMetadata.content_id == Content.id)
        .filter(Content.parent_id.is_(None))
    )

    if content_type:
        q = q.filter(Content.content_type == content_type)
    if search:
        q = q.filter(Content.title.ilike(f"%{search}%"))

    total = q.count()
    rows = (
        q.order_by(ExternalMetaSource.matched_at.desc().nulls_last())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )

    items = []
    for content, ext, meta in rows:
        poster_path = ext.raw_json.get("poster_path") if ext.raw_json else None
        items.append(
            TmdbSyncedItem(
                content_id=content.id,
                title=content.title,
                original_title=content.original_title,
                content_type=content.content_type.value,
                status=content.status.value,
                production_year=content.production_year,
                cp_name=content.cp_name,
                tmdb_id=ext.external_id or "",
                poster_url=f"{TMDB_IMG}{poster_path}" if poster_path else None,
                match_confidence=ext.match_confidence,
                matched_at=ext.matched_at,
                quality_score=meta.quality_score if meta else None,
            )
        )

    return items, total
