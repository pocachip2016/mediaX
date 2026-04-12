"""
1.1 메타데이터 AI 자동 분류 — SQLAlchemy 모델

테이블 구성:
  - contents          : 콘텐츠 원본 (단편/시리즈)
  - content_metadata  : AI 처리된 메타데이터 + 품질 스코어
  - cp_email_logs     : CP사 이메일 수신 이력
  - external_meta_cache : 외부 API(KOBIS/TMDB) 캐시
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime,
    Enum, ForeignKey, Boolean, JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from shared.database import Base


class ContentType(str, enum.Enum):
    movie = "movie"
    series = "series"
    episode = "episode"


class ContentStatus(str, enum.Enum):
    waiting = "waiting"        # CP 이메일 수신 후 대기
    processing = "processing"  # AI 처리 중
    review = "review"          # 담당자 검수 대기 (70~89점)
    approved = "approved"      # 등록 확정
    rejected = "rejected"      # 반려


class MetaSource(str, enum.Enum):
    cp = "cp"
    ai = "ai"
    kobis = "kobis"
    tmdb = "tmdb"
    manual = "manual"


class Content(Base):
    __tablename__ = "contents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False, index=True)
    original_title = Column(String(500))
    content_type = Column(Enum(ContentType), nullable=False, default=ContentType.movie)
    status = Column(Enum(ContentStatus), nullable=False, default=ContentStatus.waiting, index=True)

    # CP사 정보
    cp_name = Column(String(200), index=True)
    cp_email_id = Column(Integer, ForeignKey("cp_email_logs.id"), nullable=True)

    # 영상 기본 정보
    production_year = Column(Integer)
    runtime_minutes = Column(Integer)
    country = Column(String(100))

    # 시리즈 계층
    parent_id = Column(Integer, ForeignKey("contents.id"), nullable=True)
    season_number = Column(Integer)
    episode_number = Column(Integer)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    metadata_record = relationship("ContentMetadata", back_populates="content", uselist=False)
    cp_email = relationship("CpEmailLog", back_populates="contents")
    children = relationship("Content", foreign_keys=[parent_id], back_populates="parent")
    parent = relationship("Content", foreign_keys=[parent_id], back_populates="children", remote_side="Content.id")


class ContentMetadata(Base):
    __tablename__ = "content_metadata"

    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(Integer, ForeignKey("contents.id"), nullable=False, unique=True, index=True)

    # CP 원본 메타
    cp_synopsis = Column(Text)
    cp_genre = Column(String(200))
    cp_tags = Column(JSON)          # list[str]
    cp_cast = Column(JSON)          # list[{name, role}]
    cp_poster_url = Column(String(1000))

    # AI 생성 메타
    ai_synopsis = Column(Text)
    ai_genre_primary = Column(String(100))
    ai_genre_secondary = Column(String(100))
    ai_mood_tags = Column(JSON)     # list[str]  예: ["따뜻한", "가족과함께"]
    ai_cast = Column(JSON)
    ai_rating_suggestion = Column(String(20))  # 전체/12세/15세/청불

    # 외부 API 메타
    kobis_movie_cd = Column(String(20), index=True)
    kobis_data = Column(JSON)
    tmdb_id = Column(Integer, index=True)
    tmdb_data = Column(JSON)

    # 최종 확정 메타 (담당자 검수 후)
    final_synopsis = Column(Text)
    final_genre = Column(String(200))
    final_tags = Column(JSON)
    final_cast = Column(JSON)
    final_source = Column(Enum(MetaSource), default=MetaSource.ai)

    # 품질 스코어링
    quality_score = Column(Float, default=0.0, index=True)  # 0~100
    score_breakdown = Column(JSON)   # {field_coverage, genre_confidence, synopsis_quality, ...}

    # 처리 이력
    ai_processed_at = Column(DateTime(timezone=True))
    reviewed_by = Column(String(200))
    reviewed_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    content = relationship("Content", back_populates="metadata_record")


class CpEmailLog(Base):
    __tablename__ = "cp_email_logs"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(500), unique=True, index=True)  # 이메일 Message-ID
    subject = Column(String(1000))
    sender = Column(String(500))
    cp_name = Column(String(200), index=True)
    received_at = Column(DateTime(timezone=True))

    # AI 엔티티 추출 결과
    extracted_titles = Column(JSON)   # list[str]
    extracted_year = Column(Integer)
    extracted_quantity = Column(Integer)
    raw_body = Column(Text)
    extraction_confidence = Column(Float)

    processed = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    contents = relationship("Content", back_populates="cp_email")


class ExternalMetaCache(Base):
    __tablename__ = "external_meta_cache"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(20), index=True)   # kobis / tmdb
    external_id = Column(String(100), index=True)
    query_key = Column(String(500), index=True)  # "title:year" 검색 키
    data = Column(JSON)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
