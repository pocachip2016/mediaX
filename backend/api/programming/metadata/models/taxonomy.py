"""
분류 체계 모델 — 장르·태그 마스터 및 콘텐츠 연결

테이블:
  - genre_codes    : 장르 마스터 (대분류/소분류 계층)
  - tag_codes      : 태그 마스터 (mood/theme/keyword/ai)
  - content_genres : 콘텐츠-장르 M:N
  - content_tags   : 콘텐츠-태그 M:N
"""

import enum

from sqlalchemy import (
    Column, String, Integer, Float, DateTime,
    Enum, ForeignKey, Boolean, PrimaryKeyConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from shared.database import Base


class TagType(str, enum.Enum):
    mood = "mood"        # 감성 태그: 따뜻한, 긴장감
    theme = "theme"      # 테마 태그: 복수극, 성장
    keyword = "keyword"  # 키워드: 실화기반, 반전있음
    ai = "ai"            # AI 자동 생성 태그


class GenreCode(Base):
    """장르 마스터 — 지니TV 표준 장르 코드 기반 계층 구조"""
    __tablename__ = "genre_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)  # 예: "ACT", "DRM_ROM"
    name_ko = Column(String(100), nullable=False)     # 예: 액션, 로맨스드라마
    name_en = Column(String(100))
    parent_id = Column(Integer, ForeignKey("genre_codes.id"), nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 자기참조 관계
    children = relationship("GenreCode", foreign_keys=[parent_id], back_populates="parent")
    parent = relationship(
        "GenreCode",
        foreign_keys=[parent_id],
        back_populates="children",
        remote_side="GenreCode.id",
    )
    content_genres = relationship("ContentGenre", back_populates="genre")


class TagCode(Base):
    """태그 마스터"""
    __tablename__ = "tag_codes"

    id = Column(Integer, primary_key=True, index=True)
    tag_type = Column(Enum(TagType, name="tagtype"), nullable=False, index=True)
    name = Column(String(200), nullable=False, index=True)
    created_by = Column(String(20), default="manual")  # "ai" or "manual"
    use_count = Column(Integer, default=0)             # 사용 빈도 (검색 최적화용)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    content_tags = relationship("ContentTag", back_populates="tag")


class ContentGenre(Base):
    """콘텐츠-장르 M:N 연결"""
    __tablename__ = "content_genres"
    __table_args__ = (
        PrimaryKeyConstraint("content_id", "genre_id"),
    )

    content_id = Column(Integer, ForeignKey("contents.id"), nullable=False)
    genre_id = Column(Integer, ForeignKey("genre_codes.id"), nullable=False)
    is_primary = Column(Boolean, default=False)  # 대표 장르 여부
    source = Column(String(20), default="ai")    # cp/ai/kobis/tmdb/manual
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    content = relationship("Content", back_populates="genres")
    genre = relationship("GenreCode", back_populates="content_genres")


class ContentTag(Base):
    """콘텐츠-태그 M:N 연결"""
    __tablename__ = "content_tags"
    __table_args__ = (
        PrimaryKeyConstraint("content_id", "tag_id"),
    )

    content_id = Column(Integer, ForeignKey("contents.id"), nullable=False)
    tag_id = Column(Integer, ForeignKey("tag_codes.id"), nullable=False)
    source = Column(String(20), default="ai")         # cp/ai/kobis/tmdb/manual
    confidence_score = Column(Float, nullable=True)   # AI 태깅 신뢰도 0~1
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    content = relationship("Content", back_populates="tags")
    tag = relationship("TagCode", back_populates="content_tags")
