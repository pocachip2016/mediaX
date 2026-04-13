"""
외부 메타 소스 및 AI 처리 결과 모델

테이블:
  - external_meta_sources : 외부 시스템별 원본 데이터 (TMDB/KOBIS/Watcha 등)
  - content_ai_results    : AI 엔진별·태스크별 처리 결과
"""

import enum

from sqlalchemy import Column, String, Integer, Float, Text, DateTime, Enum, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from shared.database import Base


class ExternalSourceType(str, enum.Enum):
    kobis = "kobis"
    tmdb = "tmdb"
    watcha = "watcha"
    netflix = "netflix"
    naver = "naver"
    daum = "daum"
    other = "other"


class AITaskType(str, enum.Enum):
    synopsis = "synopsis"   # 시놉시스 생성
    genre = "genre"         # 장르 분류
    tagging = "tagging"     # 감성·태그 분류
    rating = "rating"       # 시청등급 제안
    entity = "entity"       # 엔티티 추출 (인물/키워드)
    quality = "quality"     # 품질 평가


class ExternalMetaSource(Base):
    """
    외부 시스템 원본 메타 — 콘텐츠와 명시적 연결
    external_meta_cache(레거시)와 다르게 content_id FK로 직접 연결
    """
    __tablename__ = "external_meta_sources"

    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(Integer, ForeignKey("contents.id"), nullable=True, index=True)
    source_type = Column(Enum(ExternalSourceType, name="externalsourcetype"), nullable=False, index=True)
    external_id = Column(String(200), index=True)    # TMDB id, KOBIS movieCd 등
    title_on_source = Column(String(500))            # 외부 시스템의 원본 제목
    raw_json = Column(JSON)                          # 외부 API 응답 원본 보존
    match_confidence = Column(Float)                 # 매핑 신뢰도 0~1
    matched_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    content = relationship("Content", back_populates="external_sources")


class ContentAIResult(Base):
    """
    AI 처리 결과 — 엔진별·태스크별 분리 저장
    is_final=True인 레코드가 현재 사용 중인 결과
    """
    __tablename__ = "content_ai_results"

    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(Integer, ForeignKey("contents.id"), nullable=False, index=True)
    engine = Column(String(100), nullable=False, index=True)   # "llama3.2:3b", "gpt-4o", "gemini-1.5"
    task_type = Column(Enum(AITaskType, name="aitasktype"), nullable=False, index=True)
    result_json = Column(JSON)          # 엔진 응답 원본
    quality_score = Column(Float)       # 이 결과의 품질 스코어
    is_final = Column(Boolean, default=False, index=True)  # 현재 채택된 결과 여부
    error_message = Column(Text)        # 처리 실패 시 에러 메시지
    processed_at = Column(DateTime(timezone=True), server_default=func.now())

    content = relationship("Content", back_populates="ai_results")
