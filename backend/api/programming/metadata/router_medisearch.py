"""MediSearch 온디맨드 콘텐츠 메타+Facet 라우터.

엔드포인트 prefix: /api/programming/metadata

  # content-bound (편집 패널)
  POST /contents/{content_id}/medisearch/search
  GET  /contents/{content_id}/medisearch/facet

  # free-text (WebSearch 페이지)
  POST /medisearch/search    — 빠른 레인: enrich + 저장 facet 즉시
  POST /medisearch/evaluate  — 느린 레인: facet 평가 + tmdb 캐시 저장
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from shared.config import settings
from shared.database import get_db

router = APIRouter()
logger = logging.getLogger(__name__)

_MEDISEARCH_ENRICH_PATH = "/api/movies/enrich"
_MEDISEARCH_EVALUATE_PATH = "/api/movies/evaluate"


# ── 스키마 ──────────────────────────────────────────────────────────────────

class MediSearchRequest(BaseModel):
    include_facet: bool = True
    force_facet: bool = False


class MediSearchFacetInfo(BaseModel):
    origin: str                             # "stored" | "fresh" | "none"
    facet_json: Optional[dict[str, Any]] = None
    source_count: Optional[int] = None
    confidence: Optional[float] = None
    evaluated_at: Optional[datetime] = None


class MediSearchResult(BaseModel):
    meta_source_id: int
    query: str
    metadata: dict[str, Any]
    provenance: dict[str, Any]
    sources_detail: list[dict[str, Any]]
    facet: MediSearchFacetInfo


# free-text 전용 스키마
class MediSearchFreeRequest(BaseModel):
    title: str
    production_year: Optional[int] = None
    content_type: Optional[str] = None
    original_title: Optional[str] = None


class MediSearchEvaluateRequest(MediSearchFreeRequest):
    tmdb_id: Optional[int] = None
    imdb_id: Optional[str] = None


class MediSearchFreeResult(BaseModel):
    query: str
    metadata: dict[str, Any]
    provenance: dict[str, Any]
    sources_detail: list[dict[str, Any]]
    resolved_tmdb_id: Optional[int] = None
    resolved_imdb_id: Optional[str] = None
    facet: MediSearchFacetInfo


# ── 순수 헬퍼: MediSearch HTTP 호출 ─────────────────────────────────────────

def _call_medisearch_enrich(payload: dict) -> dict:
    """POST /api/movies/enrich 호출. HTTPException 발생 시 502 변환."""
    url = f"{settings.MEDISEARCH_URL.rstrip('/')}{_MEDISEARCH_ENRICH_PATH}"
    try:
        with httpx.Client(timeout=min(settings.MEDISEARCH_TIMEOUT_S, 120)) as client:
            resp = client.post(url, json=payload)
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        logger.warning("[medisearch] enrich network error: %s", exc)
        raise HTTPException(status_code=502, detail=f"MediSearch 연결 실패: {exc}")

    if not resp.is_success:
        raise HTTPException(
            status_code=502,
            detail=f"MediSearch HTTP {resp.status_code}: {resp.text[:200]}",
        )
    return resp.json()


def _call_medisearch_evaluate_raw(payload: dict) -> dict | None:
    """POST /api/movies/evaluate 호출. 실패 시 None 반환(예외 안 냄)."""
    url = f"{settings.MEDISEARCH_URL.rstrip('/')}{_MEDISEARCH_EVALUATE_PATH}"
    evaluate_payload = {k: v for k, v in {
        "title": payload.get("title"),
        "production_year": payload.get("production_year"),
        "tmdb_id": payload.get("tmdb_id"),
        "imdb_id": payload.get("imdb_id"),
        "original_title": payload.get("original_title"),
        "require_namu": False,
    }.items() if v is not None}

    try:
        with httpx.Client(timeout=settings.MEDISEARCH_TIMEOUT_S) as client:
            resp = client.post(url, json=evaluate_payload)
        if not resp.is_success:
            logger.warning("[medisearch] evaluate → HTTP %d", resp.status_code)
            return None
        return resp.json()
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        logger.warning("[medisearch] evaluate timeout/network: %s", exc)
        return None


# ── 순수 헬퍼: facet 조회 ────────────────────────────────────────────────────

def _load_stored_facet_by_tmdb(tmdb_id: int, db: Session) -> MediSearchFacetInfo:
    """TmdbMovieFacet 캐시에서 저장된 facet 조회."""
    from api.programming.metadata.models.tmdb_cache import TmdbMovieFacet

    facet_row = (
        db.query(TmdbMovieFacet)
        .filter(TmdbMovieFacet.tmdb_id == tmdb_id, TmdbMovieFacet.status == "success")
        .first()
    )
    if facet_row and facet_row.facet_json:
        return MediSearchFacetInfo(
            origin="stored",
            facet_json=facet_row.facet_json,
            source_count=facet_row.source_count,
            confidence=facet_row.confidence,
            evaluated_at=facet_row.evaluated_at,
        )
    return MediSearchFacetInfo(origin="none")


def _load_stored_facet(content, db: Session) -> MediSearchFacetInfo:
    """content 바인딩 저장 facet 조회 (ContentAIResult 1순위 → TmdbMovieFacet 2순위)."""
    from api.programming.metadata.models.external import ContentAIResult, AITaskType, ExternalMetaSource, ExternalSourceType

    # 1순위: content_ai_results(facet_analysis, is_final)
    ai_row = (
        db.query(ContentAIResult)
        .filter(
            ContentAIResult.content_id == content.id,
            ContentAIResult.task_type == AITaskType.facet_analysis,
            ContentAIResult.is_final.is_(True),
        )
        .order_by(ContentAIResult.processed_at.desc())
        .first()
    )
    if ai_row and ai_row.result_json:
        rj = ai_row.result_json
        facet_j = {k: v for k, v in rj.items() if k != "_meta"}
        meta = rj.get("_meta", {})
        return MediSearchFacetInfo(
            origin="stored",
            facet_json=facet_j or None,
            source_count=meta.get("source_count"),
            confidence=meta.get("confidence") or ai_row.quality_score,
            evaluated_at=ai_row.processed_at,
        )

    # 2순위: tmdb_movie_facets
    tmdb_src = (
        db.query(ExternalMetaSource)
        .filter(
            ExternalMetaSource.content_id == content.id,
            ExternalMetaSource.source_type == ExternalSourceType.tmdb,
        )
        .first()
    )
    if tmdb_src and tmdb_src.external_id:
        try:
            tmdb_id = int(tmdb_src.external_id)
        except (ValueError, TypeError):
            tmdb_id = None
        if tmdb_id:
            result = _load_stored_facet_by_tmdb(tmdb_id, db)
            if result.origin == "stored":
                return result

    return MediSearchFacetInfo(origin="none")


# ── 헬퍼: enrich 응답에서 tmdb_id / imdb_id 해석 ────────────────────────────

def _resolve_ids(metadata: dict) -> tuple[int | None, str | None]:
    """enrich metadata에서 tmdb_id, imdb_id 추출."""
    tmdb_id: int | None = None
    imdb_id: str | None = None

    raw_tmdb = metadata.get("tmdb_id")
    if raw_tmdb is not None:
        try:
            tmdb_id = int(raw_tmdb)
        except (ValueError, TypeError):
            pass

    raw_imdb = metadata.get("imdb_id") or metadata.get("imdbID")
    if raw_imdb:
        imdb_id = str(raw_imdb)

    return tmdb_id, imdb_id


# ── 헬퍼: ExternalMetaSource(medisearch) upsert ───────────────────────────

def _upsert_medisearch_source(content, metadata: dict, confidence: float | None, db: Session) -> int:
    from api.programming.metadata.models.external import ExternalMetaSource, ExternalSourceType

    existing = (
        db.query(ExternalMetaSource)
        .filter(
            ExternalMetaSource.content_id == content.id,
            ExternalMetaSource.source_type == ExternalSourceType.medisearch,
        )
        .first()
    )
    now = datetime.now(timezone.utc)
    if existing:
        existing.raw_json = metadata
        existing.match_confidence = confidence
        existing.matched_at = now
        db.commit()
        db.refresh(existing)
        return existing.id
    else:
        src = ExternalMetaSource(
            content_id=content.id,
            source_type=ExternalSourceType.medisearch,
            raw_json=metadata,
            match_confidence=confidence,
            matched_at=now,
        )
        db.add(src)
        db.commit()
        db.refresh(src)
        return src.id


# ── 헬퍼: MediSearch /evaluate → facet 저장 (content-bound) ──────────────

def _run_fresh_evaluate(content, payload: dict, db: Session) -> MediSearchFacetInfo:
    from sqlalchemy import update as sa_update
    from workers.tasks.facet_tasks import _decide_facet_outcome
    from api.programming.metadata.models.external import ContentAIResult, AITaskType

    data = _call_medisearch_evaluate_raw(payload)
    if data is None:
        return MediSearchFacetInfo(origin="none")

    status, _, source_count, confidence = _decide_facet_outcome(data)
    if status != "success":
        return MediSearchFacetInfo(origin="none")

    facet_json = data.get("facet", data)
    now = datetime.now(timezone.utc)

    db.execute(
        sa_update(ContentAIResult)
        .where(
            ContentAIResult.content_id == content.id,
            ContentAIResult.task_type == AITaskType.facet_analysis,
            ContentAIResult.is_final.is_(True),
        )
        .values(is_final=False)
        .execution_options(synchronize_session=False)
    )
    db.add(ContentAIResult(
        content_id=content.id,
        engine="medisearch",
        task_type=AITaskType.facet_analysis,
        result_json={**facet_json, "_meta": {
            "tmdb_id": payload.get("tmdb_id"),
            "confidence": confidence,
            "engine": "medisearch",
            "evaluated_at": now.isoformat(),
        }},
        quality_score=confidence,
        is_final=True,
    ))
    db.commit()

    return MediSearchFacetInfo(
        origin="fresh",
        facet_json=facet_json,
        source_count=source_count,
        confidence=confidence,
        evaluated_at=now,
    )


# ── 헬퍼: content → 검색 파라미터 ───────────────────────────────────────────

def _build_search_payload(content, db: Session) -> dict:
    from api.programming.metadata.models.external import ExternalMetaSource, ExternalSourceType

    payload: dict = {"title": content.title}
    if content.original_title:
        payload["original_title"] = content.original_title
    if content.production_year:
        payload["production_year"] = content.production_year
    if content.content_type:
        ct = content.content_type.value if hasattr(content.content_type, "value") else str(content.content_type)
        payload["content_type"] = ct if ct in ("movie", "series") else "movie"

    tmdb_src = (
        db.query(ExternalMetaSource)
        .filter(
            ExternalMetaSource.content_id == content.id,
            ExternalMetaSource.source_type == ExternalSourceType.tmdb,
        )
        .first()
    )
    if tmdb_src and tmdb_src.external_id:
        try:
            payload["tmdb_id"] = int(tmdb_src.external_id)
        except (ValueError, TypeError):
            pass
        raw = tmdb_src.raw_json or {}
        imdb_id = raw.get("imdb_id") or raw.get("imdbID")
        if imdb_id:
            payload["imdb_id"] = imdb_id

    return payload


# ── 엔드포인트: content-bound ────────────────────────────────────────────────

@router.post("/contents/{content_id}/medisearch/search", response_model=MediSearchResult)
def medisearch_search(
    content_id: int,
    req: MediSearchRequest,
    db: Session = Depends(get_db),
):
    """MediSearch /enrich 온디맨드 호출. 기본메타 결과를 ExternalMetaSource(medisearch)에 저장하고 반환."""
    from api.programming.metadata.models import Content

    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="content not found")

    payload = _build_search_payload(content, db)
    data = _call_medisearch_enrich(payload)

    metadata = data.get("metadata") or {}
    provenance = metadata.pop("_provenance", {}) if isinstance(metadata, dict) else {}
    sources_detail = data.get("sources_detail") or []
    confidence = metadata.get("confidence")
    query = data.get("movie_query") or content.title

    meta_source_id = _upsert_medisearch_source(content, metadata, confidence, db)

    facet_info = _load_stored_facet(content, db)
    if facet_info.origin == "none" and req.include_facet and req.force_facet:
        facet_info = _run_fresh_evaluate(content, payload, db)

    return MediSearchResult(
        meta_source_id=meta_source_id,
        query=query,
        metadata=metadata,
        provenance=provenance,
        sources_detail=sources_detail,
        facet=facet_info,
    )


@router.get("/contents/{content_id}/medisearch/facet", response_model=MediSearchFacetInfo)
def get_stored_facet(
    content_id: int,
    db: Session = Depends(get_db),
):
    """MediSearch 호출 없이 저장된 facet만 반환 (패널 최초 렌더용)."""
    from api.programming.metadata.models import Content

    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="content not found")

    return _load_stored_facet(content, db)


# ── 엔드포인트: free-text ────────────────────────────────────────────────────

@router.post("/medisearch/search", response_model=MediSearchFreeResult)
def medisearch_search_freetext(
    req: MediSearchFreeRequest,
    db: Session = Depends(get_db),
):
    """Free-text 빠른 레인: enrich 호출 → tmdb_id 해석 → 저장 facet 즉시 첨부.

    라이브 evaluate 호출 안 함 — facet은 캐시 있으면 origin=stored, 없으면 origin=none.
    """
    payload: dict = {"title": req.title}
    if req.production_year:
        payload["production_year"] = req.production_year
    if req.content_type:
        payload["content_type"] = req.content_type
    if req.original_title:
        payload["original_title"] = req.original_title

    data = _call_medisearch_enrich(payload)

    metadata = data.get("metadata") or {}
    provenance = metadata.pop("_provenance", {}) if isinstance(metadata, dict) else {}
    sources_detail = data.get("sources_detail") or []
    query = data.get("movie_query") or req.title

    resolved_tmdb_id, resolved_imdb_id = _resolve_ids(metadata)

    # 저장 facet 즉시 첨부 (라이브 호출 없음)
    facet_info = MediSearchFacetInfo(origin="none")
    if resolved_tmdb_id is not None:
        facet_info = _load_stored_facet_by_tmdb(resolved_tmdb_id, db)

    return MediSearchFreeResult(
        query=query,
        metadata=metadata,
        provenance=provenance,
        sources_detail=sources_detail,
        resolved_tmdb_id=resolved_tmdb_id,
        resolved_imdb_id=resolved_imdb_id,
        facet=facet_info,
    )


@router.post("/medisearch/evaluate", response_model=MediSearchFacetInfo)
def medisearch_evaluate_freetext(
    req: MediSearchEvaluateRequest,
    db: Session = Depends(get_db),
):
    """Free-text 느린 레인: facet 평가 + tmdb_movie_cache FK 존재 시 캐시 저장.

    후보 선택 시 FE에서 호출. tmdb_id가 있으면 TmdbMovieFacet에 upsert해
    다음 search 호출 시 origin=stored로 즉시 재사용 가능.
    """
    from workers.tasks.facet_tasks import _decide_facet_outcome, _upsert_tmdb_facet
    from api.programming.metadata.models.tmdb_cache import TmdbMovieCache

    payload: dict = {"title": req.title}
    if req.production_year:
        payload["production_year"] = req.production_year
    if req.tmdb_id:
        payload["tmdb_id"] = req.tmdb_id
    if req.imdb_id:
        payload["imdb_id"] = req.imdb_id
    if req.original_title:
        payload["original_title"] = req.original_title

    data = _call_medisearch_evaluate_raw(payload)
    if data is None:
        raise HTTPException(status_code=502, detail="MediSearch evaluate 실패")

    status, _, source_count, confidence = _decide_facet_outcome(data)
    if status != "success":
        raise HTTPException(status_code=422, detail=f"facet 평가 실패: status={status}")

    facet_json = data.get("facet", data)
    now = datetime.now(timezone.utc)

    # tmdb_id FK 존재 확인 후 캐시 저장
    if req.tmdb_id is not None:
        exists = db.query(TmdbMovieCache).filter(TmdbMovieCache.id == req.tmdb_id).first()
        if exists:
            _upsert_tmdb_facet(db, req.tmdb_id, "success",
                               facet_json=facet_json,
                               confidence=confidence,
                               source_count=source_count)
            logger.info("[medisearch] facet 캐시 저장 tmdb_id=%d", req.tmdb_id)
        else:
            logger.info("[medisearch] tmdb_id=%d not in cache, skip upsert", req.tmdb_id)

    return MediSearchFacetInfo(
        origin="fresh",
        facet_json=facet_json,
        source_count=source_count,
        confidence=confidence,
        evaluated_at=now,
    )
