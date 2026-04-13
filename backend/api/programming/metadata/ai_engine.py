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

import json
import re
import logging
import httpx
from sqlalchemy.orm import Session

from shared.config import settings
from api.programming.metadata.schemas import AIGenerateRequest, AIGenerateResponse
from api.programming.metadata.llm import get_provider_chain

logger = logging.getLogger(__name__)

AI_ENGINE = getattr(settings, "AI_ENGINE", "gemini")

# 장르 목록 (지니TV 표준 코드 기반)
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
        "당신은 한국 OTT 플랫폼 지니TV의 콘텐츠 메타데이터 전문가입니다. "
        "주어진 콘텐츠 정보를 바탕으로 정확한 메타데이터를 JSON 형식으로 생성하세요."
    )

    user_prompt = f"""다음 콘텐츠의 메타데이터를 생성해 주세요.

제목: {req.title}
제작연도: {req.production_year or '미상'}
CP사: {req.cp_name or '미상'}
기존 시놉시스: {req.cp_synopsis or '없음'}

아래 JSON 형식으로만 응답하세요:
```json
{{
  "synopsis": "200자 이상의 상세 시놉시스",
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

    synopsis = ai_data.get("synopsis", "")
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

async def process_content_ai(content_id: int, db: Session):
    """
    Celery 태스크에서 호출 — 저장된 콘텐츠 AI 처리 후 DB 업데이트.
    품질 스코어 기준 status 자동 설정:
      90+   → approved
      70~89 → review
      <70   → review (AI 보강 제안)
    ContentAIResult에 사용된 엔진 기록.
    """
    from datetime import datetime
    from api.programming.metadata.models import (
        Content, ContentMetadata, ContentStatus,
        ContentAIResult, AITaskType,
    )

    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise ValueError(f"Content {content_id} not found")

    # status → processing
    content.status = ContentStatus.processing
    db.commit()

    meta = content.metadata_record
    if not meta:
        meta = ContentMetadata(content_id=content_id)
        db.add(meta)
        db.flush()

    req = AIGenerateRequest(
        title=content.title,
        production_year=content.production_year,
        cp_name=content.cp_name,
        cp_synopsis=meta.cp_synopsis,
    )

    result, used_engine = await _generate_metadata_with_engine(req, db)

    # ContentMetadata 업데이트
    meta.ai_synopsis = result.synopsis
    meta.ai_genre_primary = result.genre_primary
    meta.ai_genre_secondary = result.genre_secondary
    meta.ai_mood_tags = result.mood_tags
    meta.ai_rating_suggestion = result.rating_suggestion
    meta.quality_score = result.quality_score
    meta.score_breakdown = {}
    meta.kobis_data = result.kobis_match
    meta.tmdb_data = result.tmdb_match
    meta.ai_processed_at = datetime.utcnow()

    if result.kobis_match and result.kobis_match.get("movieCd"):
        meta.kobis_movie_cd = result.kobis_match["movieCd"]
    if result.tmdb_match and result.tmdb_match.get("id"):
        meta.tmdb_id = result.tmdb_match["id"]

    # 품질 스코어 기반 status 결정
    if result.quality_score >= 90:
        content.status = ContentStatus.approved
    else:
        content.status = ContentStatus.review

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
