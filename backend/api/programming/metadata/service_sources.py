"""
Sources service — Content Add Flow / Advanced Actions (changelog, lock, preview, sources_search).

service.py 분할 과정에서 추출 (dev-service-module-split Step 3).
"""

from typing import Optional

from sqlalchemy.orm import Session

from api.programming.metadata.models import (
    Content, ContentMetadata, ContentBatchJob, ContentStatus,
    ExternalMetaSource,
)


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

        existing = db.query(Content).filter(
            Content.title == row.get("title")
        ).first()
        if existing:
            duplicates.add(row.get("title"))
            continue

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
        "valid": valid[:10],
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

    content = Content(
        title=external_source.title or "",
        cp_name=cp_name,
        status=ContentStatus.waiting,
    )
    db.add(content)
    db.flush()

    external_source.content_id = content.id
    db.add(external_source)

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
