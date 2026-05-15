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
from sqlalchemy.orm import Session, joinedload, selectinload

from api.programming.metadata.models import (
    Content, ContentMetadata, CpEmailLog, ContentBatchJob,
    ContentStatus, ContentType,
    ExternalMetaSource,
    ContentGenre, ContentCredit,
)
from api.programming.metadata.schemas import (
    ContentCreate, ContentUpdate, MetadataReviewAction, DashboardStats,
    StagingItem, BulkActionRequest, PipelineStatus,
    ExternalSourceOut,
)


# ── Content CRUD ──────────────────────────────────────────

def create_content(db: Session, data: ContentCreate) -> Content:
    content = Content(**data.model_dump())
    db.add(content)
    db.flush()
    meta = ContentMetadata(content_id=content.id, quality_score=0.0)
    db.add(meta)
    db.commit()
    db.refresh(content)
    return content


def update_content(db: Session, content_id: int, data: ContentUpdate) -> Content:
    """
    수동 수정 — 입력 필드를 manual source로 ExternalMetaSource에 저장 후 resolve_metadata 재실행.
    manual 우선순위(100)가 최고이므로 기존 tmdb/kobis 값보다 우선.
    """
    from api.programming.metadata.models.external import ExternalSourceType

    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise ValueError(f"Content {content_id} not found")

    raw_json = {k: v for k, v in data.model_dump().items() if v is not None}
    if raw_json:
        ext_src = ExternalMetaSource(
            content_id=content_id,
            source_type=ExternalSourceType.manual,
            raw_json=raw_json,
            matched_at=datetime.utcnow(),
        )
        db.add(ext_src)
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
    """파싱된 배치 행 → Content(waiting) + ExternalMetaSource(bulk_upload) → resolve_metadata"""
    from api.programming.metadata.models.external import ExternalSourceType
    from workers.tasks.metadata import process_content_metadata

    job.status = "processing"
    job.total_count = len(rows)
    db.flush()

    success = 0
    failed = 0
    errors = []

    for i, row in enumerate(rows):
        try:
            title = (row.get("title") or "").strip()
            if not title:
                raise ValueError("제목 없음")

            content = Content(
                title=title,
                content_type=ContentType(row.get("content_type") or "movie"),
                status=ContentStatus.waiting,
                cp_name=row.get("cp_name") or job.cp_name,
                production_year=row.get("production_year"),
            )
            db.add(content)
            db.flush()

            meta = ContentMetadata(content_id=content.id, quality_score=0.0)
            db.add(meta)
            db.flush()

            # 입력 데이터 전체를 external_meta_sources(bulk_upload)에 raw_json으로 저장
            raw_json = {k: v for k, v in {
                "title": title,
                "synopsis": row.get("synopsis") or row.get("cp_synopsis"),
                "cast": row.get("cast"),
                "directors": row.get("directors"),
                "genres": row.get("genres"),
                "country": row.get("country"),
                "runtime": row.get("runtime"),
                "rating_age": row.get("rating_age"),
                "poster_url": row.get("poster_url"),
                "production_year": row.get("production_year"),
            }.items() if v}

            ext_src = ExternalMetaSource(
                content_id=content.id,
                source_type=ExternalSourceType.bulk_upload,
                raw_json=raw_json,
                matched_at=datetime.utcnow(),
            )
            db.add(ext_src)
            db.flush()

            # resolution: credits/genres/이미지 분산 저장
            resolve_metadata(db, content.id)

            # 포스터 이미지 등록 (poster_url이 있으면)
            if row.get("poster_url"):
                add_content_image(db, content.id, "poster", row["poster_url"], source="cp")

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

    # 동일 (content_id, image_type, url) 이미 존재하면 skip (멱등)
    existing = db.query(ContentImage).filter(
        ContentImage.content_id == content_id,
        ContentImage.image_type == img_type,
        ContentImage.url == url,
    ).first()
    if existing:
        return get_image_meta(db, content_id)

    # 동일 타입의 기존 이미지가 없으면 is_primary=True
    has_same_type = db.query(ContentImage).filter(
        ContentImage.content_id == content_id,
        ContentImage.image_type == img_type,
    ).first()
    img = ContentImage(
        content_id=content_id,
        image_type=img_type,
        url=url,
        width=width,
        height=height,
        source=source,
        is_primary=(has_same_type is None),
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


# ── TMDB 캐시 모니터링 ─────────────────────────────────────────────────────────

def get_tmdb_cache_stats(db) -> dict:
    """tmdb_movie_cache / tmdb_tv_cache / tmdb_sync_log 기반 통계."""
    from datetime import datetime, timedelta
    from api.programming.metadata.models import (
        TmdbMovieCache, TmdbTvCache, TmdbPersonCache, TmdbSyncLog,
    )
    from sqlalchemy import func
    from collections import defaultdict

    now = datetime.utcnow()
    cutoff_24h = now - timedelta(hours=24)
    cutoff_7d = now - timedelta(days=7)

    total_movies = db.query(TmdbMovieCache).count()
    total_tv = db.query(TmdbTvCache).count()
    total_persons = db.query(TmdbPersonCache).count()

    last_24h_movies = db.query(TmdbMovieCache).filter(TmdbMovieCache.first_fetched_at >= cutoff_24h).count()
    last_24h_tv = db.query(TmdbTvCache).filter(TmdbTvCache.first_fetched_at >= cutoff_24h).count()
    last_24h_errors = (
        db.query(func.coalesce(func.sum(TmdbSyncLog.errors), 0))
        .filter(TmdbSyncLog.started_at >= cutoff_24h)
        .scalar() or 0
    )

    recent_logs = (
        db.query(TmdbSyncLog)
        .filter(TmdbSyncLog.started_at >= cutoff_7d)
        .all()
    )

    day_map: dict = defaultdict(lambda: {"movies": 0, "tv": 0, "errors": 0})
    for log in recent_logs:
        if log.started_at:
            day_str = log.started_at.strftime("%Y-%m-%d")
            is_movie = "movie" in str(log.source)
            day_map[day_str]["movies" if is_movie else "tv"] += log.items_inserted or 0
            day_map[day_str]["errors"] += log.errors or 0

    last_7d = [
        {"date": d, "movies": v["movies"], "tv": v["tv"], "errors": v["errors"]}
        for d, v in sorted(day_map.items())
    ]

    oldest = db.query(func.min(TmdbMovieCache.release_date)).scalar()
    newest = db.query(func.max(TmdbMovieCache.release_date)).scalar()

    last_log = db.query(TmdbSyncLog).order_by(TmdbSyncLog.started_at.desc()).first()

    return {
        "total_movies": total_movies,
        "total_tv": total_tv,
        "total_persons": total_persons,
        "last_24h_movies_added": last_24h_movies,
        "last_24h_tv_added": last_24h_tv,
        "last_24h_errors": int(last_24h_errors),
        "last_7d_daily": last_7d,
        "oldest_movie_year": oldest.year if oldest else None,
        "newest_movie_year": newest.year if newest else None,
        "last_run_at": last_log.started_at if last_log else None,
        "last_run_status": last_log.status.value if last_log else None,
    }


def list_tmdb_sync_log(db, source: str | None, status: str | None, page: int, size: int):
    from api.programming.metadata.models import TmdbSyncLog

    q = db.query(TmdbSyncLog)
    if source:
        q = q.filter(TmdbSyncLog.source == source)
    if status:
        q = q.filter(TmdbSyncLog.status == status)

    total = q.count()
    items = q.order_by(TmdbSyncLog.started_at.desc()).offset((page - 1) * size).limit(size).all()
    return items, total


def list_tmdb_cache_recent(db, kind: str, limit: int) -> list:
    from datetime import datetime
    from api.programming.metadata.models import TmdbMovieCache, TmdbTvCache
    from api.programming.metadata.tmdb_client import TmdbClient

    results = []
    if kind in ("movie", "both"):
        for r in db.query(TmdbMovieCache).order_by(TmdbMovieCache.last_fetched_at.desc()).limit(limit).all():
            results.append({
                "id": r.id, "title": r.title, "original_title": r.original_title,
                "release_date": r.release_date, "first_air_date": None,
                "popularity": r.popularity, "vote_average": r.vote_average,
                "poster_url": TmdbClient.poster_url(r.poster_path),
                "kind": "movie", "fetched_at": r.last_fetched_at,
            })
    if kind in ("tv", "both"):
        for r in db.query(TmdbTvCache).order_by(TmdbTvCache.last_fetched_at.desc()).limit(limit).all():
            results.append({
                "id": r.id, "title": r.name, "original_title": r.original_name,
                "release_date": None, "first_air_date": r.first_air_date,
                "popularity": r.popularity, "vote_average": r.vote_average,
                "poster_url": TmdbClient.poster_url(r.poster_path),
                "kind": "tv", "fetched_at": r.last_fetched_at,
            })
    results.sort(key=lambda x: x["fetched_at"] or datetime.min, reverse=True)
    return results[:limit]


# ── 외부 소스 (KOBIS / KMDB) ──────────────────────────────────────────────────

def get_external_source_stats(db, source_type: str) -> dict:
    """KOBIS 또는 KMDB 통계: external_meta_sources 건수 + sync_log 집계."""
    from datetime import datetime, timedelta
    from collections import defaultdict
    from api.programming.metadata.models import ExternalMetaSource, ExternalSourceType, TmdbSyncLog, TmdbSyncSource
    from sqlalchemy import func

    ext_type = ExternalSourceType(source_type)
    total = db.query(ExternalMetaSource).filter(ExternalMetaSource.source_type == ext_type).count()

    # KOBIS만 sync_log가 있음
    kobis_sources = [TmdbSyncSource.kobis_daily, TmdbSyncSource.kobis_backfill]
    if source_type == "kobis":
        sync_sources = kobis_sources
        last_log = (
            db.query(TmdbSyncLog)
            .filter(TmdbSyncLog.source.in_(sync_sources))
            .order_by(TmdbSyncLog.started_at.desc())
            .first()
        )
        cutoff_7d = datetime.utcnow() - timedelta(days=7)
        recent_logs = (
            db.query(TmdbSyncLog)
            .filter(TmdbSyncLog.source.in_(sync_sources), TmdbSyncLog.started_at >= cutoff_7d)
            .all()
        )
        day_map: dict = defaultdict(lambda: {"count": 0, "errors": 0})
        for log in recent_logs:
            if log.started_at:
                day_str = log.started_at.strftime("%Y-%m-%d")
                day_map[day_str]["count"] += log.items_inserted or 0
                day_map[day_str]["errors"] += log.errors or 0
        last_7d = [{"date": d, "count": v["count"], "errors": v["errors"]} for d, v in sorted(day_map.items())]
        return {
            "total_synced": total,
            "last_run_at": last_log.started_at if last_log else None,
            "last_run_status": last_log.status.value if last_log else None,
            "last_7d_daily": last_7d,
        }

    # KMDB: sync_log 없으므로 matched_at 기준
    last_matched = (
        db.query(func.max(ExternalMetaSource.matched_at))
        .filter(ExternalMetaSource.source_type == ext_type)
        .scalar()
    )
    return {
        "total_synced": total,
        "last_run_at": last_matched,
        "last_run_status": None,
        "last_7d_daily": [],
    }


def list_external_source_sync_log(db, source_type: str, status: str | None, page: int, size: int):
    """KOBIS sync 이력 (KMDB는 항상 빈 결과)."""
    from api.programming.metadata.models import TmdbSyncLog, TmdbSyncSource

    if source_type != "kobis":
        return [], 0

    q = db.query(TmdbSyncLog).filter(
        TmdbSyncLog.source.in_([TmdbSyncSource.kobis_daily, TmdbSyncSource.kobis_backfill])
    )
    if status:
        q = q.filter(TmdbSyncLog.status == status)

    total = q.count()
    items = q.order_by(TmdbSyncLog.started_at.desc()).offset((page - 1) * size).limit(size).all()
    return items, total


def search_external_sources(db, source_type: str, title: str | None, year: int | None, page: int, size: int):
    """external_meta_sources에서 소스별 검색."""
    from api.programming.metadata.models import ExternalMetaSource, ExternalSourceType

    ext_type = ExternalSourceType(source_type)
    q = db.query(ExternalMetaSource).filter(ExternalMetaSource.source_type == ext_type)

    if title:
        q = q.filter(ExternalMetaSource.title_on_source.ilike(f"%{title}%"))

    total = q.count()
    items = q.order_by(ExternalMetaSource.matched_at.desc()).offset((page - 1) * size).limit(size).all()
    return items, total


# ── dev-api-consolidation: Bulk Actions ──────────────────────

async def bulk_reprocess(
    db: Session,
    ids: list[int],
    reason: Optional[str] = None,
    sync_mode: bool = False,
) -> "JobStatusOut":
    """Bulk AI 재처리 — review/processing.error 상태만 처리"""
    from api.programming.metadata.schemas import JobStatusOut, BulkActionResponse
    from workers.metadata_tasks import process_bulk_reprocess

    # 1. IDs 로드 및 상태 필터링
    contents = db.query(Content).filter(Content.id.in_(ids)).all()
    content_map = {c.id: c for c in contents}

    valid_ids = [
        c.id for c in contents
        if c.status in [ContentStatus.review, ContentStatus.processing]
    ]
    invalid_ids = [id for id in ids if id not in {c.id for c in valid_ids}]

    # 2. ContentBatchJob 생성
    job = ContentBatchJob(
        job_name=f"bulk_reprocess_{len(valid_ids)}_items",
        status="pending",
        total_count=len(valid_ids),
        parse_mode="reprocess",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # 3. Task 큐잉 또는 동기 실행
    if sync_mode:
        # 각 content 재처리 (trigger_ai_processing 재사용)
        for content_id in valid_ids:
            trigger_ai_processing(content_id)
        job.status = "done"
        job.success_count = len(valid_ids)
    else:
        # Celery 큐잉
        process_bulk_reprocess.delay(job.id)

    db.add(job)
    db.commit()

    return JobStatusOut(
        id=job.id,
        status=job.status,
        action_type="bulk_reprocess",
        target_count=len(valid_ids),
        completed_count=job.success_count,
        failed_count=job.failed_count,
        progress_percent=0 if job.status == "pending" else 100,
        created_at=job.created_at,
        errors=[f"ID {id} 상태 부적합" for id in invalid_ids] if invalid_ids else None,
    )


async def bulk_enrich(
    db: Session,
    ids: list[int],
    reason: Optional[str] = None,
    sync_mode: bool = False,
) -> "JobStatusOut":
    """Bulk 외부 재매칭"""
    from api.programming.metadata.schemas import JobStatusOut
    from workers.metadata_tasks import process_bulk_enrich

    # 모든 상태 허용
    contents = db.query(Content).filter(Content.id.in_(ids)).all()
    valid_ids = [c.id for c in contents]
    invalid_ids = [id for id in ids if id not in {c.id for c in contents}]

    job = ContentBatchJob(
        job_name=f"bulk_enrich_{len(valid_ids)}_items",
        status="pending",
        total_count=len(valid_ids),
        parse_mode="enrich",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    if sync_mode:
        for content_id in valid_ids:
            trigger_enrichment(content_id)
        job.status = "done"
        job.success_count = len(valid_ids)
    else:
        process_bulk_enrich.delay(job.id)

    db.add(job)
    db.commit()

    return JobStatusOut(
        id=job.id,
        status=job.status,
        action_type="bulk_enrich",
        target_count=len(valid_ids),
        completed_count=job.success_count,
        failed_count=job.failed_count,
        progress_percent=0 if job.status == "pending" else 100,
        created_at=job.created_at,
        errors=[f"ID {id} 없음" for id in invalid_ids] if invalid_ids else None,
    )


async def bulk_process(
    db: Session,
    ids: list[int],
    reason: Optional[str] = None,
    sync_mode: bool = False,
) -> "JobStatusOut":
    """Bulk 즉시 처리 (status=processed)"""
    from api.programming.metadata.schemas import JobStatusOut

    contents = db.query(Content).filter(Content.id.in_(ids)).all()
    valid_ids = [c.id for c in contents]
    invalid_ids = [id for id in ids if id not in {c.id for c in contents}]

    # Update statuses
    for c in contents:
        c.status = ContentStatus.approved

    job = ContentBatchJob(
        job_name=f"bulk_process_{len(valid_ids)}_items",
        status="done",
        total_count=len(valid_ids),
        success_count=len(valid_ids),
        parse_mode="process",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return JobStatusOut(
        id=job.id,
        status="done",
        action_type="bulk_process",
        target_count=len(valid_ids),
        completed_count=len(valid_ids),
        failed_count=0,
        progress_percent=100,
        created_at=job.created_at,
        errors=[f"ID {id} 없음" for id in invalid_ids] if invalid_ids else None,
    )


async def bulk_recall(
    db: Session,
    ids: list[int],
    reason: Optional[str] = None,
    sync_mode: bool = False,
) -> "JobStatusOut":
    """Bulk 회수 — approved/rejected → review"""
    from api.programming.metadata.schemas import JobStatusOut

    contents = db.query(Content).filter(Content.id.in_(ids)).all()
    content_map = {c.id: c for c in contents}

    valid_contents = [
        c for c in contents
        if c.status in [ContentStatus.approved, ContentStatus.rejected]
    ]
    valid_ids = [c.id for c in valid_contents]
    invalid_ids = [id for id in ids if id not in {c.id for c in valid_contents}]

    # Update statuses
    for c in valid_contents:
        c.status = ContentStatus.review

    job = ContentBatchJob(
        job_name=f"bulk_recall_{len(valid_ids)}_items",
        status="done",
        total_count=len(valid_ids),
        success_count=len(valid_ids),
        parse_mode="recall",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return JobStatusOut(
        id=job.id,
        status="done",
        action_type="bulk_recall",
        target_count=len(valid_ids),
        completed_count=len(valid_ids),
        failed_count=0,
        progress_percent=100,
        created_at=job.created_at,
        errors=[f"ID {id} 상태 부적합" for id in invalid_ids] if invalid_ids else None,
    )


async def bulk_delete(
    db: Session,
    ids: list[int],
    reason: Optional[str] = None,
    sync_mode: bool = False,
) -> "JobStatusOut":
    """Bulk soft delete (is_deleted=True)"""
    from api.programming.metadata.schemas import JobStatusOut

    contents = db.query(Content).filter(Content.id.in_(ids)).all()
    valid_ids = [c.id for c in contents]
    invalid_ids = [id for id in ids if id not in {c.id for c in contents}]

    # Soft delete
    for c in contents:
        c.is_deleted = True

    job = ContentBatchJob(
        job_name=f"bulk_delete_{len(valid_ids)}_items",
        status="done",
        total_count=len(valid_ids),
        success_count=len(valid_ids),
        parse_mode="delete",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return JobStatusOut(
        id=job.id,
        status="done",
        action_type="bulk_delete",
        target_count=len(valid_ids),
        completed_count=len(valid_ids),
        failed_count=0,
        progress_percent=100,
        created_at=job.created_at,
        errors=[f"ID {id} 없음" for id in invalid_ids] if invalid_ids else None,
    )


# ── Job Lifecycle & Undo ──────────────────────────────────

async def get_job_status(db: Session, job_id: int) -> "JobStatusOut":
    """ContentBatchJob 상태 조회"""
    from api.programming.metadata.schemas import JobStatusOut
    
    job = db.query(ContentBatchJob).filter(ContentBatchJob.id == job_id).first()
    if not job:
        return None
    
    progress = 0
    if job.total_count > 0:
        progress = int((job.success_count + job.failed_count) / job.total_count * 100)
    
    return JobStatusOut(
        id=job.id,
        status=job.status,
        action_type=job.parse_mode or "unknown",
        target_count=job.total_count,
        completed_count=job.success_count,
        failed_count=job.failed_count,
        progress_percent=progress,
        created_at=job.created_at,
        started_at=job.created_at,
        completed_at=job.finished_at,
        errors=job.error_log,
    )


async def bulk_undo(db: Session, action_id: str) -> "UndoActionOut":
    """Bulk 액션 되돌리기 (24시간 이내)"""
    from api.programming.metadata.schemas import UndoActionOut
    from datetime import datetime, timedelta
    
    # 1. Action log 조회
    action_log = db.query(ContentActionLog).filter(ContentActionLog.action_id == action_id).first()
    if not action_log:
        return None
    
    # 2. 24시간 확인
    elapsed = datetime.utcnow() - action_log.executed_at.replace(tzinfo=None)
    if elapsed > timedelta(hours=24):
        return None  # 24시간 초과
    
    # 3. before_state 복원
    before_state = action_log.before_state or {}
    reverted_count = 0
    
    for content_id_str, state_dict in before_state.items():
        try:
            content_id = int(content_id_str)
            content = db.query(Content).filter(Content.id == content_id).first()
            if content and "status" in state_dict:
                content.status = state_dict["status"]
                reverted_count += 1
        except (ValueError, KeyError):
            pass
    
    # 4. reverted_at 기록
    action_log.reverted_at = datetime.utcnow()
    db.add(action_log)
    db.commit()
    
    # 복구된 content 중 첫 번째의 상태 반환
    first_state = next(iter(before_state.values())) if before_state else {}
    
    return UndoActionOut(
        id=action_log.action_id,
        status=first_state.get("status", "unknown"),
        reverted_count=reverted_count,
    )


async def retry_failed_in_job(db: Session, job_id: int) -> "BulkActionResponse":
    """Job의 실패 항목만 재실행"""
    from api.programming.metadata.schemas import BulkActionResponse
    import uuid
    
    # 1. 기존 job 조회
    orig_job = db.query(ContentBatchJob).filter(ContentBatchJob.id == job_id).first()
    if not orig_job or not orig_job.error_log:
        return None
    
    # 2. 실패한 content IDs 추출
    failed_ids = []
    for error_item in orig_job.error_log:
        if "content_id" in error_item:
            failed_ids.append(error_item["content_id"])
    
    if not failed_ids:
        return None
    
    # 3. 신규 job 생성
    new_job = ContentBatchJob(
        job_name=f"retry_failed_{len(failed_ids)}_items",
        status="pending",
        total_count=len(failed_ids),
        parse_mode="retry",
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    
    return BulkActionResponse(
        job_id=str(new_job.id),
        ids_accepted=len(failed_ids),
        ids_rejected=0,
        errors=None,
    )


# ── Content Detail — Simple Actions ──────────────────────

async def promote_ai_result(db: Session, content_id: int, ai_result_id: int) -> "PromoteAIResultOut":
    """AI 결과 채택 (is_final=True)"""
    from api.programming.metadata.schemas import PromoteAIResultOut
    from api.programming.metadata.models.external import ContentAIResult
    
    # 1. AI 결과 조회
    ai_result = db.query(ContentAIResult).filter(ContentAIResult.id == ai_result_id).first()
    if not ai_result:
        return None
    
    # 2. 기존 is_final 결과들 False로 설정
    db.query(ContentAIResult).filter(
        ContentAIResult.content_id == content_id,
        ContentAIResult.is_final == True,
    ).update({"is_final": False})
    
    # 3. 새 결과를 is_final=True로 설정
    ai_result.is_final = True
    db.add(ai_result)
    db.commit()
    db.refresh(ai_result)
    
    return PromoteAIResultOut(
        id=ai_result.id,
        is_final=True,
    )


async def partial_reprocess(
    db: Session,
    content_id: int,
    fields: list[str],
) -> "JobStatusOut":
    """특정 필드만 AI 재처리"""
    from api.programming.metadata.schemas import JobStatusOut
    
    # 화이트리스트 검증
    whitelist = {"synopsis", "genre", "tags", "cast", "director", "production_year"}
    valid_fields = [f for f in fields if f in whitelist]
    
    if not valid_fields:
        return None
    
    # Celery task 큐잉 (동기 실행은 생략)
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        return None
    
    job = ContentBatchJob(
        job_name=f"partial_reprocess_{content_id}_{','.join(valid_fields)}",
        status="pending",
        total_count=1,
        parse_mode="partial_reprocess",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    return JobStatusOut(
        id=job.id,
        status="pending",
        action_type="partial_reprocess",
        target_count=1,
        completed_count=0,
        failed_count=0,
        progress_percent=0,
        created_at=job.created_at,
    )


async def apply_external_fields(
    db: Session,
    content_id: int,
    source_id: int,
    fields: list[str],
) -> dict:
    """외부 소스 필드 선택 적용"""
    # 1. Content & ExternalMetaSource 조회
    content = db.query(Content).filter(Content.id == content_id).first()
    external = db.query(ExternalMetaSource).filter(ExternalMetaSource.id == source_id).first()
    
    if not content or not external:
        return None
    
    # 2. 필드 적용
    if external.body and isinstance(external.body, dict):
        ext_fields = external.body.get("fields", {})
        for field in fields:
            if field in ext_fields:
                # Content에 필드 적용 (간단한 예: synopsis)
                if field == "synopsis" and hasattr(content, "synopsis"):
                    setattr(content, field, ext_fields[field])
    
    db.add(content)
    db.commit()
    db.refresh(content)
    
    return {
        "content_id": content.id,
        "applied_fields": fields,
        "status": content.status,
    }


# ── Content Detail — Advanced Actions ──────────────────────

async def get_changelog(db: Session, content_id: int) -> "ContentChangelogOut":
    """변경 이력 조회"""
    from api.programming.metadata.schemas import ContentChangelogOut, ChangeLogItem
    from api.programming.metadata.models.external import ContentAuditLog
    
    logs = db.query(ContentAuditLog).filter(ContentAuditLog.content_id == content_id).order_by(ContentAuditLog.at.desc()).all()
    changes = [
        ChangeLogItem(
            field=log.field,
            old_value=log.old_value,
            new_value=log.new_value,
            changed_by=log.source,
            changed_at=log.at,
        )
        for log in logs
    ]
    return ContentChangelogOut(changes=changes)


async def lock_fields(db: Session, content_id: int, fields: list[str], reason: Optional[str] = None) -> dict:
    """필드 잠금"""
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        return None
    
    # locked_fields 업데이트
    locked = content.locked_fields or []
    locked = list(set(locked + fields))
    content.locked_fields = locked
    
    db.add(content)
    db.commit()
    db.refresh(content)
    
    return {
        "content_id": content.id,
        "locked_fields": content.locked_fields,
        "reason": reason,
    }


async def request_preview_clip(db: Session, content_id: int) -> dict:
    """Preview clip 생성 요청 (stub)"""
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        return None
    
    # Celery task 큐잉 (stub)
    job = ContentBatchJob(
        job_name=f"preview_clip_{content_id}",
        status="pending",
        total_count=1,
        parse_mode="preview_clip",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    return {
        "job_id": job.id,
        "status": "queued",
        "content_id": content_id,
    }


# ── Content Add Flow ──────────────────────────────────────────


async def enrich_preview(
    db: Session, content_id: int, fields: Optional[list[str]] = None
) -> dict:
    """
    Content {content_id}를 외부 소스와 매칭 (dry-run).
    DB 변경 없음. enriched_fields + external_sources 반환.
    """
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        return {"error": f"Content {content_id} not found"}

    # 기존 외부 소스 조회
    external_sources = db.query(ExternalMetaSource).filter(
        ExternalMetaSource.content_id == content_id
    ).all()

    return {
        "content_id": content_id,
        "title": content.title,
        "enriched_fields": fields or ["synopsis", "genre", "tags"],
        "external_sources": [
            {
                "id": s.id,
                "source": s.source,
                "title": s.title,
                "data": s.body,
            }
            for s in external_sources
        ],
        "preview_mode": True,
    }


async def batch_preview(
    db: Session, csv_data: list[dict]
) -> dict:
    """
    CSV dry-run. 유효성 검사만 수행.
    valid_count, missing_count, error_count, duplicate_count 반환.
    """
    if not csv_data:
        return {
            "total": 0,
            "valid": [],
            "missing": [],
            "errors": [],
            "duplicates": [],
            "preview_mode": True,
        }

    valid = []
    missing = []
    errors = []
    duplicates = set()

    for idx, row in enumerate(csv_data, 1):
        if not row.get("title"):
            missing.append({"row": idx, "reason": "title 필수"})
            continue

        # 중복 검사
        existing = db.query(Content).filter(
            Content.title == row.get("title")
        ).first()
        if existing:
            duplicates.add(row.get("title"))
            continue

        # 유효성 검사
        if len(row.get("title", "")) > 500:
            errors.append({"row": idx, "reason": "title 길이 초과 (500자)"})
            continue

        valid.append({"row": idx, "title": row.get("title")})

    return {
        "total": len(csv_data),
        "valid_count": len(valid),
        "missing_count": len(missing),
        "error_count": len(errors),
        "duplicate_count": len(duplicates),
        "valid": valid[:10],  # 처음 10개만
        "missing": missing[:10],
        "errors": errors[:10],
        "duplicates": list(duplicates)[:10],
        "preview_mode": True,
    }


async def sources_search(
    db: Session, query: str, sources: Optional[list[str]] = None
) -> dict:
    """SourcesAggregator 사용해서 병렬 검색."""
    from api.programming.metadata.sources_aggregator import SourcesAggregator

    aggregator = SourcesAggregator()
    result = await aggregator.search(query, sources)

    return {
        "query": query,
        "sources": sources or ["tmdb", "kobis"],
        "results": result.get("results", []),
        "errors": result.get("errors"),
    }


async def create_from_sources(
    db: Session,
    source_id: int,
    selected_fields: list[str],
    cp_name: str,
) -> dict:
    """
    ExternalMetaSource {source_id}에서 Content 생성.
    Content + ExternalMetaSource를 한번에 생성 (atomic).
    """
    external_source = db.query(ExternalMetaSource).filter(
        ExternalMetaSource.id == source_id
    ).first()
    if not external_source:
        return {"error": f"ExternalMetaSource {source_id} not found"}

    # 새 Content 생성
    content = Content(
        title=external_source.title or "",
        cp_name=cp_name,
        status=ContentStatus.waiting,
    )
    db.add(content)
    db.flush()  # ID 획득

    # ExternalMetaSource의 content_id 업데이트
    external_source.content_id = content.id
    db.add(external_source)

    # ContentMetadata 초기화
    metadata = ContentMetadata(content_id=content.id, quality_score=0.0)
    db.add(metadata)

    db.commit()
    db.refresh(content)

    return {
        "content_id": content.id,
        "title": content.title,
        "source_id": source_id,
        "status": content.status.value,
        "created_at": content.created_at.isoformat() if content.created_at else None,
    }


# ── Resolution Service ─────────────────────────────────────

def _source_priority(source_type: str) -> int:
    """소스 우선순위 (높을수록 우선)"""
    return {
        "manual": 100,
        "tmdb": 80,
        "kobis": 70,
        "kmdb": 60,
        "watcha": 50,
        "naver": 40,
        "daum": 30,
        "netflix": 20,
        "bulk_upload": 15,
        "ai": 10,
        "other": 5,
    }.get(source_type, 0)


def _parse_source_fields(source_type: str, raw_json: dict) -> dict:
    """소스별 raw_json에서 표준 필드 추출"""
    fields: dict = {}

    if source_type == "tmdb":
        if raw_json.get("title"):
            fields["title"] = raw_json["title"]
        if raw_json.get("original_title"):
            fields["original_title"] = raw_json["original_title"]
        if raw_json.get("overview"):
            fields["synopsis"] = raw_json["overview"]
        if raw_json.get("genres"):
            fields["genres"] = [g["name"] for g in raw_json["genres"] if g.get("name")]
        credits = raw_json.get("credits", {})
        if credits.get("cast"):
            fields["cast"] = [
                {"name": p["name"], "character": p.get("character", "")}
                for p in credits["cast"][:15]
                if p.get("name")
            ]
        if credits.get("crew"):
            fields["directors"] = [
                p["name"] for p in credits["crew"]
                if p.get("job") == "Director" and p.get("name")
            ]
        if raw_json.get("production_countries"):
            countries = [c["name"] for c in raw_json["production_countries"] if c.get("name")]
            if countries:
                fields["country"] = countries[0]
        if raw_json.get("runtime"):
            fields["runtime"] = int(raw_json["runtime"])
        release = raw_json.get("release_date", "")
        if release and len(release) >= 4 and release[:4].isdigit():
            fields["production_year"] = int(release[:4])

    elif source_type == "kobis":
        movie_info = raw_json.get("movieInfoResult", {}).get("movieInfo", raw_json)
        if movie_info.get("movieNm"):
            fields["title"] = movie_info["movieNm"]
        if movie_info.get("showTm"):
            try:
                fields["runtime"] = int(movie_info["showTm"])
            except (ValueError, TypeError):
                pass
        nations = [n.get("nationNm") for n in movie_info.get("nations", []) if n.get("nationNm")]
        if nations:
            fields["country"] = nations[0]
        genres = [g.get("genreNm") for g in movie_info.get("genres", []) if g.get("genreNm")]
        if genres:
            fields["genres"] = genres
        directors = [d.get("peopleNm") for d in movie_info.get("directors", []) if d.get("peopleNm")]
        if directors:
            fields["directors"] = directors
        actors = [
            {"name": a.get("peopleNm"), "character": a.get("cast", "")}
            for a in movie_info.get("actors", [])[:15]
            if a.get("peopleNm")
        ]
        if actors:
            fields["cast"] = actors
        if movie_info.get("prdtYear"):
            try:
                fields["production_year"] = int(movie_info["prdtYear"])
            except (ValueError, TypeError):
                pass

    else:
        # watcha / bulk_upload / manual / other 등 — raw_json 직접 매핑
        for key in ["title", "synopsis", "country", "rating_age", "poster_url", "original_title"]:
            if raw_json.get(key):
                fields[key] = raw_json[key]

        if raw_json.get("production_year"):
            try:
                fields["production_year"] = int(raw_json["production_year"])
            except (ValueError, TypeError):
                pass

        if raw_json.get("runtime"):
            runtime_raw = raw_json["runtime"]
            if isinstance(runtime_raw, (int, float)):
                fields["runtime"] = int(runtime_raw)
            elif isinstance(runtime_raw, str):
                cleaned = runtime_raw.replace("분", "").strip()
                if cleaned.isdigit():
                    fields["runtime"] = int(cleaned)

        cast_raw = raw_json.get("cast")
        if cast_raw:
            if isinstance(cast_raw, list):
                fields["cast"] = [
                    {"name": c["name"] if isinstance(c, dict) else c,
                     "character": c.get("character", "") if isinstance(c, dict) else ""}
                    for c in cast_raw if c
                ]
            elif isinstance(cast_raw, str):
                fields["cast"] = [{"name": n.strip(), "character": ""} for n in cast_raw.split(",") if n.strip()]

        dirs_raw = raw_json.get("directors")
        if dirs_raw:
            if isinstance(dirs_raw, list):
                fields["directors"] = [d if isinstance(d, str) else d.get("name", "") for d in dirs_raw if d]
            elif isinstance(dirs_raw, str):
                fields["directors"] = [n.strip() for n in dirs_raw.split(",") if n.strip()]

        genres_raw = raw_json.get("genres")
        if genres_raw:
            if isinstance(genres_raw, list):
                fields["genres"] = [g if isinstance(g, str) else g.get("name", "") for g in genres_raw if g]
            elif isinstance(genres_raw, str):
                fields["genres"] = [n.strip().rstrip("/") for n in genres_raw.split(",") if n.strip().strip("/")]

    return {k: v for k, v in fields.items() if v is not None and v != "" and v != []}


def _get_or_create_genre(db: Session, genre_name: str, source: str = "ai") -> Optional[object]:
    """장르명으로 GenreCode 조회 또는 생성"""
    from api.programming.metadata.models.taxonomy import GenreCode

    if not genre_name or not genre_name.strip():
        return None
    genre_name = genre_name.strip()

    existing = db.query(GenreCode).filter(GenreCode.name_ko == genre_name).first()
    if existing:
        return existing

    base_code = "GN_" + "".join(c for c in genre_name if c.isalnum())[:8].upper()
    code = base_code
    if db.query(GenreCode).filter(GenreCode.code == code).first():
        total = db.query(GenreCode).count()
        code = f"{base_code}_{total % 1000}"

    new_genre = GenreCode(code=code, name_ko=genre_name, is_active=True)
    db.add(new_genre)
    db.flush()
    return new_genre


def _get_or_create_person(db: Session, name_ko: str) -> Optional[object]:
    """인물명으로 PersonMaster 조회 또는 생성"""
    from api.programming.metadata.models.person import PersonMaster

    if not name_ko or not name_ko.strip():
        return None
    name_ko = name_ko.strip()

    existing = db.query(PersonMaster).filter(PersonMaster.name_ko == name_ko).first()
    if existing:
        return existing

    new_person = PersonMaster(name_ko=name_ko)
    db.add(new_person)
    db.flush()
    return new_person


def resolve_metadata(db: Session, content_id: int) -> dict:
    """
    content_id의 external_meta_sources를 우선순위 병합해
    Content, ContentMetadata, ContentCredits, ContentGenres에 적용.

    우선순위: manual(100) > tmdb(80) > kobis(70) > watcha(50) > bulk_upload(15) > ai(10)
    멱등: 여러 번 호출해도 같은 결과 (기존 credits/genres는 중복 추가 방지).
    """
    from api.programming.metadata.models.taxonomy import ContentGenre
    from api.programming.metadata.models.person import ContentCredit, CreditRole

    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        return {"error": f"Content {content_id} not found"}

    sources = db.query(ExternalMetaSource).filter(ExternalMetaSource.content_id == content_id).all()
    if not sources:
        return {"status": "no_sources", "content_id": content_id}

    # 필드별 winner 결정
    winner: dict[str, dict] = {}
    for src in sources:
        src_name = src.source_type.value if hasattr(src.source_type, "value") else str(src.source_type)
        priority = _source_priority(src_name)
        try:
            fields = _parse_source_fields(src_name, src.raw_json or {})
        except Exception:
            continue
        for field, value in fields.items():
            if field not in winner or winner[field]["priority"] < priority:
                winner[field] = {"value": value, "source": src_name, "priority": priority}

    if not winner:
        return {"status": "no_fields_extracted", "content_id": content_id}

    locked = set(content.locked_fields or [])

    # Content 기본 필드 업데이트 (locked 필드는 건너뜀)
    for field, col_attr in [
        ("title", "title"),
        ("original_title", "original_title"),
        ("country", "country"),
    ]:
        if field in winner and field not in locked:
            current = getattr(content, col_attr, None)
            if not current:
                setattr(content, col_attr, winner[field]["value"])

    if "production_year" in winner and "production_year" not in locked and not content.production_year:
        content.production_year = winner["production_year"]["value"]

    if "runtime" in winner and "runtime" not in locked and not content.runtime_minutes:
        content.runtime_minutes = winner["runtime"]["value"]

    db.add(content)

    # ContentMetadata 업데이트
    meta = content.metadata_record
    if meta:
        if "synopsis" in winner and "synopsis" not in locked and not meta.final_synopsis:
            src_name = winner["synopsis"]["source"]
            if src_name in ("manual", "cp", "bulk_upload"):
                meta.cp_synopsis = winner["synopsis"]["value"]
            else:
                meta.ai_synopsis = winner["synopsis"]["value"]

        meta.score_breakdown = {
            f: {"source": info["source"], "confidence": round(info["priority"] / 100, 2)}
            for f, info in winner.items()
        }
        db.add(meta)

    # ContentGenre 저장 (중복 방지)
    if "genres" in winner:
        genre_list = winner["genres"]["value"] or []
        src_name = winner["genres"]["source"]
        existing_genre_ids = {cg.genre_id for cg in (content.genres or [])}
        for i, genre_name in enumerate(genre_list):
            genre = _get_or_create_genre(db, genre_name, src_name)
            if genre and genre.id not in existing_genre_ids:
                db.add(ContentGenre(
                    content_id=content_id,
                    genre_id=genre.id,
                    is_primary=(i == 0),
                    source=src_name,
                ))
                existing_genre_ids.add(genre.id)

    # ContentCredit 저장 (중복 방지 — person_id 기준)
    existing_person_ids = {cc.person_id for cc in (content.credits or [])}

    if "directors" in winner:
        src_name = winner["directors"]["source"]
        for name in (winner["directors"]["value"] or []):
            person = _get_or_create_person(db, name)
            if person and person.id not in existing_person_ids:
                db.add(ContentCredit(
                    content_id=content_id,
                    person_id=person.id,
                    role=CreditRole.director,
                    source=src_name,
                ))
                existing_person_ids.add(person.id)

    if "cast" in winner:
        src_name = winner["cast"]["source"]
        for i, item in enumerate(winner["cast"]["value"] or []):
            name = item.get("name") if isinstance(item, dict) else item
            character = item.get("character", "") if isinstance(item, dict) else ""
            person = _get_or_create_person(db, name)
            if person and person.id not in existing_person_ids:
                db.add(ContentCredit(
                    content_id=content_id,
                    person_id=person.id,
                    role=CreditRole.actor,
                    character_name=character or None,
                    cast_order=i + 1,
                    source=src_name,
                ))
                existing_person_ids.add(person.id)

    db.flush()

    return {
        "status": "resolved",
        "content_id": content_id,
        "filled_fields": list(winner.keys()),
        "source_breakdown": {f: info["source"] for f, info in winner.items()},
    }
