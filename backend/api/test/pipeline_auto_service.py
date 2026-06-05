"""파이프라인 AUTO 워커 서비스 — ADR-010.

엔드포인트와 Celery 태스크 양쪽에서 호출되는 순수 비즈니스 로직.
- claim_bucket: FOR UPDATE SKIP LOCKED + auto_hold 필터 + visibility_timeout 재claim
- advance_one / approve_one: 멱등 전이 (txn 내 선조건 재확인, 실제 전이만 StageEvent)
- enrich_autofill_one / ai_autofill_one: status 불변 autofill (sync, asyncio.run 래핑)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import TypedDict

from sqlalchemy.orm import Session

from api.programming.metadata.models.content import (
    Content, ContentStatus, PipelineStage, StageEventType,
)
from api.programming.metadata.models.stage_event import StageEvent  # noqa: F401 — ensure model loaded

logger = logging.getLogger(__name__)

# ── 공유 상수 ─────────────────────────────────────────────────────────────────

_STAGE_BUCKET: dict[str, int] = {
    PipelineStage.S1_INTAKE.value:         1,
    PipelineStage.S2_NORMALIZE.value:      2,
    PipelineStage.S3_SOURCE_MATCH.value:   2,
    PipelineStage.S4_GAP_DETECT.value:     2,
    PipelineStage.S5_WEBSEARCH_FILL.value: 2,
    PipelineStage.S6_LLM_EXTRACT.value:    3,
    PipelineStage.S7_STAGING.value:        3,
    PipelineStage.S8_REVIEW.value:         4,
    PipelineStage.S9_PUBLISH.value:        5,
}

_BUCKET_NEXT_STAGE: dict[int, PipelineStage] = {
    1: PipelineStage.S2_NORMALIZE,
    2: PipelineStage.S6_LLM_EXTRACT,
    3: PipelineStage.S8_REVIEW,
    4: PipelineStage.S9_PUBLISH,
}

_BUCKET_PRODUCE_STATUS: dict[int, ContentStatus] = {
    1: ContentStatus.raw,
    2: ContentStatus.enriched,
    3: ContentStatus.ai,
    4: ContentStatus.review,
}

# bucket → 진입 시 expected "현재 허용 status" 목록 (멱등 선조건)
_BUCKET_ALLOWED_STATUS: dict[int, set[ContentStatus]] = {
    1: {ContentStatus.raw},
    2: {ContentStatus.raw},
    3: {ContentStatus.enriched},
    4: {ContentStatus.ai},
}

# bucket → 전이 완료 후 도달 status (멱등 판별: 이미 이 status면 no-op)
_BUCKET_DONE_STATUS: dict[int, ContentStatus] = {
    1: ContentStatus.raw,       # bucket1→2: raw 유지이므로 도착 후도 raw — stage로 판별
    2: ContentStatus.enriched,
    3: ContentStatus.ai,
    4: ContentStatus.approved,
}


def content_bucket(c: Content) -> int:
    """Content 객체 → bucket 번호. rejected=6, terminal/unknown=5."""
    if c.status == ContentStatus.rejected:
        return 6
    return _STAGE_BUCKET.get(c.current_stage.value if c.current_stage else "", 1)


def expand_same_bucket_descendants(db: Session, ids: list[int]) -> list[int]:
    """ids 목록에 각 id와 같은 bucket에 있는 자손(시즌·에피소드)을 추가해 dedup 반환.

    같은 bucket 조건: 자손의 content_bucket()이 부모 노드와 동일.
    앞선 자손이 다른 bucket에 있으면 제외 — desync 방지.
    """
    if not ids:
        return []

    # 시드 id 각각의 bucket 기록 (나중에 자손 bucket과 비교)
    roots = db.query(Content).filter(
        Content.id.in_(ids), Content.is_deleted.is_(False)
    ).all()
    root_bucket: dict[int, int] = {c.id: content_bucket(c) for c in roots}

    # 각 root에 대해 BFS로 자손 수집 — 같은 bucket인 경우만 포함
    all_ids: list[int] = list(ids)
    seen: set[int] = set(ids)

    # (child_id, parent_root_bucket) 쌍으로 frontier 관리
    frontier: list[tuple[int, int]] = [(rid, root_bucket[rid]) for rid in ids]

    while frontier:
        parent_ids = [pid for pid, _ in frontier]
        parent_bucket_map = {pid: bkt for pid, bkt in frontier}

        children = db.query(Content.id, Content.parent_id, Content.current_stage, Content.status).filter(
            Content.parent_id.in_(parent_ids),
            Content.is_deleted.is_(False),
        ).all()

        next_frontier: list[tuple[int, int]] = []
        for child_id, parent_id, cur_stage, status in children:
            if child_id in seen:
                continue
            # 자손 bucket 계산
            if status == ContentStatus.rejected:
                child_bkt = 6
            else:
                child_bkt = _STAGE_BUCKET.get(cur_stage.value if cur_stage else "", 1)

            expected_bkt = parent_bucket_map.get(parent_id)
            if child_bkt == expected_bkt:
                seen.add(child_id)
                all_ids.append(child_id)
                next_frontier.append((child_id, child_bkt))

        frontier = next_frontier

    return all_ids


# ── claim ─────────────────────────────────────────────────────────────────────

def claim_bucket(
    db: Session,
    bucket: int,
    batch_size: int,
    visibility_timeout: int,
) -> list[Content]:
    """bucket 내 처리 가능 콘텐츠를 최대 batch_size 건 claim하여 반환.

    조건:
    - bucket 일치 (current_stage 기준)
    - auto_hold=False
    - rejected 제외
    - auto_claimed_at 없거나 visibility_timeout 초과 (stuck 재claim)
    - SELECT FOR UPDATE SKIP LOCKED — 동시 워커 중복 방지
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=visibility_timeout)

    # bucket별 current_stage 목록
    stages_in_bucket = [
        stage for stage, b in _STAGE_BUCKET.items() if b == bucket
    ]
    # bucket 1(S1): current_stage가 None인 시드 직후 콘텐츠도 포함
    include_null_stage = (bucket == 1)

    q = db.query(Content).filter(
        Content.is_deleted.is_(False),
        Content.auto_hold.is_(False),
        Content.status != ContentStatus.rejected,
    )

    if include_null_stage:
        from sqlalchemy import or_
        q = q.filter(
            or_(
                Content.current_stage.is_(None),
                Content.current_stage.in_(stages_in_bucket),
            )
        )
    else:
        q = q.filter(Content.current_stage.in_(stages_in_bucket))

    # visibility_timeout: 미claim 또는 stuck(timeout 초과) 만
    from sqlalchemy import or_
    q = q.filter(
        or_(
            Content.auto_claimed_at.is_(None),
            Content.auto_claimed_at < cutoff,
        )
    )

    # bucket 4(검수): 이미 임계값 미달로 잔류 판정된 건(auto_review_skipped_at) 제외 — 무한 재평가 방지.
    # 임계값 변경 시 정책 PATCH가 일괄 clear → 재평가 재개.
    if bucket == 4:
        q = q.filter(Content.auto_review_skipped_at.is_(None))

    rows = q.with_for_update(skip_locked=True).limit(batch_size).all()

    # claim 마킹
    for c in rows:
        c.auto_claimed_at = now
    db.flush()

    return rows


def release_claim(db: Session, content_id: int) -> None:
    """처리 완료/실패 후 claim 마킹 해제."""
    c = db.get(Content, content_id)
    if c:
        c.auto_claimed_at = None
        db.flush()


# ── advance_one (멱등) ────────────────────────────────────────────────────────

class AdvanceResult(TypedDict):
    content_id: int
    result: str  # "ok" | "not_found" | "terminal" | "hold"


def advance_one(db: Session, content_id: int, actor: str = "auto") -> AdvanceResult:
    """단건 멱등 advance. txn 내 선조건 재확인 → 이미 이동 시 no-op.

    반환 result:
    - "ok": 정상 전이
    - "already_moved": 다른 actor가 이미 이동
    - "not_found": 콘텐츠 없음
    - "terminal": 더 이상 advance할 단계 없음
    - "hold": auto_hold=True
    """
    from api.programming.metadata.stage_events import record_stage_event
    from api.programming.metadata.ai_engine import recompute_quality_score

    c = db.query(Content).filter(
        Content.id == content_id,
        Content.is_deleted.is_(False),
    ).with_for_update().first()

    if not c:
        return AdvanceResult(content_id=content_id, result="not_found")

    # auto_hold는 AUTO 워커(claim_bucket)만 제외 — 수동(user) 액션은 hold를 해제하고 진행.
    # 워커는 claim 단계에서 이미 hold를 걸러내므로 여기 도달 시 actor="auto"는 방어적 차단.
    if c.auto_hold:
        if actor == "auto":
            return AdvanceResult(content_id=content_id, result="hold")
        c.auto_hold = False  # 운영자 수동 진행 → hold 해제

    cur_bucket = _STAGE_BUCKET.get(c.current_stage.value if c.current_stage else "", 1)
    next_stage = _BUCKET_NEXT_STAGE.get(cur_bucket)
    if next_stage is None:
        return AdvanceResult(content_id=content_id, result="terminal")

    # FOR UPDATE 직렬화로 동시 이중 advance 방지 — 실제 전이만 StageEvent 기록
    record_stage_event(db, content_id, next_stage, StageEventType.ADVANCED, actor=actor)
    produce = _BUCKET_PRODUCE_STATUS.get(cur_bucket)
    if produce is not None:
        c.status = produce

    # 검수(bucket 4) 진입 시 quality_score 재계산
    if cur_bucket + 1 == 4:
        recompute_quality_score(db, content_id)

    release_claim(db, content_id)
    return AdvanceResult(content_id=content_id, result="ok")


# ── approve_one (멱등) ────────────────────────────────────────────────────────

class ApproveResult(TypedDict):
    content_id: int
    result: str  # "ok" | "already_approved" | "not_in_review" | "not_found" | "hold"
    # already_approved: FOR UPDATE 직렬화로 두 번째 approve 시 no-op


def approve_one(db: Session, content_id: int, actor: str = "auto") -> ApproveResult:
    """단건 멱등 approve. 검수(bucket 4) 위치가 아니거나 이미 approved면 no-op."""
    from api.programming.metadata.stage_events import record_stage_event

    c = db.query(Content).filter(
        Content.id == content_id,
        Content.is_deleted.is_(False),
    ).with_for_update().first()

    if not c:
        return ApproveResult(content_id=content_id, result="not_found")

    # auto_hold는 AUTO 워커만 제외 — 수동(user) 승인은 hold 해제하고 진행.
    if c.auto_hold:
        if actor == "auto":
            return ApproveResult(content_id=content_id, result="hold")
        c.auto_hold = False

    # 이미 approved
    if c.status == ContentStatus.approved:
        release_claim(db, content_id)
        return ApproveResult(content_id=content_id, result="already_approved")

    # 검수 bucket(4)에 있어야 함
    cur_bucket = _STAGE_BUCKET.get(c.current_stage.value if c.current_stage else "", 1)
    if cur_bucket != 4:
        return ApproveResult(content_id=content_id, result="not_in_review")

    record_stage_event(db, content_id, PipelineStage.S9_PUBLISH, StageEventType.COMPLETED, actor=actor)
    release_claim(db, content_id)
    return ApproveResult(content_id=content_id, result="ok")


# ── reject_one ────────────────────────────────────────────────────────────────

class RejectResult(TypedDict):
    content_id: int
    result: str  # "ok" | "not_found" | "already_rejected"


def reject_one(db: Session, content_id: int, actor: str = "auto", set_hold: bool = False) -> RejectResult:
    """단건 반려 — status=rejected(bucket 6 반려/실패). StageEvent REJECTED.
    set_hold=True(수동 반려): auto_hold 설정해 재검수 복귀 시 AUTO 재진입 차단.
    set_hold=False(AUTO 반려): hold 미설정 — rejected는 claim에서 이미 제외됨."""
    from api.programming.metadata.stage_events import record_stage_event

    c = db.query(Content).filter(
        Content.id == content_id,
        Content.is_deleted.is_(False),
    ).with_for_update().first()

    if not c:
        return RejectResult(content_id=content_id, result="not_found")

    if c.status == ContentStatus.rejected:
        release_claim(db, content_id)
        return RejectResult(content_id=content_id, result="already_rejected")

    stage = c.current_stage or PipelineStage.S8_REVIEW
    record_stage_event(db, content_id, stage, StageEventType.REJECTED, actor=actor)
    c.status = ContentStatus.rejected
    if set_hold:
        c.auto_hold = True
    c.auto_claimed_at = None
    c.auto_review_skipped_at = None  # 잔류 마킹 해제 (이제 반려됨)
    db.flush()
    return RejectResult(content_id=content_id, result="ok")


# ── enrich_autofill_one (sync) ────────────────────────────────────────────────

class EnrichAutofillResult(TypedDict):
    content_id: int
    enriched_sources: list
    filled_fields: list
    skipped_fields: list
    status_unchanged: str


def enrich_autofill_one(db: Session, content_id: int) -> EnrichAutofillResult:
    """S2 AUTO: tmdb+kmdb enrich 후 빈 필드에만 auto_fill. status 불변.
    async apply_external_fields를 asyncio.run으로 래핑 (Celery 동기 컨텍스트 지원).
    """
    from api.meta_core.enrich import enrich_content
    from api.programming.metadata.service_recommendations import get_content_recommendations
    from api.programming.metadata.service_bulk import apply_external_fields
    from api.programming.metadata.ai_engine import recompute_quality_score

    c = db.query(Content).filter(Content.id == content_id, Content.is_deleted.is_(False)).first()
    if not c:
        return EnrichAutofillResult(
            content_id=content_id, enriched_sources=[], filled_fields=[],
            skipped_fields=[], status_unchanged="",
        )

    before_status = c.status

    result = enrich_content(content_id, db, only_sources={"tmdb", "kmdb"})
    db.flush()

    recs = get_content_recommendations(db, content_id)
    empty = set(recs.missing_fields)
    filled_fields: list[str] = []
    skipped_fields: list[str] = []

    for rec in recs.auto_fill:
        if not rec.recommendations:
            continue
        if rec.field not in empty:
            skipped_fields.append(rec.field)
            continue
        best = max(rec.recommendations, key=lambda r: r.confidence or 0)
        asyncio.run(apply_external_fields(db, content_id, best.source_id, [rec.field]))
        filled_fields.append(rec.field)

    db.refresh(c)
    if c.status != before_status:
        c.status = before_status
        db.add(c)
        db.commit()
        db.refresh(c)

    series_filled = apply_series_meta_from_cache(db, content_id)
    if series_filled:
        filled_fields.extend(series_filled)

    # season/episode 스칼라 필드(production_year, country) 부모 상속 DB 기록
    parent_filled = apply_parent_inheritance(db, content_id)
    if parent_filled:
        filled_fields.extend(parent_filled)

    recompute_quality_score(db, content_id)
    db.commit()

    return EnrichAutofillResult(
        content_id=content_id,
        enriched_sources=result.sources_hit,
        filled_fields=filled_fields,
        skipped_fields=skipped_fields,
        status_unchanged=c.status.value if c.status else (before_status.value if before_status else ""),
    )


# ── apply_parent_inheritance ──────────────────────────────────────────────────

def apply_parent_inheritance(db: Session, content_id: int) -> list[str]:
    """season/episode 전용: 부모 스칼라 필드(production_year, country)를 빈 경우만 DB 기록.

    title·synopsis·genre·cast 등은 건드리지 않음(점수만 read-time 상속).
    empty-only + 멱등. movie/series는 무처리.
    반환: 채운 필드명 list (빈 list = 처리 없음).
    """
    from api.programming.metadata.models.content import ContentType

    c = db.query(Content).filter(Content.id == content_id, Content.is_deleted.is_(False)).first()
    if not c or c.content_type not in (ContentType.season, ContentType.episode):
        return []

    from api.programming.metadata.inheritance import resolve_inherited_metadata
    inh = resolve_inherited_metadata(c, db) or {}

    filled: list[str] = []
    if not c.production_year and inh.get("production_year"):
        c.production_year = inh["production_year"]
        filled.append("production_year")
    if not c.country and inh.get("country"):
        c.country = inh["country"]
        filled.append("country")

    if filled:
        db.add(c)
        db.flush()
    return filled


# ── apply_series_meta_from_cache ──────────────────────────────────────────────

def apply_series_meta_from_cache(db: Session, content_id: int) -> list[str]:
    """series 노드 전용: TmdbTvCache → ContentMetadata 시리즈 필드 채우기.

    빈 값만 채움(empty-only) + 멱등. movie/season/episode는 무처리.
    ExternalMetaSource(tmdb) → TmdbTvCache(id) 경로로 캐시 조회.
    캐시 미연결 시 title+first_air_year 퍼지 매칭 시도(기존 worker 방식 동일).
    반환: 채운 필드명 list (빈 list = 처리 없음).
    """
    from api.programming.metadata.models.content import ContentType, ContentMetadata
    from api.programming.metadata.models.external import ExternalMetaSource, ExternalSourceType
    from api.programming.metadata.models.tmdb_cache import TmdbTvCache

    c = db.query(Content).filter(Content.id == content_id, Content.is_deleted.is_(False)).first()
    if not c or c.content_type != ContentType.series:
        return []

    # ExternalMetaSource(tmdb) → TmdbTvCache 경로
    cache: TmdbTvCache | None = None
    ext = (
        db.query(ExternalMetaSource)
        .filter(
            ExternalMetaSource.content_id == content_id,
            ExternalMetaSource.source_type == ExternalSourceType.tmdb,
        )
        .first()
    )
    if ext and ext.external_id:
        try:
            tmdb_id = int(ext.external_id)
            cache = db.get(TmdbTvCache, tmdb_id)
        except (ValueError, TypeError):
            pass

    # 퍼지 폴백: name 정확 매칭 → year 슬라이싱
    if cache is None:
        cache = db.query(TmdbTvCache).filter(TmdbTvCache.name == c.title).first()
    if cache is None and c.production_year:
        from sqlalchemy import extract
        import difflib
        candidates = (
            db.query(TmdbTvCache)
            .filter(extract("year", TmdbTvCache.first_air_date) == c.production_year)
            .limit(50)
            .all()
        )
        best_ratio, best_cache = 0.0, None
        for cand in candidates:
            ratio = difflib.SequenceMatcher(None, c.title, cand.name).ratio()
            if ratio > best_ratio:
                best_ratio, best_cache = ratio, cand
        if best_ratio >= 0.85:
            cache = best_cache

    if cache is None:
        return []

    meta = db.query(ContentMetadata).filter_by(content_id=content_id).first()
    if meta is None:
        meta = ContentMetadata(content_id=content_id)
        db.add(meta)
        db.flush()

    filled: list[str] = []

    def _set_if_empty(attr: str, value) -> None:
        if value is not None and getattr(meta, attr) is None:
            setattr(meta, attr, value)
            filled.append(attr)

    _set_if_empty("total_seasons", cache.number_of_seasons)
    _set_if_empty("total_episodes", cache.number_of_episodes)
    _set_if_empty("first_air_date", cache.first_air_date)
    _set_if_empty("last_air_date", cache.last_air_date)
    _set_if_empty("air_status", cache.status)
    raw = cache.raw_json or {}
    networks_val = [n.get("name") for n in raw.get("networks", []) if n.get("name")]
    _set_if_empty("networks", networks_val if networks_val else None)

    if filled:
        db.flush()
        logger.info("[series_meta] content_id=%d filled=%s", content_id, filled)

    return filled


# ── ai_autofill_one (sync) ────────────────────────────────────────────────────

class AiAutofillResult(TypedDict):
    content_id: int
    rag_sources: list
    ai_tasks: dict
    filled_fields: list
    skipped_fields: list
    status_unchanged: str


def ai_autofill_one(db: Session, content_id: int) -> AiAutofillResult:
    """S3 AUTO: RAG+AI태스크 후 빈 필드에만 보완값 적용. status 불변.
    async run_single_ai_task를 asyncio.run으로 래핑 (Celery 동기 컨텍스트 지원).
    """
    from api.meta_core.reference_extract import reference_extract
    from api.programming.metadata.service_recommendations import get_content_recommendations
    from api.programming.metadata.service_content import update_content
    from api.programming.metadata.schemas import ContentUpdate
    from api.programming.metadata.ai_tasks.runner import run_single_ai_task
    from api.programming.metadata.ai_engine import recompute_quality_score

    c = db.query(Content).filter(Content.id == content_id, Content.is_deleted.is_(False)).first()
    if not c:
        return AiAutofillResult(
            content_id=content_id, rag_sources=[], ai_tasks={},
            filled_fields=[], skipped_fields=[], status_unchanged="",
        )

    before_status = c.status

    ref = reference_extract(content_id, db)
    facts = ref.wikidata_facts

    recs = get_content_recommendations(db, content_id)
    empty = set(recs.missing_fields)
    autofill: dict[str, str] = {}
    for rec in recs.auto_fill:
        if rec.recommendations:
            best = max(rec.recommendations, key=lambda r: r.confidence or 0)
            autofill[rec.field] = best.value

    payload: dict = {}
    filled_fields: list[str] = []
    skipped_fields: list[str] = []

    def _pick(field: str, facts_key: str | None = None) -> str | None:
        v = autofill.get(field)
        if not v and facts_key:
            raw = facts.get(facts_key)
            if raw is not None:
                v = ", ".join(raw) if isinstance(raw, list) else str(raw)
        return v if v else None

    field_map: list[tuple[str, str, str | None]] = [
        ("cast",     "cast",      "cast"),
        ("director", "directors", "directors"),
        ("genres",   "genres",    "genres"),
        ("country",  "country",   "country"),
        ("synopsis", "synopsis",  None),
    ]
    for missing_key, update_key, facts_key in field_map:
        val = _pick(missing_key, facts_key)
        if missing_key in empty:
            if val:
                payload[update_key] = val
                filled_fields.append(missing_key)
        else:
            if val:
                skipped_fields.append(missing_key)

    if "runtime" in empty:
        rv = autofill.get("runtime") or (str(facts.get("runtime")) if facts.get("runtime") else None)
        if rv:
            try:
                payload["runtime"] = int(str(rv).strip().split()[0])
                filled_fields.append("runtime")
            except (ValueError, IndexError):
                pass
    elif autofill.get("runtime") or facts.get("runtime"):
        skipped_fields.append("runtime")

    if not c.production_year:
        yr = facts.get("production_year") or autofill.get("production_year")
        if yr:
            try:
                payload["production_year"] = int(str(yr)[:4])
                filled_fields.append("production_year")
            except ValueError:
                pass

    if payload:
        update_content(db, content_id, ContentUpdate(**payload))

    ai_results: dict[str, str] = {}
    for task_name in ("translate_synopsis", "short_synopsis"):
        try:
            r = asyncio.run(run_single_ai_task(content_id, task_name, db))
            ai_results[task_name] = r.get("status", "ok")
        except Exception:
            ai_results[task_name] = "error"

    db.refresh(c)
    if c.status != before_status:
        c.status = before_status
        db.add(c)
        db.commit()
        db.refresh(c)

    recompute_quality_score(db, content_id)
    db.commit()

    return AiAutofillResult(
        content_id=content_id,
        rag_sources=ref.sources_hit,
        ai_tasks=ai_results,
        filled_fields=filled_fields,
        skipped_fields=skipped_fields,
        status_unchanged=c.status.value if c.status else (before_status.value if before_status else ""),
    )
