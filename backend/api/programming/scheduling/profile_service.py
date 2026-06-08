"""profile_service.py — ingest-time Content Understanding Profile 생성.

build_profile(db, content_id) 를 호출하면:
  1. 시놉시스 임베딩 (Ollama bge-m3)
  2. LLM facet 추출 (provider chain, 통제어휘 강제)
  3. WebSearch facet 병합 (파생만 저장, verbatim 금지)
  4. ContentSemanticProfile upsert (멱등, model_version 버전드)
"""
from __future__ import annotations

import asyncio
import json
import logging

from sqlalchemy.orm import Session

from api.programming.metadata.llm import get_provider_chain
from api.programming.metadata.llm.ollama import OllamaEmbeddingsProvider
from api.programming.metadata.models.content import Content, ContentMetadata
from api.programming.scheduling.facets import validate_facets
from api.programming.scheduling.profile_models import ContentSemanticProfile
from shared.config import settings

logger = logging.getLogger(__name__)

MODEL_VERSION = "ollama:bge-m3:1.0"

_FACET_SYSTEM = (
    "당신은 한국 VOD 편성 전문가입니다. "
    "아래 콘텐츠 정보를 읽고 JSON으로만 응답하세요. "
    "반드시 아래 통제어휘에서만 값을 선택해야 합니다. "
    "통제어휘 외 값은 절대 포함하지 마세요.\n"
    "{\n"
    '  "mood": ["경쾌|감성|긴장|따뜻|어두움|코믹|로맨틱|비장 중 해당하는 것"],\n'
    '  "occasion": ["주말|가족시청|심야|명절|연말|비오는날|몰아보기 중 해당하는 것"],\n'
    '  "audience": ["아동|청소년|성인|가족|시니어 중 해당하는 것"],\n'
    '  "tempo": ["느림|보통|빠름 중 하나"],\n'
    '  "tone": ["진지|가벼움|풍자|다큐멘터리 중 하나 이상"],\n'
    '  "themes": ["성장|복수|우정|가족|생존|범죄|사랑|전쟁|음모 중 해당하는 것"],\n'
    '  "setting": {"era": ["현대|시대극|근미래|중세|고대"], "place": ["한국|미국|일본|유럽|가상"]},\n'
    '  "keywords": ["핵심 키워드 최대 5개"],\n'
    '  "essence": "1~2문장 핵심 요약"\n'
    "}"
)


def _pick_synopsis(content: Content, metadata: ContentMetadata | None) -> str:
    """우선순위: final_synopsis → cp_synopsis → ai_synopsis → synopsis_ko → 제목."""
    if metadata:
        for field in ("final_synopsis", "cp_synopsis", "ai_synopsis"):
            val = getattr(metadata, field, None)
            if val and val.strip():
                return val.strip()
    if hasattr(content, "synopsis_ko") and content.synopsis_ko:
        return content.synopsis_ko.strip()
    return content.title or ""


async def _call_facet_llm(synopsis: str) -> dict:
    """LLM provider chain → JSON facets. 파싱 실패 시 빈 dict."""
    providers = get_provider_chain(getattr(settings, "AI_ENGINE", "gemini"))
    prompt = f"다음 콘텐츠 정보:\n{synopsis}\n\nJSON만 출력하세요."
    for ProviderClass in providers:
        try:
            provider = ProviderClass()
            raw = await provider.generate(prompt=prompt, system=_FACET_SYSTEM)
            # JSON 추출 (```json ... ``` 블록 포함 대비)
            raw = raw.strip()
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(raw[start:end])
        except Exception as e:
            logger.debug("facet LLM provider %s failed: %s", ProviderClass.__name__, e)
            continue
    return {}


def _heuristic_facets(content: Content, metadata: ContentMetadata | None) -> dict:
    """LLM 실패 시 구조메타로 최소 facets 생성."""
    out: dict = {}
    if metadata:
        genres = [g.genre_code.name_ko for g in getattr(metadata, "content_genres", []) if hasattr(g, "genre_code")]
        if genres:
            out["themes"] = genres[:3]
    return out


def _try_websearch_facets(title: str) -> dict:
    """WebSearch로 보강 — 파생(키워드) 만 반환, 원문 verbatim 저장 안 함."""
    try:
        from api.meta_core.web_search.factory import search_with_fallback
        from shared.quota_manager import QuotaManager

        qm = QuotaManager()
        if not qm.is_allowed("websearch_facet", 10):
            return {}
        results, _ = asyncio.run(search_with_fallback(f"{title} 영화 분위기 장르 키워드", quota_manager=qm))
        keywords = []
        for r in results[:3]:
            snippet = getattr(r, "snippet", "") or ""
            keywords += [w for w in snippet.split() if len(w) >= 2][:3]
        return {"keywords": list(dict.fromkeys(keywords))[:5]} if keywords else {}
    except Exception:
        return {}


async def build_profile(db: Session, content_id: int) -> ContentSemanticProfile | None:
    """ContentSemanticProfile 생성/갱신 (멱등, model_version 변경 시 재계산).

    Returns upserted profile or None on critical failure.
    """
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        return None

    metadata = db.query(ContentMetadata).filter(ContentMetadata.content_id == content_id).first()

    existing = (
        db.query(ContentSemanticProfile)
        .filter(ContentSemanticProfile.content_id == content_id)
        .first()
    )
    if existing and existing.model_version == MODEL_VERSION:
        return existing  # 이미 최신 버전

    synopsis = _pick_synopsis(content, metadata)
    provenance: dict = {}

    # 1. 시놉시스 임베딩
    embed_synopsis: list[float] = []
    if synopsis:
        embed_provider = OllamaEmbeddingsProvider()
        embed_synopsis = await embed_provider.embed(synopsis)
        if embed_synopsis:
            provenance["embed_synopsis"] = f"ollama:{OllamaEmbeddingsProvider.EMBED_MODEL}"

    # 2. LLM facet 추출
    raw_llm = await _call_facet_llm(synopsis) if synopsis else {}
    if raw_llm:
        provenance["facets"] = f"llm:{getattr(settings, 'AI_ENGINE', 'gemini')}"
    else:
        raw_llm = _heuristic_facets(content, metadata)
        if raw_llm:
            provenance["facets"] = "heuristic:genre"

    facets = validate_facets(raw_llm)
    keywords: list[str] = raw_llm.get("keywords", [])
    essence: str = raw_llm.get("essence", "")

    # 3. WebSearch 보강 (쿼터 허용 시)
    ws_extra = _try_websearch_facets(content.title or "")
    if ws_extra.get("keywords"):
        merged = list(dict.fromkeys(keywords + ws_extra["keywords"]))[:5]
        keywords = merged
        provenance["keywords_web"] = "web_search:derived"

    if embed_synopsis:
        provenance["synopsis_source"] = "cp_synopsis" if (metadata and metadata.cp_synopsis) else "fallback"

    # 4. Upsert
    if existing:
        existing.facets = facets
        existing.keywords = keywords
        existing.embed_synopsis = embed_synopsis or None
        existing.essence = essence or None
        existing.provenance = provenance
        existing.model_version = MODEL_VERSION
        from sqlalchemy.sql import func as sqlfunc
        existing.computed_at = sqlfunc.now()
        db.flush()
        return existing
    else:
        profile = ContentSemanticProfile(
            content_id=content_id,
            facets=facets,
            keywords=keywords,
            embed_synopsis=embed_synopsis or None,
            embed_dialogue=None,
            embed_visual=None,
            essence=essence or None,
            provenance=provenance,
            model_version=MODEL_VERSION,
        )
        db.add(profile)
        db.flush()
        return profile
