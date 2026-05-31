"""
Bulk Actions / Job Lifecycle / Content Detail Simple Actions service.

service.py 분할 과정에서 추출 (dev-service-module-split Step 6).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from api.programming.metadata.models import (
    Content, ContentBatchJob, ContentActionLog,
    ContentStatus, ExternalMetaSource,
)


# ── Bulk Actions ──────────────────────────────────────────

async def bulk_reprocess(
    db: Session,
    ids: list[int],
    reason: Optional[str] = None,
    sync_mode: bool = False,
) -> "BulkActionResponse":
    """Bulk AI 재처리 — review/processing.error 상태만 처리"""
    from api.programming.metadata.schemas import JobStatusOut, BulkActionResponse
    from api.programming.metadata.service_content import trigger_ai_processing
    from workers.metadata_tasks import process_bulk_reprocess

    contents = db.query(Content).filter(Content.id.in_(ids)).all()
    content_map = {c.id: c for c in contents}

    valid_ids = [
        c.id for c in contents
        if c.status in [ContentStatus.review, ContentStatus.enriched]
    ]
    invalid_ids = [id for id in ids if id not in {c.id for c in valid_ids}]

    job = ContentBatchJob(
        job_name=f"bulk_reprocess_{len(valid_ids)}_items",
        status="pending",
        total_count=len(valid_ids),
        parse_mode="reprocess",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    if sync_mode:
        for content_id in valid_ids:
            trigger_ai_processing(content_id)
        job.status = "done"
        job.success_count = len(valid_ids)
    else:
        process_bulk_reprocess.delay(job.id)

    db.add(job)
    db.commit()

    return BulkActionResponse(
        job_id=str(job.id),
        ids_accepted=len(valid_ids),
        ids_rejected=len(invalid_ids),
        errors=[f"ID {id} 상태 부적합" for id in invalid_ids] if invalid_ids else None,
    )


async def bulk_enrich(
    db: Session,
    ids: list[int],
    reason: Optional[str] = None,
    sync_mode: bool = False,
) -> "BulkActionResponse":
    """Bulk 외부 재매칭"""
    from api.programming.metadata.schemas import BulkActionResponse
    from api.programming.metadata.service_content import trigger_enrichment
    from workers.tasks.metadata import enrich_content_metadata

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
        for content_id in valid_ids:
            enrich_content_metadata.delay(content_id)

    db.add(job)
    db.commit()

    return BulkActionResponse(
        job_id=str(job.id),
        ids_accepted=len(valid_ids),
        ids_rejected=len(invalid_ids),
        errors=[f"ID {id} 없음" for id in invalid_ids] if invalid_ids else None,
    )


async def bulk_process(
    db: Session,
    ids: list[int],
    reason: Optional[str] = None,
    sync_mode: bool = False,
) -> "BulkActionResponse":
    """Bulk AI 처리 큐 등록 (raw/enriched 상태 콘텐츠 → AI 처리 태스크 디스패치)"""
    from api.programming.metadata.schemas import BulkActionResponse
    from api.programming.metadata.service_content import trigger_ai_processing

    contents = db.query(Content).filter(Content.id.in_(ids)).all()
    valid_ids = [c.id for c in contents]
    invalid_ids = [id for id in ids if id not in {c.id for c in contents}]

    job = ContentBatchJob(
        job_name=f"bulk_process_{len(valid_ids)}_items",
        status="pending",
        total_count=len(valid_ids),
        parse_mode="process",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    if sync_mode:
        for content_id in valid_ids:
            trigger_ai_processing(content_id)
        job.status = "done"
        job.success_count = len(valid_ids)
    else:
        from workers.tasks.metadata import process_content_metadata
        for content_id in valid_ids:
            process_content_metadata.delay(content_id, False)  # auto_chain=False: enriched→ai only

    db.commit()

    return BulkActionResponse(
        job_id=str(job.id),
        ids_accepted=len(valid_ids),
        ids_rejected=len(invalid_ids),
        errors=[f"ID {id} 없음" for id in invalid_ids] if invalid_ids else None,
    )


async def bulk_recall(
    db: Session,
    ids: list[int],
    reason: Optional[str] = None,
    sync_mode: bool = False,
) -> "BulkActionResponse":
    """Bulk 회수 — approved/rejected → review"""
    from api.programming.metadata.schemas import BulkActionResponse

    contents = db.query(Content).filter(Content.id.in_(ids)).all()
    content_map = {c.id: c for c in contents}

    valid_contents = [
        c for c in contents
        if c.status in [ContentStatus.approved, ContentStatus.rejected]
    ]
    valid_ids = [c.id for c in valid_contents]
    invalid_ids = [id for id in ids if id not in {c.id for c in valid_contents}]

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

    return BulkActionResponse(
        job_id=str(job.id),
        ids_accepted=len(valid_ids),
        ids_rejected=len(invalid_ids),
        errors=[f"ID {id} 상태 부적합" for id in invalid_ids] if invalid_ids else None,
    )


def _collect_descendant_ids(db: Session, root_ids: list[int]) -> list[int]:
    """BFS로 root_ids의 모든 자손 Content id 수집 (root 포함)."""
    seen: set[int] = set(root_ids)
    queue: list[int] = list(root_ids)
    while queue:
        children = (
            db.query(Content.id)
            .filter(Content.parent_id.in_(queue))
            .all()
        )
        next_ids = [row[0] for row in children if row[0] not in seen]
        seen.update(next_ids)
        queue = next_ids
    return list(seen)


async def bulk_delete(
    db: Session,
    ids: list[int],
    reason: Optional[str] = None,
    sync_mode: bool = False,
) -> "BulkActionResponse":
    """Bulk soft delete (is_deleted=True) — 자손 season/episode cascade 전파."""
    from api.programming.metadata.schemas import BulkActionResponse

    contents = db.query(Content).filter(Content.id.in_(ids)).all()
    valid_ids = [c.id for c in contents]
    invalid_ids = [id for id in ids if id not in {c.id for c in contents}]

    all_ids = _collect_descendant_ids(db, valid_ids)
    db.query(Content).filter(Content.id.in_(all_ids)).update(
        {"is_deleted": True}, synchronize_session=False
    )

    db.commit()

    return BulkActionResponse(
        job_id="0",
        ids_accepted=len(valid_ids),
        ids_rejected=len(invalid_ids),
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
    from datetime import timedelta

    action_log = db.query(ContentActionLog).filter(ContentActionLog.action_id == action_id).first()
    if not action_log:
        return None

    elapsed = datetime.utcnow() - action_log.executed_at.replace(tzinfo=None)
    if elapsed > timedelta(hours=24):
        return None

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

    action_log.reverted_at = datetime.utcnow()
    db.add(action_log)
    db.commit()

    first_state = next(iter(before_state.values())) if before_state else {}

    return UndoActionOut(
        id=action_log.action_id,
        status=first_state.get("status", "unknown"),
        reverted_count=reverted_count,
    )


async def retry_failed_in_job(db: Session, job_id: int) -> "BulkActionResponse":
    """Job의 실패 항목만 재실행"""
    from api.programming.metadata.schemas import BulkActionResponse

    orig_job = db.query(ContentBatchJob).filter(ContentBatchJob.id == job_id).first()
    if not orig_job or not orig_job.error_log:
        return None

    failed_ids = []
    for error_item in orig_job.error_log:
        if "content_id" in error_item:
            failed_ids.append(error_item["content_id"])

    if not failed_ids:
        return None

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

    ai_result = db.query(ContentAIResult).filter(ContentAIResult.id == ai_result_id).first()
    if not ai_result:
        return None

    db.query(ContentAIResult).filter(
        ContentAIResult.content_id == content_id,
        ContentAIResult.is_final == True,
    ).update({"is_final": False})

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

    whitelist = {"synopsis", "genre", "tags", "cast", "director", "production_year"}
    valid_fields = [f for f in fields if f in whitelist]

    if not valid_fields:
        return None

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
    """외부 소스의 선택 필드를 manual source에 머지 후 resolve_metadata 호출.
    사용자가 명시적으로 선택한 값이므로 manual priority(100)로 적용.
    _extract_field_from_raw로 raw_json의 다양한 키(directors/director, overview/synopsis 등) 정규화."""
    from api.programming.metadata.models.external import ExternalSourceType
    from api.programming.metadata.models.person import ContentCredit, CreditRole
    from api.programming.metadata.models.taxonomy import ContentGenre
    from api.programming.metadata.service_recommendations import resolve_metadata, _extract_field_from_raw

    content = db.query(Content).filter(Content.id == content_id).first()
    external = db.query(ExternalMetaSource).filter(ExternalMetaSource.id == source_id).first()

    if not content or not external:
        raise ValueError("Content or ExternalMetaSource not found")

    raw = external.raw_json or {}

    _field_alias = {"director": "directors"}

    extracted: dict = {}
    applied: list[str] = []
    not_found: list[str] = []

    for field in fields:
        val = _extract_field_from_raw(raw, field)
        if val is None:
            not_found.append(field)
            continue

        if field in ("runtime", "production_year"):
            try:
                val = int(val)
            except (ValueError, TypeError):
                not_found.append(field)
                continue

        if field == "cp_name":
            content.cp_name = val
            db.add(content)
            applied.append(field)
            continue

        key = _field_alias.get(field, field)
        extracted[key] = val
        applied.append(field)

    if extracted:
        if "directors" in extracted or "cast" in extracted:
            existing_credits = db.query(ContentCredit).filter(
                ContentCredit.content_id == content_id,
                ContentCredit.source == "manual"
            ).all()
            for cc in existing_credits:
                if ("directors" in extracted and cc.role == CreditRole.director) or \
                   ("cast" in extracted and cc.role == CreditRole.actor):
                    db.delete(cc)

        if "genres" in extracted:
            existing_genres = db.query(ContentGenre).filter(
                ContentGenre.content_id == content_id,
                ContentGenre.source == "manual"
            ).all()
            for cg in existing_genres:
                db.delete(cg)

        manual_src = db.query(ExternalMetaSource).filter(
            ExternalMetaSource.content_id == content_id,
            ExternalMetaSource.source_type == ExternalSourceType.manual
        ).first()
        if manual_src:
            manual_src.raw_json = {**(manual_src.raw_json or {}), **extracted}
            manual_src.matched_at = datetime.utcnow()
        else:
            manual_src = ExternalMetaSource(
                content_id=content_id,
                source_type=ExternalSourceType.manual,
                raw_json=extracted,
                matched_at=datetime.utcnow(),
            )
            db.add(manual_src)
        db.flush()
        resolve_metadata(db, content_id)

    db.commit()
    db.refresh(content)

    return {
        "content_id": content.id,
        "applied_fields": applied,
        "not_found_fields": not_found,
        "source_id": source_id,
        "source_type": external.source_type.value if hasattr(external.source_type, "value") else str(external.source_type),
    }


def get_enrich_policy(db):
    """현재 EnrichPolicy 반환. 없으면 기본값 dict."""
    from api.programming.metadata.models.external import EnrichPolicy
    row = db.query(EnrichPolicy).filter(EnrichPolicy.id == 1).first()
    if not row:
        return {"use_cache_db": False, "confidence_threshold": 0.90, "use_websearch": False}
    return {
        "use_cache_db": row.use_cache_db,
        "confidence_threshold": row.confidence_threshold,
        "use_websearch": row.use_websearch,
    }


def get_stage_auto_policy(db) -> dict:
    """현재 StageAutoPolicy 반환. 없으면 전부 False dict (자동 전이 없음)."""
    from api.programming.metadata.models.external import StageAutoPolicy
    row = db.query(StageAutoPolicy).filter(StageAutoPolicy.id == 1).first()
    if not row:
        return {f"s{i}_auto": False for i in range(1, 7)}
    return {f"s{i}_auto": getattr(row, f"s{i}_auto") for i in range(1, 7)}
