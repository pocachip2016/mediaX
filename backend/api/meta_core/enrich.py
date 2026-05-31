"""
Meta Intelligence Enrich — Gap 기반 외부 소스 호출 → candidate/suggestion 적재

enrich_content(content_id, db) → EnrichResult

외부 소스를 동기 httpx 로 호출해 MetadataCandidate upsert,
compute_match_score 로 MatchEdge 계산, FieldSuggestion 분해.

금지: ContentMetadata 직접 쓰기. audit trail 은 step7(Aggregator) 에서.
참조: docs/dev/meta-intelligence.md §1 §4
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from shared.config import settings
from api.meta_core.gap import analyze_gap
from api.meta_core.scoring import classify_match, compute_match_score, normalize_title
from api.meta_core.clients.kmdb_client import KmdbApiKeyMissing, KmdbClient
from api.meta_core.models.intelligence import FieldSuggestion, MatchEdge, MetadataCandidate
from api.programming.metadata.models.content import Content
from api.programming.metadata.models.external import ExternalSourceType

logger = logging.getLogger(__name__)

_TMDB_SEARCH_MOVIE = "https://api.themoviedb.org/3/search/movie"
_TMDB_SEARCH_TV = "https://api.themoviedb.org/3/search/tv"
_TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

# FieldSuggestion 으로 분해할 필드 목록
_SUGGESTION_FIELDS = ("synopsis", "poster", "cast", "director", "primary_genre", "external_id")


@dataclass
class EnrichResult:
    content_id: int
    candidates_upserted: int = 0
    match_edges_created: int = 0
    suggestions_created: int = 0
    sources_skipped: list[str] = field(default_factory=list)
    sources_hit: list[str] = field(default_factory=list)


# ── Public API ────────────────────────────────────────────────────────────────

def enrich_content(
    content_id: int, db: Session, *,
    use_cache_db: bool = True,
    only_sources: set[str] | None = None,
) -> EnrichResult:
    """Gap 분석 후 외부 소스 호출 → candidate/suggestion 적재.

    use_cache_db=False 시 모든 소스 skip.
    only_sources 지정 시 해당 소스만 강제 실행(gap·정책 무시) — 수동 sub-step용(ADR-009).
    """
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise ValueError(f"Content {content_id} not found")

    result = EnrichResult(content_id=content_id)

    if only_sources is not None:
        needed_sources = set(only_sources)
    else:
        if not use_cache_db:
            logger.info("[enrich] content_id=%d use_cache_db=False → skip all sources", content_id)
            return result
        gap_report = analyze_gap(content_id, db)
        if gap_report.is_clean:
            logger.info("[enrich] content_id=%d 갭 없음 — skip", content_id)
            return result
        needed_sources = _needed_sources(gap_report)

    tmdb_key = settings.TMDB_API_KEY
    kmdb_key = settings.KMDB_API_KEY

    if "tmdb" in needed_sources:
        if tmdb_key:
            raw = _fetch_tmdb(content, tmdb_key, db)
            if raw:
                candidate = _upsert_candidate(db, ExternalSourceType.tmdb, raw)
                result.candidates_upserted += 1
                result.sources_hit.append("tmdb")
                _process_candidate(content_id, content, candidate, db, result)
            else:
                result.sources_skipped.append("tmdb:no_result")
        else:
            result.sources_skipped.append("tmdb:no_key")

    if "kmdb" in needed_sources:
        try:
            raws = _fetch_kmdb_with_cache(db, content)
            for raw in raws[:3]:
                candidate = _upsert_candidate(db, ExternalSourceType.kmdb, raw)
                result.candidates_upserted += 1
                _process_candidate(content_id, content, candidate, db, result)
            if raws:
                result.sources_hit.append("kmdb")
            else:
                result.sources_skipped.append("kmdb:no_result")
        except KmdbApiKeyMissing:
            result.sources_skipped.append("kmdb:no_key")

    db.flush()
    logger.info(
        "[enrich] content_id=%d candidates=%d edges=%d suggestions=%d",
        content_id, result.candidates_upserted, result.match_edges_created,
        result.suggestions_created,
    )
    return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _needed_sources(gap_report) -> set[str]:
    from api.programming.metadata.content_kind import TV_TYPES
    from api.programming.metadata.models.content import ContentType

    sources: set[str] = set()
    for g in gap_report.missing_fields:
        sources.update(g.recommended_sources)

    # KMDB/KOBIS 는 영화 전용 DB — tv-type(series/season/episode) 에는 적용 안 함
    try:
        ct = ContentType(gap_report.content_type)
    except ValueError:
        ct = None
    if ct in TV_TYPES:
        sources.discard("kmdb")
        sources.discard("kobis")

    return sources


def _fetch_kmdb_with_cache(db: Session, content: Content) -> list[dict]:
    """KMDB enrich: 캐시 우선 조회 → miss 시 API 호출 + 캐시 upsert.

    cache hit/miss 는 INFO 레벨로 로깅.
    """
    from api.programming.metadata.models.kmdb_cache import KmdbMovieCache
    from workers.tasks.kmdb_cache import _upsert_kmdb_movie

    # 1. 캐시 조회 (title + prod_year 일치)
    q = db.query(KmdbMovieCache).filter(KmdbMovieCache.title == content.title)
    if content.production_year:
        q = q.filter(KmdbMovieCache.prod_year == content.production_year)
    cached = q.limit(3).all()

    if cached:
        logger.info("[enrich] KMDB cache HIT content_id=%d title=%r year=%s (%d건)",
                    content.id, content.title, content.production_year, len(cached))
        return [c.raw_json for c in cached if c.raw_json]

    # 2. cache miss → API 호출
    logger.info("[enrich] KMDB cache MISS content_id=%d title=%r — API 호출",
                content.id, content.title)
    client = KmdbClient(api_key=settings.KMDB_API_KEY)
    raws = client.search_movie(content.title, year=content.production_year)

    # 3. 결과를 캐시에 저장 (다음 번 enrich 에서 hit)
    for raw in raws:
        try:
            _upsert_kmdb_movie(db, raw)
        except Exception as exc:
            logger.warning("[enrich] KMDB cache upsert 실패: %s", exc)

    return raws


def _fetch_tmdb(content: Content, api_key: str, db: Session) -> dict | None:
    from api.programming.metadata.content_kind import external_lookup_target, tmdb_search_kind

    # season/episode 는 시리즈 조상으로 조회 — 단독 에피소드 타이틀은 TMDB 매칭 불가
    lookup = external_lookup_target(content, db)
    kind = tmdb_search_kind(content)

    if kind == "tv":
        url = _TMDB_SEARCH_TV
        params: dict[str, Any] = {
            "api_key": api_key,
            "query": lookup.title,
            "language": "ko-KR",
        }
        if lookup.production_year:
            params["first_air_date_year"] = lookup.production_year
    else:
        url = _TMDB_SEARCH_MOVIE
        params = {"api_key": api_key, "query": lookup.title, "language": "ko-KR"}
        if lookup.production_year:
            params["year"] = lookup.production_year

    try:
        resp = httpx.get(url, params=params, timeout=10.0)
        results = resp.json().get("results", [])
        return results[0] if results else None
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("[enrich] TMDB 검색 실패 content_id=%d: %s", content.id, exc)
        return None


def _parse_candidate_fields(source_type: ExternalSourceType, raw: dict) -> dict:
    """소스별 raw dict → MetadataCandidate 공통 필드 파싱."""
    if source_type == ExternalSourceType.tmdb:
        title = raw.get("title") or raw.get("name") or ""
        return {
            "source_external_id": str(raw.get("id", "")),
            "title_norm": normalize_title(title),
            "original_title": raw.get("original_title") or raw.get("original_name"),
            "year": _year_from_str(raw.get("release_date") or raw.get("first_air_date")),
            "synopsis": raw.get("overview"),
            "poster_url": (
                f"{_TMDB_IMAGE_BASE}{raw['poster_path']}" if raw.get("poster_path") else None
            ),
            "cast_json": None,
            "director_json": None,
            "genre_json": None,
            "external_ids_json": {"tmdb": raw.get("id")},
        }
    if source_type == ExternalSourceType.kmdb:
        title = raw.get("title", "")
        directors = [
            {"name": d.get("directorNm", "")}
            for d in (raw.get("directors", {}).get("director") or [])
        ]
        actors = [
            {"name": a.get("actorNm", ""), "role": "actor"}
            for a in (raw.get("actors", {}).get("actor") or [])[:10]
        ]
        plots = raw.get("plots", {}).get("plot") or []
        synopsis = next((p.get("plotText") for p in plots if p.get("plotText")), None)
        return {
            "source_external_id": raw.get("DOCID", ""),
            "title_norm": normalize_title(title),
            "original_title": raw.get("titleEng"),
            "year": int(raw["prodYear"]) if raw.get("prodYear") else None,
            "synopsis": synopsis,
            "poster_url": None,
            "cast_json": actors or None,
            "director_json": directors or None,
            "genre_json": [g.strip() for g in raw.get("genre", "").split(",") if g.strip()] or None,
            "external_ids_json": {"kmdb_docid": raw.get("DOCID")},
        }
    return {"source_external_id": "", "title_norm": ""}


def _year_from_str(date_str: str | None) -> int | None:
    if date_str and len(date_str) >= 4:
        try:
            return int(date_str[:4])
        except ValueError:
            pass
    return None


def _upsert_candidate(db: Session, source_type: ExternalSourceType, raw: dict) -> MetadataCandidate:
    parsed = _parse_candidate_fields(source_type, raw)
    source_ext_id = parsed.get("source_external_id") or ""

    existing = (
        db.query(MetadataCandidate)
        .filter(
            MetadataCandidate.source_type == source_type.value,
            MetadataCandidate.source_external_id == source_ext_id,
        )
        .first()
    )
    if existing:
        existing.raw_payload = raw
        existing.fetched_at = datetime.now(timezone.utc)
        for k, v in parsed.items():
            if k not in ("source_external_id",) and v is not None:
                setattr(existing, k, v)
        db.flush()
        return existing

    candidate = MetadataCandidate(
        source_type=source_type.value,
        raw_payload=raw,
        **{k: v for k, v in parsed.items() if v is not None},
    )
    db.add(candidate)
    db.flush()
    return candidate


def _candidate_dict(c: MetadataCandidate) -> dict:
    return {
        "title_norm": c.title_norm,
        "year": c.year,
        "cast_json": c.cast_json,
        "external_ids_json": c.external_ids_json,
        "source_type": c.source_type,
        "poster_url": c.poster_url,
    }


def _content_dict(c: Content) -> dict:
    return {
        "title": c.title,
        "production_year": c.production_year,
        "cast": None,
        "external_ids": None,
        "poster_url": None,
    }


def _process_candidate(
    content_id: int,
    content: Content,
    candidate: MetadataCandidate,
    db: Session,
    result: EnrichResult,
) -> None:
    match_result = compute_match_score(_candidate_dict(candidate), _content_dict(content))
    classification = classify_match(match_result.score)

    if classification == "drop":
        return

    existing_edge = (
        db.query(MatchEdge)
        .filter(
            MatchEdge.candidate_id == candidate.id,
            MatchEdge.content_id == content_id,
        )
        .first()
    )
    if not existing_edge:
        edge = MatchEdge(
            candidate_id=candidate.id,
            content_id=content_id,
            score=match_result.score,
            reasons_json=match_result.reasons,
            sub_scores_json=vars(match_result.breakdown),
            decided=(classification == "auto"),
            decided_at=datetime.now(timezone.utc) if classification == "auto" else None,
            decided_by="system" if classification == "auto" else None,
        )
        db.add(edge)
        db.flush()
        result.match_edges_created += 1

    _decompose_suggestions(content_id, candidate, match_result.score, db, result)


def _decompose_suggestions(
    content_id: int,
    candidate: MetadataCandidate,
    confidence: float,
    db: Session,
    result: EnrichResult,
) -> None:
    """candidate 에서 필드별 FieldSuggestion 생성 (중복 skip)."""
    field_values: dict[str, Any] = {
        "synopsis": candidate.synopsis,
        "poster": candidate.poster_url,
        "cast": candidate.cast_json,
        "director": candidate.director_json,
        "primary_genre": candidate.genre_json,
        "external_id": candidate.external_ids_json,
    }
    for field_name, value in field_values.items():
        if value is None:
            continue
        exists = (
            db.query(FieldSuggestion)
            .filter(
                FieldSuggestion.content_id == content_id,
                FieldSuggestion.field_name == field_name,
                FieldSuggestion.source_candidate_id == candidate.id,
            )
            .first()
        )
        if exists:
            continue
        db.add(FieldSuggestion(
            content_id=content_id,
            field_name=field_name,
            value_json=value,
            source_candidate_id=candidate.id,
            source_type=candidate.source_type,
            confidence=confidence,
            status="pending",
        ))
        result.suggestions_created += 1
    db.flush()
