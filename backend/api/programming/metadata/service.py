"""
Public service namespace — backward-compat re-exports + monkeypatch shim.

새 함수는 도메인별 service_<domain>.py에 추가하고 이 파일의 import 목록에 등록한다.

⚠️  service/ 패키지 디렉토리를 만들지 말 것 — Python의 패키지 우선 규칙으로
    service.py 전체가 무시되어 shadowing 사고가 발생한다 (530ddb5 사례).
    pre-commit guard (backend/scripts/check_no_module_package_shadowing.sh) 가 감지 차단한다.
"""

from datetime import datetime
from sqlalchemy.orm import Session, selectinload
from api.programming.metadata.models import Content, ContentStatus


# ── Content CRUD / Review Queue / Dashboard / Staging / Pipeline ──────────────
from api.programming.metadata.service_content import (
    create_content,
    update_content,
    get_content,
    _primary_poster_url,
    list_contents,
    get_review_queue,
    apply_review_action,
    get_dashboard_stats,
    trigger_ai_processing,
    trigger_enrichment,
    _build_diff,
    _content_to_staging_item,
    get_staging_queue,
    bulk_approve_staging,
    bulk_reject_staging,
    get_content_hierarchy,
    get_pipeline_status,
)

# ── 배치 업로드 ───────────────────────────────────────────────────────────────
from api.programming.metadata.service_batch_import import (
    create_batch_job,
    _process_movie_row,
    _process_series_rows,
    process_batch_rows,
)

# ── text/image/video meta + service readiness ─────────────────────────────────
from api.programming.metadata.service_meta import (
    _build_text_meta_out,
    _collect_all_descendants,
    get_text_meta_list,
    get_text_meta,
    update_text_meta,
    bulk_complete_text_meta,
    _propagate_text_completion,
    get_image_meta_list,
    get_image_meta,
    update_image_completion,
    get_video_meta_list,
    get_video_meta,
    update_video_meta,
    bulk_complete_video_meta,
    get_service_readiness,
    add_content_image,
    bulk_complete_image_meta,
    suggest_text_meta,
    suggest_image_meta,
)

# ── External mapping ──────────────────────────────────────────────────────────
from api.programming.metadata.service_external_mapping import (
    list_tmdb_synced,
    list_external_mapped_contents,
)

# ── External cache (TMDB/KMDB/KOBIS) ─────────────────────────────────────────
from api.programming.metadata.service_external_cache import (
    get_tmdb_cache_stats,
    list_tmdb_sync_log,
    list_tmdb_cache_recent,
    get_external_source_stats,
    list_external_source_sync_log,
    search_kmdb_cache,
    search_tmdb_cache,
    search_kobis_cache,
    search_external_sources,
)

# ── Bulk Actions / Job Lifecycle / Content Detail Simple Actions ───────────────
from api.programming.metadata.service_bulk import (
    bulk_reprocess,
    bulk_enrich,
    bulk_process,
    bulk_recall,
    _collect_descendant_ids,
    bulk_delete,
    get_job_status,
    bulk_undo,
    retry_failed_in_job,
    promote_ai_result,
    partial_reprocess,
    apply_external_fields,
)

# ── Sources (Advanced Actions + Add Flow) ─────────────────────────────────────
from api.programming.metadata.service_sources import (
    get_changelog,
    lock_fields,
    request_preview_clip,
    enrich_preview,
    batch_preview,
    sources_search,
    create_from_sources,
)

# ── Resolution Service + Recommendations ──────────────────────────────────────
from api.programming.metadata.service_recommendations import (
    _source_priority,
    _parse_source_fields,
    _get_or_create_genre,
    _get_or_create_person,
    resolve_metadata,
    _SOURCE_DEFAULT_CONFIDENCE,
    _CAST_ROLES,
    _DIRECTOR_ROLES,
    _STANDARD_RECOMMENDATION_FIELDS,
    _names_from_list,
    _extract_field_from_raw,
    get_content_recommendations,
    _classify_input_type,
    _classify_metadata_status,
    _classify_poster_status,
    _risk_level,
    _fetch_dam_count,
    _fetch_dam_counts,
    _enrich_tmdb_source,
    _enrich_kobis_source,
    enrich_external_credits,
)


# ── build_ai_review_queue: service.py에 직접 유지 (monkeypatch 호환) ────────────
# get_content_recommendations / _fetch_dam_counts를 service 네임스페이스에서 조회하므로
# patch("api.programming.metadata.service.get_content_recommendations") 가 동작한다.

def build_ai_review_queue(
    db: Session,
    *,
    status: str | None = None,
    input_type: str | None = None,
    metadata_status: str | None = None,
    poster_status: str | None = None,
    risk_level: str | None = None,
    include_dam: bool = False,
    page: int = 1,
    size: int = 50,
):
    from api.programming.metadata.schemas import (
        AiReviewQueueRow, AiReviewQueueSummary, PaginatedAiReviewQueue,
    )

    query = (
        db.query(Content)
        .options(
            selectinload(Content.images),
            selectinload(Content.external_sources),
        )
        .filter(Content.is_deleted == False)  # noqa: E712
    )
    if status:
        try:
            query = query.filter(Content.status == ContentStatus(status))
        except ValueError:
            pass

    contents = query.all()

    rows: list[AiReviewQueueRow] = []
    content_images_map: dict[int, list] = {}
    for content in contents:
        rec = get_content_recommendations(db, content.id)

        all_source_recs = [
            r
            for field in (rec.auto_fill + rec.conflicts)
            for r in field.recommendations
        ]
        confidence = (
            sum(r.confidence for r in all_source_recs) / len(all_source_recs)
            if all_source_recs
            else 1.0
        )

        it = _classify_input_type(content.external_sources)
        ms = _classify_metadata_status(rec)
        ps = _classify_poster_status(content.images, 0)
        rl = _risk_level(ms, ps, confidence)

        content_images_map[content.id] = list(content.images)
        rows.append(AiReviewQueueRow(
            content_id=content.id,
            title=content.title,
            content_type=content.content_type.value if content.content_type else "",
            input_type=it,
            content_status=content.status.value if content.status else "",
            metadata_status=ms,
            poster_status=ps,
            dam_match_count=0,
            risk_level=rl,
            confidence=round(confidence, 3),
            updated_at=content.updated_at or content.created_at or datetime.utcnow(),
        ))

    if input_type:
        rows = [r for r in rows if r.input_type == input_type]
    if metadata_status:
        rows = [r for r in rows if r.metadata_status == metadata_status]
    if poster_status:
        rows = [r for r in rows if r.poster_status == poster_status]
    if risk_level:
        rows = [r for r in rows if r.risk_level == risk_level]

    if include_dam and rows:
        dam_counts = _fetch_dam_counts([r.content_id for r in rows])
        updated = []
        for r in rows:
            dc = dam_counts.get(r.content_id, 0)
            ps = _classify_poster_status(content_images_map.get(r.content_id, []), dc)
            rl = _risk_level(r.metadata_status, ps, r.confidence)
            updated.append(r.model_copy(update={"dam_match_count": dc, "poster_status": ps, "risk_level": rl}))
        rows = updated

    summary = AiReviewQueueSummary(
        total=len(rows),
        missing=sum(1 for r in rows if r.metadata_status == "missing"),
        conflict=sum(1 for r in rows if r.metadata_status == "conflict"),
        needs_poster=sum(
            1 for r in rows
            if r.poster_status in {"needs_selection", "no_candidate", "external_only"}
        ),
        dam_match=sum(1 for r in rows if r.dam_match_count > 0),
        high_risk=sum(1 for r in rows if r.risk_level == "high"),
    )

    total = len(rows)
    start = (page - 1) * size
    return PaginatedAiReviewQueue(
        items=rows[start:start + size],
        summary=summary,
        total=total,
        page=page,
        size=size,
    )


__all__ = [
    # service_content
    "create_content", "update_content", "get_content", "list_contents",
    "get_review_queue", "apply_review_action", "get_dashboard_stats",
    "trigger_ai_processing", "trigger_enrichment",
    "get_staging_queue", "bulk_approve_staging", "bulk_reject_staging",
    "get_content_hierarchy", "get_pipeline_status",
    "_primary_poster_url", "_build_diff", "_content_to_staging_item",
    # service_batch_import
    "create_batch_job", "process_batch_rows",
    "_process_movie_row", "_process_series_rows",
    # service_meta
    "get_text_meta_list", "get_text_meta", "update_text_meta", "bulk_complete_text_meta",
    "get_image_meta_list", "get_image_meta", "update_image_completion",
    "get_video_meta_list", "get_video_meta", "update_video_meta", "bulk_complete_video_meta",
    "get_service_readiness", "add_content_image", "bulk_complete_image_meta",
    "suggest_text_meta", "suggest_image_meta",
    "_build_text_meta_out", "_collect_all_descendants", "_propagate_text_completion",
    # service_external_mapping
    "list_tmdb_synced", "list_external_mapped_contents",
    # service_external_cache
    "get_tmdb_cache_stats", "list_tmdb_sync_log", "list_tmdb_cache_recent",
    "get_external_source_stats", "list_external_source_sync_log",
    "search_kmdb_cache", "search_tmdb_cache", "search_kobis_cache", "search_external_sources",
    # service_bulk
    "bulk_reprocess", "bulk_enrich", "bulk_process", "bulk_recall", "bulk_delete",
    "get_job_status", "bulk_undo", "retry_failed_in_job",
    "promote_ai_result", "partial_reprocess", "apply_external_fields",
    "_collect_descendant_ids",
    # service_sources
    "get_changelog", "lock_fields", "request_preview_clip",
    "enrich_preview", "batch_preview", "sources_search", "create_from_sources",
    # service_recommendations
    "resolve_metadata", "get_content_recommendations", "enrich_external_credits",
    "_source_priority", "_parse_source_fields", "_get_or_create_genre", "_get_or_create_person",
    "_names_from_list", "_extract_field_from_raw",
    "_classify_input_type", "_classify_metadata_status", "_classify_poster_status",
    "_risk_level", "_fetch_dam_count", "_fetch_dam_counts",
    "_enrich_tmdb_source", "_enrich_kobis_source",
    "_SOURCE_DEFAULT_CONFIDENCE", "_CAST_ROLES", "_DIRECTOR_ROLES", "_STANDARD_RECOMMENDATION_FIELDS",
    # directly in this shim (monkeypatch 호환)
    "build_ai_review_queue",
]
