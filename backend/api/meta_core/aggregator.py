"""
Field Aggregator — FieldSuggestion 풀 → FieldResolution → ContentMetadata 반영

aggregate_content(content_id, db) → AggregateReport
aggregate_batch(content_ids, db) → list[AggregateReport]

ContentMetadata 에 쓰는 유일한 합법 경로.
외부 API 호출 없음. Suggestion 풀만 보고 결정.
manual_pick 상태 FieldResolution 은 덮어쓰지 않음.
참조: docs/dev/meta-intelligence.md §2, §5 / field_strategy.py
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from api.meta_core.field_strategy import FIELD_STRATEGIES, FieldType, get_strategy
from api.meta_core.models.intelligence import FieldResolution, FieldSuggestion
from api.meta_core.scoring import source_reliability
from api.programming.metadata.models.content import ContentMetadata
from api.programming.metadata.models.external import ExternalMetaSource, ExternalSourceType
from api.programming.metadata.models.image import ContentImage, ImageType
from api.programming.metadata.models.taxonomy import ContentGenre

logger = logging.getLogger(__name__)

_MANUAL_DECISIONS = {"manual_pick", "manual_merge"}


def llm_merge_synopses(values: list[str], db: Session) -> str:
    """여러 시놉시스를 LLM으로 통합 — 검수자 명시 요청 시에만 호출.

    비용 추적: external_sync_log 에 llm_merge 1행 기록.
    폴백 체인: Gemini → Groq → Ollama.
    """
    import asyncio
    import os
    from api.programming.metadata.llm import get_provider_chain
    from api.programming.metadata.models.tmdb_cache import (
        ExternalSyncLog, TmdbSyncSource, TmdbSyncStatus,
    )

    prompt = (
        "아래 시놉시스들을 하나의 자연스러운 한국어 문장으로 통합해줘. "
        "중복 표현은 제거하고 핵심 내용만 남겨. 200자 이내로.\n\n"
        + "\n---\n".join(f"[{i+1}] {v}" for i, v in enumerate(values))
    )

    engine = os.environ.get("AI_ENGINE", "gemini")
    chain = get_provider_chain(engine)

    async def _run() -> str:
        for provider_cls in chain:
            try:
                provider = provider_cls()
                return await provider.generate(prompt)
            except Exception as exc:
                logger.warning("[llm_merge] provider=%s 실패: %s", provider_cls.__name__, exc)
        return values[0] if values else ""

    result_text = asyncio.run(_run())

    log = ExternalSyncLog(
        source=TmdbSyncSource.llm_merge,
        status=TmdbSyncStatus.completed,
        items_fetched=len(values),
        items_inserted=1,
    )
    db.add(log)
    db.flush()

    return result_text


@dataclass
class FieldAggregateResult:
    field_name: str
    decision: str       # auto_agreement | auto_quality | pending | skipped
    applied: bool = False
    suggestion_ids: list[int] = field(default_factory=list)
    agreeing_sources: list[str] = field(default_factory=list)


@dataclass
class AggregateReport:
    content_id: int
    auto_applied: int = 0
    pending: int = 0
    skipped: int = 0
    fields: list[FieldAggregateResult] = field(default_factory=list)


# ── Public API ────────────────────────────────────────────────────────────────

def aggregate_content(
    content_id: int, db: Session, enable_web_search: bool = False
) -> AggregateReport:
    """pending FieldSuggestion 풀에 Strategy 적용 → FieldResolution + write-back.

    Args:
        content_id: Content ID
        db: Database session
        enable_web_search: True 시 빈 필드(synopsis, cast, director)에 대해 WebSearch 실행
    """
    report = AggregateReport(content_id=content_id)

    # Step 0: enable_web_search=True 시 WebSearch 기반 suggestions 추가
    if enable_web_search:
        _add_websearch_suggestions(content_id, db)

    suggestions = (
        db.query(FieldSuggestion)
        .filter(
            FieldSuggestion.content_id == content_id,
            FieldSuggestion.status == "pending",
        )
        .all()
    )
    if not suggestions:
        return report

    # field_name 기준 그룹핑
    by_field: dict[str, list[FieldSuggestion]] = {}
    for s in suggestions:
        by_field.setdefault(s.field_name, []).append(s)

    for field_name, field_sugs in by_field.items():
        strategy = get_strategy(field_name)
        if strategy is None:
            report.skipped += 1
            report.fields.append(FieldAggregateResult(field_name, "skipped"))
            continue

        result = _decide(content_id, field_name, field_sugs, strategy, db)
        if result.applied:
            report.auto_applied += 1
        elif result.decision == "pending":
            report.pending += 1
        else:
            report.skipped += 1
        report.fields.append(result)

    db.flush()
    logger.info(
        "[aggregator] content_id=%d auto=%d pending=%d skipped=%d",
        content_id, report.auto_applied, report.pending, report.skipped,
    )
    return report


def aggregate_batch(
    content_ids: list[int], db: Session, enable_web_search: bool = False
) -> list[AggregateReport]:
    return [aggregate_content(cid, db, enable_web_search=enable_web_search) for cid in content_ids]


# ── 분류별 결정 ───────────────────────────────────────────────────────────────

def _decide(
    content_id: int,
    field_name: str,
    sugs: list[FieldSuggestion],
    strategy,
    db: Session,
) -> FieldAggregateResult:
    if strategy.type == FieldType.A_SINGLE:
        return _decide_a(content_id, field_name, sugs, strategy, db)
    if strategy.type == FieldType.B_MULTI:
        return _decide_b(content_id, field_name, sugs, strategy, db)
    if strategy.type == FieldType.C_TEXT:
        return _decide_c(content_id, field_name, sugs, db)
    if strategy.type == FieldType.D_ASSET:
        return _decide_d(content_id, field_name, sugs, strategy, db)
    if strategy.type == FieldType.E_EXTERNAL_ID:
        return _decide_e(content_id, field_name, sugs, db)
    return FieldAggregateResult(field_name, "skipped")


def _decide_a(content_id, field_name, sugs, strategy, db) -> FieldAggregateResult:
    """A: 정규화 값 기준 그룹핑 → 최다 동의 그룹 선택 → 가드 통과 시 auto_agreement."""
    norm = strategy.normalizer or (lambda x: str(x).strip().lower())
    tol = strategy.tolerance

    # 값별로 소스 목록 집계
    groups: dict[str, list[FieldSuggestion]] = {}
    for s in sugs:
        raw_val = s.value_json
        if isinstance(raw_val, list):
            raw_val = raw_val[0] if raw_val else ""
        key = _norm_with_tolerance(str(raw_val), norm, tol)
        groups.setdefault(key, []).append(s)

    # 동의 수 최대 그룹
    best_key, best_group = max(groups.items(), key=lambda kv: len(kv[1]))
    agree_count = len(best_group)
    weight_sum = sum(source_reliability(s.source_type) for s in best_group)
    sources = [s.source_type for s in best_group]

    if agree_count >= strategy.agree_threshold and weight_sum >= strategy.weight_threshold:
        chosen_val = best_group[0].value_json
        applied = _upsert_resolution(
            db, content_id, field_name,
            decision="auto_agreement",
            chosen_value=chosen_val,
            suggestion_ids=[s.id for s in best_group],
            agreeing_sources=sources,
            agree_count=agree_count,
            apply=True,
        )
        if applied:
            _mark_suggestions(db, best_group, "applied")
            _mark_suggestions(db, [s for s in sugs if s not in best_group], "superseded")
            _write_back_a(content_id, field_name, chosen_val, best_group[0].source_type, db)
        return FieldAggregateResult(field_name, "auto_agreement", applied,
                                    [s.id for s in best_group], sources)

    # 가드 미충족 → pending
    _upsert_resolution(db, content_id, field_name, decision="pending",
                       chosen_value=None, suggestion_ids=[s.id for s in sugs],
                       agreeing_sources=sources, agree_count=agree_count, apply=False)
    return FieldAggregateResult(field_name, "pending", False, [s.id for s in sugs], sources)


def _decide_b(content_id, field_name, sugs, strategy, db) -> FieldAggregateResult:
    """B: 멤버별 출현 소스 카운트 → threshold 이상 멤버 auto union (cap 적용)."""
    member_sources: dict[str, set[str]] = {}
    for s in sugs:
        items = s.value_json if isinstance(s.value_json, list) else [s.value_json]
        for item in items:
            key = _member_key(item)
            member_sources.setdefault(key, set()).add(s.source_type)

    auto_members = [
        k for k, srcs in member_sources.items()
        if len(srcs) >= strategy.agree_threshold
    ]
    if strategy.max_auto:
        auto_members = auto_members[: strategy.max_auto]

    agree_sources = list({src for k in auto_members for src in member_sources[k]})

    if auto_members:
        applied = _upsert_resolution(
            db, content_id, field_name,
            decision="auto_agreement",
            chosen_value=auto_members,
            suggestion_ids=[s.id for s in sugs],
            agreeing_sources=agree_sources,
            agree_count=len(auto_members),
            apply=True,
        )
        if applied:
            _mark_suggestions(db, sugs, "applied")
        return FieldAggregateResult(field_name, "auto_agreement", applied,
                                    [s.id for s in sugs], agree_sources)

    _upsert_resolution(db, content_id, field_name, decision="pending",
                       chosen_value=None, suggestion_ids=[s.id for s in sugs],
                       agreeing_sources=[], agree_count=0, apply=False)
    return FieldAggregateResult(field_name, "pending", False, [s.id for s in sugs])


def _decide_c(content_id, field_name, sugs, db) -> FieldAggregateResult:
    """C: 항상 pending."""
    _upsert_resolution(db, content_id, field_name, decision="pending",
                       chosen_value=None, suggestion_ids=[s.id for s in sugs],
                       agreeing_sources=[s.source_type for s in sugs],
                       agree_count=0, apply=False)
    return FieldAggregateResult(field_name, "pending", False, [s.id for s in sugs])


def _decide_d(content_id, field_name, sugs, strategy, db) -> FieldAggregateResult:
    """D: source_priority 순 → 첫 번째 소스 자동 채택."""
    priority = strategy.source_priority
    ordered = sorted(sugs, key=lambda s: _source_rank(s.source_type, priority))
    best = ordered[0]

    applied = _upsert_resolution(
        db, content_id, field_name,
        decision="auto_quality",
        chosen_value=best.value_json,
        suggestion_ids=[best.id],
        agreeing_sources=[best.source_type],
        agree_count=1,
        apply=True,
    )
    if applied:
        _mark_suggestions(db, [best], "applied")
        _mark_suggestions(db, [s for s in sugs if s != best], "superseded")
        _write_back_d(content_id, field_name, best.value_json, best.source_type, db)
    return FieldAggregateResult(field_name, "auto_quality", applied, [best.id], [best.source_type])


def _decide_e(content_id, field_name, sugs, db) -> FieldAggregateResult:
    """E: 모든 소스 외부 ID → ExternalMetaSource upsert."""
    sug_ids = []
    sources = []
    for s in sugs:
        ids: dict = s.value_json if isinstance(s.value_json, dict) else {}
        for src_key, ext_id in ids.items():
            if not ext_id:
                continue
            src_type = _map_source_key(src_key)
            if src_type is None:
                continue
            existing = (
                db.query(ExternalMetaSource)
                .filter(
                    ExternalMetaSource.content_id == content_id,
                    ExternalMetaSource.source_type == src_type,
                )
                .first()
            )
            if not existing:
                db.add(ExternalMetaSource(
                    content_id=content_id,
                    source_type=src_type,
                    external_id=str(ext_id),
                ))
        sug_ids.append(s.id)
        sources.append(s.source_type)

    _upsert_resolution(db, content_id, field_name, decision="auto_agreement",
                       chosen_value=[s.value_json for s in sugs],
                       suggestion_ids=sug_ids, agreeing_sources=sources,
                       agree_count=len(sugs), apply=True)
    _mark_suggestions(db, sugs, "applied")
    return FieldAggregateResult(field_name, "auto_agreement", True, sug_ids, sources)


# ── Write-back ────────────────────────────────────────────────────────────────

def _write_back_a(content_id, field_name, value, source_type, db):
    """A 자동 확정 → ContentGenre(primary_genre) 등 갱신."""
    if field_name == "primary_genre":
        # 기존 is_primary=True 해제 후 첫 번째 장르에 표시 (genre_id 추론 불가 — source 기록만)
        existing = (
            db.query(ContentGenre)
            .filter(ContentGenre.content_id == content_id, ContentGenre.is_primary.is_(True))
            .first()
        )
        if existing:
            existing.source = source_type
        # ContentGenre 신규 생성은 genre_id(FK) 필요해 카탈로그 조회가 선행돼야 하므로 skip


def _write_back_d(content_id, field_name, value, source_type, db):
    """D 자동 확정 → ContentImage 생성 (poster 계열)."""
    image_type_map = {
        "poster": ImageType.poster,
        "backdrop": ImageType.thumbnail,
        "stillcut": ImageType.stillcut,
        "logo": ImageType.logo,
    }
    img_type = image_type_map.get(field_name)
    if img_type is None:
        return
    url = value if isinstance(value, str) else None
    if not url:
        return

    # 기존 is_primary=True 해제
    db.query(ContentImage).filter(
        ContentImage.content_id == content_id,
        ContentImage.image_type == img_type,
        ContentImage.is_primary.is_(True),
    ).update({"is_primary": False})

    existing = (
        db.query(ContentImage)
        .filter(ContentImage.content_id == content_id,
                ContentImage.image_type == img_type,
                ContentImage.url == url)
        .first()
    )
    if existing:
        existing.is_primary = True
        existing.source = source_type
    else:
        db.add(ContentImage(
            content_id=content_id,
            image_type=img_type,
            url=url,
            source=source_type,
            is_primary=True,
        ))


# ── FieldResolution upsert ────────────────────────────────────────────────────

def _upsert_resolution(
    db, content_id, field_name, *, decision, chosen_value, suggestion_ids,
    agreeing_sources, agree_count, apply
) -> bool:
    """UNIQUE(content_id, field_name) 보존. manual_pick 은 덮어쓰지 않음. → 실제 apply 여부 반환."""
    existing = (
        db.query(FieldResolution)
        .filter(
            FieldResolution.content_id == content_id,
            FieldResolution.field_name == field_name,
        )
        .first()
    )
    if existing and existing.decision in _MANUAL_DECISIONS:
        return False  # manual 결정 보존

    now = datetime.now(timezone.utc)
    if existing:
        existing.decision = decision
        existing.chosen_value_json = chosen_value
        existing.chosen_suggestion_ids = suggestion_ids
        existing.agreement_count = agree_count
        existing.agreeing_sources_json = agreeing_sources
        existing.applied_to_content = apply
        existing.decided_by = "system"
        existing.decided_at = now
    else:
        db.add(FieldResolution(
            content_id=content_id,
            field_name=field_name,
            decision=decision,
            chosen_value_json=chosen_value,
            chosen_suggestion_ids=suggestion_ids,
            agreement_count=agree_count,
            agreeing_sources_json=agreeing_sources,
            applied_to_content=apply,
            decided_by="system",
            decided_at=now,
        ))
    return apply


# ── 유틸 ─────────────────────────────────────────────────────────────────────

def _norm_with_tolerance(val: str, norm_fn, tolerance: int | None) -> str:
    normed = norm_fn(val)
    if tolerance is not None:
        try:
            num = int("".join(c for c in normed if c.isdigit()))
            return str(round(num / tolerance) * tolerance)
        except (ValueError, ZeroDivisionError):
            pass
    return normed


def _member_key(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("name", item)).strip().lower()
    return str(item).strip().lower()


def _source_rank(source_type: str, priority: list[str]) -> int:
    try:
        return priority.index(source_type)
    except ValueError:
        return len(priority)


def _mark_suggestions(db, sugs: list[FieldSuggestion], status: str):
    for s in sugs:
        s.status = status


def _map_source_key(key: str) -> ExternalSourceType | None:
    mapping = {
        "tmdb": ExternalSourceType.tmdb,
        "kobis": ExternalSourceType.kobis,
        "kmdb": ExternalSourceType.kmdb,
        "kmdb_docid": ExternalSourceType.kmdb,
    }
    return mapping.get(key.lower())


# ── WebSearch opt-in integration ────────────────────────────────────────────────

def _add_websearch_suggestions(content_id: int, db: Session) -> None:
    """
    WebSearch 기반 suggestions 추가 (enable_web_search=True 시).

    대상 필드: synopsis, cast, director (비어있을 때만)
    """
    import asyncio
    from api.programming.metadata.models.content import Content
    from api.meta_core.web_search import search_with_fallback

    # Step 1: Content 조회
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        logger.warning(f"[websearch] content_id={content_id} not found")
        return

    # Step 2: 빈 필드 탐지
    target_fields = []
    metadata = content.metadata
    if metadata:
        if not metadata.synopsis or metadata.synopsis.strip() == "":
            target_fields.append("synopsis")

    if not target_fields:
        logger.debug(f"[websearch] content_id={content_id} no empty fields")
        return

    # Step 3: WebSearch 실행
    search_query = f"{content.title} {content.production_year or ''} 시놉시스 줄거리".strip()

    try:
        results, provider = asyncio.run(
            search_with_fallback(search_query, db, num=5)
        )
    except Exception as e:
        logger.warning(f"[websearch] search_with_fallback failed: {e}")
        return

    if not results:
        logger.debug(f"[websearch] no results for {search_query}")
        return

    # Step 4: LLM 추출 + FieldSuggestion 생성
    for field_name in target_fields:
        _create_websearch_suggestion(content_id, field_name, results, db)


def _create_websearch_suggestion(
    content_id: int, field_name: str, search_results, db: Session
) -> None:
    """LLM으로 WebSearch 결과 추출 후 FieldSuggestion 생성."""
    import asyncio
    from api.programming.metadata.llm import get_provider_chain

    snippet = " ".join(r.snippet for r in search_results[:3])[:500]

    if field_name == "synopsis":
        prompt = f"웹 검색 결과에서 시놉시스(줄거리)를 한국어 2~3문장으로 요약해줘. 오직 요약만 반환:\n{snippet}"
    elif field_name == "cast":
        prompt = f"웹 검색 결과에서 배우 이름을 쉼표로 구분해 나열해줘:\n{snippet}"
    elif field_name == "director":
        prompt = f"웹 검색 결과에서 감독 이름을 찾아줘:\n{snippet}"
    else:
        return

    async def _run_extraction() -> str:
        chain = get_provider_chain("gemini")
        for provider_cls in chain:
            try:
                provider = provider_cls()
                return await provider.generate(prompt)
            except Exception as e:
                logger.debug(f"[websearch] {provider_cls.__name__} failed: {e}")
        return ""

    try:
        extracted_value = asyncio.run(_run_extraction())
    except Exception as e:
        logger.error(f"[websearch] extraction failed: {e}")
        return

    if not extracted_value or extracted_value.strip() == "":
        logger.debug(f"[websearch] empty extraction for {field_name}")
        return

    # FieldSuggestion 생성
    suggestion = FieldSuggestion(
        content_id=content_id,
        field_name=field_name,
        value_json=extracted_value,
        source_type=ExternalSourceType.websearch,
        source_id="websearch",
        confidence_score=0.5,  # Phase C 정책
        status="pending",
    )
    db.add(suggestion)
    db.flush()
    logger.info(f"[websearch] added suggestion: {content_id} {field_name}")
