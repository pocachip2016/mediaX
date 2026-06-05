"""
1.1.2 AI 처리 엔진 — 멀티 프로바이더 LLM 연동

지원 엔진 (AI_ENGINE 환경변수로 선택):
  gemini  → Google Gemini 1.5 Flash (기본값)
  groq    → llama-3.3-70b-versatile
  ollama  → llama3.2:3b 로컬

폴백: 지정 엔진 실패 → 다음 엔진 자동 시도
외부 API: KOBIS + TMDB 병렬 조회 (키 없으면 skip)
품질 스코어: 0~100점 (90+ 자동승인, 70~89 검수큐)
"""

import hashlib
import json
import re
import logging
from datetime import datetime, timedelta
import httpx
from sqlalchemy.orm import Session

from shared.config import settings
from api.programming.metadata.schemas import AIGenerateRequest, AIGenerateResponse
from api.programming.metadata.llm import get_provider_chain

logger = logging.getLogger(__name__)


def _upsert_external_source(db: Session, content_id: int, source_type, external_id: str, raw_json: dict):
    """ExternalMetaSource 행 upsert — (content_id, source_type) 기준."""
    from api.programming.metadata.models import ExternalMetaSource
    existing = (
        db.query(ExternalMetaSource)
        .filter(
            ExternalMetaSource.content_id == content_id,
            ExternalMetaSource.source_type == source_type,
        )
        .first()
    )
    if existing:
        existing.external_id = external_id
        existing.raw_json = raw_json
        existing.matched_at = datetime.utcnow()
    else:
        db.add(ExternalMetaSource(
            content_id=content_id,
            source_type=source_type,
            external_id=external_id,
            raw_json=raw_json,
            matched_at=datetime.utcnow(),
        ))

def _cached_web_search(query: str, db: Session, ttl_days: int = 7) -> list:
    """Brave/SerpAPI 웹 검색 — DB 캐시 우선, 키 없으면 빈 리스트 반환."""
    from api.programming.metadata.models.tmdb_cache import WebSearchCache

    query_hash = hashlib.sha256(query.encode()).hexdigest()
    now = datetime.utcnow()

    cached = db.query(WebSearchCache).filter(WebSearchCache.query_hash == query_hash).first()
    if cached and cached.expires_at > now:
        return cached.results_json or []

    results: list = []
    source = "none"

    brave_key = getattr(settings, "BRAVE_SEARCH_API_KEY", "")
    serp_key = getattr(settings, "SERP_API_KEY", "")

    if brave_key:
        try:
            resp = httpx.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"Accept": "application/json", "X-Subscription-Token": brave_key},
                params={"q": query, "count": 5},
                timeout=10.0,
            )
            results = resp.json().get("web", {}).get("results", [])
            source = "brave"
        except Exception as exc:
            logger.warning(f"[web_search] Brave 실패: {exc}")
    elif serp_key:
        try:
            resp = httpx.get(
                "https://serpapi.com/search",
                params={"q": query, "num": 5, "api_key": serp_key},
                timeout=10.0,
            )
            results = resp.json().get("organic_results", [])
            source = "serp"
        except Exception as exc:
            logger.warning(f"[web_search] SerpAPI 실패: {exc}")

    expires_at = now + timedelta(days=ttl_days if source != "none" else 1)
    if cached:
        cached.query = query
        cached.source = source
        cached.results_json = results
        cached.fetched_at = now
        cached.expires_at = expires_at
    else:
        db.add(WebSearchCache(
            query_hash=query_hash,
            query=query,
            source=source,
            results_json=results,
            expires_at=expires_at,
        ))
    db.flush()
    return results


AI_ENGINE = getattr(settings, "AI_ENGINE", "gemini")

# 장르 목록 (표준 코드 기반)
GENRES = [
    "액션", "드라마", "코미디", "로맨스", "스릴러", "공포", "SF", "판타지",
    "애니메이션", "다큐멘터리", "예능", "키즈", "교육", "스포츠", "음악",
    "역사", "범죄", "미스터리", "어드벤처", "전쟁",
]

MOOD_TAGS = [
    "따뜻한", "긴장감", "가족과함께", "심야감성", "액션몰입", "힐링",
    "웃음보장", "눈물주의", "반전있음", "실화기반", "청춘", "성장",
    "복수극", "사랑이야기", "인간드라마",
]

RATING_OPTIONS = ["전체관람가", "12세이상관람가", "15세이상관람가", "청소년관람불가"]


# ── 폴백 체인 핵심 함수 ────────────────────────────────────

async def _call_with_fallback(prompt: str, system: str = "") -> tuple[str, str]:
    """
    AI_ENGINE 설정 기준으로 프로바이더 체인 시도.
    반환: (응답 텍스트, 실제 사용된 engine_name)
    모든 엔진 실패 시 ValueError raise.
    """
    chain = get_provider_chain(AI_ENGINE)
    last_exc: Exception | None = None

    for ProviderClass in chain:
        try:
            provider = ProviderClass()
            text = await provider.generate(prompt, system)
            logger.info(f"[ai_engine] 엔진 사용: {provider.engine_name}")
            return text, provider.engine_name
        except Exception as exc:
            logger.warning(
                f"[ai_engine] {ProviderClass.__name__} 실패 → 다음 엔진으로 폴백: {exc}"
            )
            last_exc = exc

    raise ValueError(f"모든 LLM 엔진 실패: {last_exc}")


async def call_ollama(prompt: str, system: str = "") -> str:
    """
    하위호환용 — OllamaProvider 직접 호출.
    workers/tasks/metadata.py 등 외부 코드에서 직접 import 시 사용.
    """
    from api.programming.metadata.llm.ollama import OllamaProvider
    provider = OllamaProvider()
    return await provider.generate(prompt, system)


# ── JSON 파싱 유틸 ────────────────────────────────────────

def _extract_json(text: str) -> dict:
    """LLM 응답에서 JSON 블록 추출"""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError("JSON을 파싱할 수 없습니다")


# ── 품질 스코어 ───────────────────────────────────────────

def _calculate_quality_score(
    title: str,
    synopsis: str,
    genre: str,
    tags: list[str],
    kobis_match: dict | None,
    tmdb_match: dict | None,
) -> tuple[float, dict]:
    """
    콘텐츠 메타 완성도 점수 (0~100). 외부 후보와의 동일성 점수(match_score, 0~1)와 다름.
    동일성 비교: api.meta_core.scoring.compute_match_score 참조.

    엔진 E — 품질 스코어 산정 (0~100점)
      - 시놉시스 길이/완성도  : 30점
      - 장르 분류 완성도       : 20점
      - 태그 수                : 15점
      - 외부 메타 매핑 성공    : 20점
      - 기본 필드 충족률       : 15점
    """
    breakdown = {}

    syn_len = len(synopsis or "")
    if syn_len >= 200:
        syn_score = 30
    elif syn_len >= 100:
        syn_score = 20
    elif syn_len >= 50:
        syn_score = 10
    else:
        syn_score = 0
    breakdown["synopsis_quality"] = syn_score

    genre_score = 20 if genre else 0
    breakdown["genre_confidence"] = genre_score

    tag_count = len(tags or [])
    tag_score = min(15, tag_count * 3)
    breakdown["tag_coverage"] = tag_score

    ext_score = 0
    if kobis_match:
        ext_score += 10
    if tmdb_match:
        ext_score += 10
    breakdown["external_meta"] = ext_score

    field_score = 15 if title else 0
    breakdown["field_coverage"] = field_score

    total = syn_score + genre_score + tag_score + ext_score + field_score
    return round(float(total), 1), breakdown


# 기본 메타 완성도 배점 (합 100) — 외부 매핑 성공 여부가 아니라 '핵심 필드가 채워졌는지' 기준
_COMPLETENESS_WEIGHTS = {
    "title": 10, "genre": 14, "cast": 12, "director": 12,
    "country": 10, "production_year": 10, "runtime": 10,
}  # synopsis(22)는 길이 tier로 별도 가산


def recompute_quality_score(db: Session, content_id: int) -> float | None:
    """콘텐츠의 **기본 메타 필드 완성도**(0~100) 기준으로 quality_score 재계산 → ContentMetadata 갱신.

    설계 원칙: 외부 매핑(TMDB/KOBIS/KMDB) 성공 여부가 아니라 **핵심 메타가 실제로 채워졌는지**가 기준.
    매핑이 없어도 대부분의 필드가 채워지면 임계값을 통과하도록 완성도 가중치를 둔다.
    (AI 생성 경로의 _calculate_quality_score(외부매핑 20점 포함)와 다른 축 — 파이프라인 autofill 후 점수화 용도.)
    score_breakdown은 resolve_metadata가 소스 출처맵으로 사용하므로 건드리지 않고 quality_score만 기록.

    배점(합 100): synopsis 22(길이 tier) / genre 14 / cast 12 / director 12 /
                  country 10 / production_year 10 / runtime 10 / title 10
    """
    from api.programming.metadata.models.content import Content, ContentMetadata, ContentType
    from api.programming.metadata.models.person import CreditRole

    content = (
        db.query(Content)
        .filter(Content.id == content_id, Content.is_deleted.is_(False))
        .first()
    )
    if not content:
        return None
    meta = content.metadata_record
    if meta is None:
        meta = ContentMetadata(content_id=content_id, quality_score=0.0)
        db.add(meta)
        db.flush()

    w = _COMPLETENESS_WEIGHTS
    score = 0.0

    if content.title:
        score += w["title"]

    # synopsis — 길이 tier (최대 22)
    synopsis = meta.ai_synopsis or meta.cp_synopsis or meta.final_synopsis or meta.synopsis_ko or ""
    syn_len = len(synopsis)
    if syn_len >= 200:
        score += 22
    elif syn_len >= 100:
        score += 16
    elif syn_len >= 50:
        score += 8
    elif syn_len > 0:
        score += 4

    # genre — meta 문자열 또는 ContentGenre 관계 존재
    if (meta and (meta.final_genre or meta.ai_genre_primary or meta.cp_genre)) or len(content.genres) > 0:
        score += w["genre"]

    # cast / director — ContentCredit 관계 (season/episode는 조상 상속 폴백)
    roles = {cc.role for cc in content.credits}
    has_actor = CreditRole.actor in roles
    has_director = CreditRole.director in roles

    if not has_actor or not has_director:
        if content.content_type in (ContentType.season, ContentType.episode):
            from api.programming.metadata.inheritance import resolve_inherited_metadata
            inh = resolve_inherited_metadata(content, db) or {}
            if not has_actor and "cast_credits" in inh:
                has_actor = True
            if not has_director and "director_credits" in inh:
                has_director = True

    if has_actor:
        score += w["cast"]
    if has_director:
        score += w["director"]

    # Content 직접 필드
    if content.country:
        score += w["country"]
    if content.production_year:
        score += w["production_year"]
    if content.runtime_minutes:
        score += w["runtime"]

    score = round(score, 1)
    meta.quality_score = score
    db.add(meta)
    db.flush()
    return score


# ── 메타 생성 내부 함수 (엔진명 포함 반환) ─────────────────

async def _generate_metadata_with_engine(
    req: AIGenerateRequest,
    db: Session,
) -> tuple[AIGenerateResponse, str]:
    """
    내부용 — (AIGenerateResponse, 사용된 engine_name) 반환.
    process_content_ai에서 ContentAIResult 기록 시 사용.
    """
    system_prompt = (
        "당신은 한국 VOD 플랫폼의 콘텐츠 메타데이터 전문가입니다. "
        "주어진 콘텐츠 정보를 바탕으로 정확한 메타데이터를 JSON 형식으로 생성하세요."
    )

    user_prompt = f"""다음 콘텐츠의 메타데이터를 생성해 주세요.

제목: {req.title}
제작연도: {req.production_year or '미상'}
CP사: {req.cp_name or '미상'}
기존 시놉시스: {req.cp_synopsis or '없음'}

아래 JSON 형식으로만 응답하세요 (synopsis는 실제 줄거리를 200자 이상 작성):
```json
{{
  "synopsis": "실제 줄거리 내용",
  "genre_primary": "{' | '.join(GENRES[:10])} 중 하나",
  "genre_secondary": "{' | '.join(GENRES[10:])} 중 하나 또는 null",
  "mood_tags": ["태그1", "태그2", "태그3"],
  "rating_suggestion": "{' | '.join(RATING_OPTIONS)} 중 하나"
}}
```

mood_tags는 다음 중에서 3~5개 선택: {', '.join(MOOD_TAGS)}"""

    try:
        raw_response, used_engine = await _call_with_fallback(user_prompt, system_prompt)
    except ValueError as e:
        logger.error(f"[ai_engine] 모든 엔진 실패: {e}")
        raw_response = ""
        used_engine = "none"

    try:
        ai_data = _extract_json(raw_response)
    except (ValueError, json.JSONDecodeError):
        ai_data = {
            "synopsis": f"{req.title}의 시놉시스를 생성하지 못했습니다.",
            "genre_primary": "드라마",
            "genre_secondary": None,
            "mood_tags": [],
            "rating_suggestion": "15세이상관람가",
        }

    _SYNOPSIS_PLACEHOLDERS = {"200자 이상의 상세 시놉시스", "실제 줄거리 내용"}
    synopsis = ai_data.get("synopsis", "")
    if synopsis in _SYNOPSIS_PLACEHOLDERS:
        synopsis = ""
    genre_primary = ai_data.get("genre_primary", "")
    genre_secondary = ai_data.get("genre_secondary")
    mood_tags = ai_data.get("mood_tags", [])
    rating = ai_data.get("rating_suggestion", "15세이상관람가")

    kobis_match, tmdb_match = await _fetch_external_meta(req.title, req.production_year)

    quality_score, score_breakdown = _calculate_quality_score(
        req.title, synopsis, genre_primary, mood_tags, kobis_match, tmdb_match
    )

    return AIGenerateResponse(
        synopsis=synopsis,
        genre_primary=genre_primary,
        genre_secondary=genre_secondary,
        mood_tags=mood_tags,
        rating_suggestion=rating,
        quality_score=quality_score,
        kobis_match=kobis_match,
        tmdb_match=tmdb_match,
    ), used_engine


async def generate_metadata_ollama(
    req: AIGenerateRequest,
    db: Session,
) -> AIGenerateResponse:
    """
    실시간 메타 AI 생성 (화면 3 — /generate 엔드포인트).
    하위호환 시그니처 유지: engine_name 버림.
    """
    result, _ = await _generate_metadata_with_engine(req, db)
    return result


# ── Celery 태스크용 AI 처리 ───────────────────────────────

def _get_external_data_from_db(
    content_id: int, db: Session
) -> tuple[dict | None, dict | None]:
    """enrich 단계에서 저장된 KOBIS/TMDB ExternalMetaSource raw_json 조회."""
    from api.programming.metadata.models.external import ExternalMetaSource, ExternalSourceType
    kobis = (
        db.query(ExternalMetaSource)
        .filter(
            ExternalMetaSource.content_id == content_id,
            ExternalMetaSource.source_type == ExternalSourceType.kobis,
        )
        .first()
    )
    tmdb = (
        db.query(ExternalMetaSource)
        .filter(
            ExternalMetaSource.content_id == content_id,
            ExternalMetaSource.source_type == ExternalSourceType.tmdb,
        )
        .first()
    )
    return (kobis.raw_json if kobis else None, tmdb.raw_json if tmdb else None)


async def process_content_ai(
    content_id: int,
    db: Session,
    *,
    auto_chain: bool = True,
    advance_to_review: bool = True,
    auto_approve: bool = True,
    score_threshold: int = 90,
):
    """
    AI 처리 단계 (ADR-007 ③단계) — enrich 완료 후 호출.

    status 전이:
      enriched → ai  (항상)
      auto_chain=True 일 때만 ai 이후 자동 전이 (단계별 게이트, ADR-009):
        advance_to_review(검수 s3) False → ai 에 머무름
        advance_to_review True:
          auto_approve(승인 s4) True & score ≥ threshold → approved
          그 외 → review

    외부 메타 조회 없음 — enrich 단계에서 저장된 ExternalMetaSource 활용.
    """
    from api.programming.metadata.models import (
        Content, ContentMetadata, ContentStatus,
        ContentAIResult, AITaskType,
    )
    from api.programming.metadata.models.content import PipelineStage, StageEventType
    from api.programming.metadata.stage_events import record_stage_event

    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise ValueError(f"Content {content_id} not found")

    if content.status != ContentStatus.enriched:
        logger.warning(
            "[ai] content_id=%d status=%s (expected enriched) — proceeding anyway",
            content_id, content.status,
        )

    record_stage_event(db, content_id, PipelineStage.S6_LLM_EXTRACT,
                       StageEventType.ENTERED, actor="system")

    meta = content.metadata_record
    if not meta:
        meta = ContentMetadata(content_id=content_id)
        db.add(meta)
        db.flush()

    kobis_match, tmdb_match = _get_external_data_from_db(content_id, db)

    req = AIGenerateRequest(
        title=content.title,
        production_year=content.production_year,
        cp_name=content.cp_name,
        cp_synopsis=meta.cp_synopsis,
    )

    result, used_engine = await _generate_metadata_with_engine(req, db)

    # ContentMetadata 업데이트 (외부 데이터는 DB에서 로드한 값 활용)
    meta.ai_synopsis = result.synopsis
    meta.ai_genre_primary = result.genre_primary
    meta.ai_genre_secondary = result.genre_secondary
    meta.ai_mood_tags = result.mood_tags
    meta.ai_rating_suggestion = result.rating_suggestion
    meta.quality_score = result.quality_score
    meta.score_breakdown = {}
    meta.tmdb_data = tmdb_match
    meta.ai_processed_at = datetime.utcnow()

    # enriched → ai
    content.status = ContentStatus.ai

    record_stage_event(db, content_id, PipelineStage.S6_LLM_EXTRACT,
                       StageEventType.COMPLETED, actor="system",
                       payload={"score": result.quality_score, "engine": used_engine})

    # 기존 is_final 레코드 해제
    db.query(ContentAIResult).filter(
        ContentAIResult.content_id == content_id,
        ContentAIResult.is_final == True,  # noqa: E712
    ).update({"is_final": False})

    # 새 AI 결과 기록
    db.add(ContentAIResult(
        content_id=content_id,
        engine=used_engine,
        task_type=AITaskType.synopsis,
        result_json={
            "synopsis": result.synopsis,
            "genre_primary": result.genre_primary,
            "genre_secondary": result.genre_secondary,
            "mood_tags": result.mood_tags,
            "rating_suggestion": result.rating_suggestion,
        },
        quality_score=result.quality_score,
        is_final=True,
        processed_at=datetime.utcnow(),
    ))

    # ai 이후 자동 전이 — 단계별 게이트(advance_to_review=검수 s3, auto_approve=승인 s4)
    if auto_chain and advance_to_review:
        if auto_approve and result.quality_score >= score_threshold:
            content.status = ContentStatus.approved
        else:
            content.status = ContentStatus.review

    db.commit()
    db.refresh(meta)
    return meta


# ── 외부 API 조회 ─────────────────────────────────────────

async def _fetch_external_meta(
    title: str, year: int | None
) -> tuple[dict | None, dict | None]:
    """KOBIS + TMDB 병렬 조회"""
    import asyncio
    kobis_task = asyncio.create_task(_fetch_kobis(title, year))
    tmdb_task = asyncio.create_task(_fetch_tmdb(title, year))
    kobis_result, tmdb_result = await asyncio.gather(
        kobis_task, tmdb_task, return_exceptions=True
    )
    return (
        kobis_result if isinstance(kobis_result, dict) else None,
        tmdb_result if isinstance(tmdb_result, dict) else None,
    )


async def _fetch_kobis(title: str, year: int | None) -> dict | None:
    if not settings.KOBIS_API_KEY:
        return None
    params = {
        "key": settings.KOBIS_API_KEY,
        "movieNm": title,
        "itemPerPage": "1",
    }
    if year:
        params["openStartDt"] = str(year)
        params["openEndDt"] = str(year)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "http://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieList.json",
                params=params,
            )
            data = resp.json()
            movies = data.get("movieListResult", {}).get("movieList", [])
            return movies[0] if movies else None
    except Exception:
        return None


async def _fetch_tmdb(title: str, year: int | None) -> dict | None:
    if not settings.TMDB_API_KEY:
        return None
    params = {
        "api_key": settings.TMDB_API_KEY,
        "query": title,
        "language": "ko-KR",
    }
    if year:
        params["year"] = year
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.themoviedb.org/3/search/movie",
                params=params,
            )
            data = resp.json()
            results = data.get("results", [])
            return results[0] if results else None
    except Exception:
        return None
