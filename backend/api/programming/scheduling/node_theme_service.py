"""node_theme_service.py — ProgrammingNode theme 임베딩 precompute 헬퍼.

ingest/edit-time에 노드의 편성 의도 텍스트를 bge-m3로 임베딩해
ProgrammingNode.embed_theme에 캐시한다.
Tier2 매칭(match_service)이 매 추천마다 재임베딩하지 않도록 하는 것이 목적.

CUP(ContentSemanticProfile)과 대칭 구조:
  콘텐츠 측: profile_service.build_profile   → content_semantic_profiles.embed_synopsis
  노드 측:   node_theme_service.build_node_theme_embedding → programming_nodes.embed_theme
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from api.programming.metadata.llm.ollama import OllamaEmbeddingsProvider
from api.programming.scheduling.models import ProgrammingNode
from api.programming.scheduling.profile_service import MODEL_VERSION  # noqa: F401 — 단일 출처


def compose_theme_text(node: ProgrammingNode) -> str:
    """노드의 편성 의도 텍스트를 공백으로 결합.

    우선순위: name → headline_copy → sub_copy → theme_features(facet 평탄화).
    None/빈 값 스킵. setting era/place도 풀어 포함.
    """
    parts: list[str] = []

    for field in ("name", "headline_copy", "sub_copy"):
        val = getattr(node, field, None)
        if val and val.strip():
            parts.append(val.strip())

    theme_features = getattr(node, "theme_features", None)
    if isinstance(theme_features, dict):
        for k, v in theme_features.items():
            if k == "setting" and isinstance(v, dict):
                for sub in v.values():
                    if isinstance(sub, list):
                        parts.extend(s for s in sub if isinstance(s, str) and s)
            elif isinstance(v, list):
                parts.extend(s for s in v if isinstance(s, str) and s)
            elif isinstance(v, str) and v:
                parts.append(v)

    return " ".join(parts)


async def build_node_theme_embedding(
    db: Session,
    node_id: int,
    *,
    force: bool = False,
) -> list[float] | None:
    """ProgrammingNode.embed_theme 생성/반환 (멱등).

    - force=False: 캐시 존재 시 즉시 반환(재임베딩 안 함).
    - force=True: 노드 편집 후 강제 갱신 시 사용.
    - 빈 theme 텍스트 or Ollama 미응답: None 반환, 캐시 미갱신.
    """
    node = db.query(ProgrammingNode).filter(ProgrammingNode.id == node_id).first()
    if node is None:
        return None

    if node.embed_theme and not force:
        return node.embed_theme

    text = compose_theme_text(node)
    if not text:
        return None

    vec = await OllamaEmbeddingsProvider().embed(text)
    if not vec:
        return None

    node.embed_theme = vec
    db.flush()
    return vec
