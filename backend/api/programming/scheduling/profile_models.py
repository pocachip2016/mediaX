from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.sql import func

from shared.database import Base


class ContentSemanticProfile(Base):
    """ingest-time Content Understanding Profile (CUP).

    시놉시스 임베딩 + LLM facet 추출 결과를 1회 저장.
    read-time AI 추천은 이 프로파일을 참조해 cosine + facet 매칭만 수행.

    nullable 슬롯:
      - embed_dialogue: 자막/STT 확보 시 채움 (현재 미보유)
      - embed_visual:   포스터/키프레임 CLIP 확보 시 채움
    """
    __tablename__ = "content_semantic_profiles"

    id          = Column(Integer, primary_key=True, index=True)
    content_id  = Column(Integer, ForeignKey("contents.id", ondelete="CASCADE"), nullable=False)

    # facet 통제어휘 (scheduling/facets.py VOCAB 준수)
    facets      = Column(JSON, nullable=True)
    # 핵심 키워드 list[str]
    keywords    = Column(JSON, nullable=True)

    # 시놉시스 임베딩 벡터 list[float] (bge-m3 1024-dim)
    embed_synopsis  = Column(JSON, nullable=True)
    # dialogue 임베딩 — 자막/STT 확보 시 (현재 null)
    embed_dialogue  = Column(JSON, nullable=True)
    # visual 임베딩 — CLIP 확보 시 (현재 null)
    embed_visual    = Column(JSON, nullable=True)

    # 1~2문장 로컬 LLM 증류 요약
    essence     = Column(Text, nullable=True)
    # 기여 소스 추적 (합법성 감사 + confidence 가중)
    # {"synopsis": "cp", "facets": "ollama:llama3.2:3b", "keywords": "ollama", "web_search": "brave"}
    provenance  = Column(JSON, nullable=True)

    # 재계산 트리거 키 ("ollama:bge-m3:1.0" 등)
    model_version   = Column(String(80), nullable=True)
    computed_at     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("content_id", name="uq_content_semantic_profile_content_id"),
    )
