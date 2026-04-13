"""
인물 모델 — 배우·감독·작가 마스터 및 콘텐츠 크레딧

테이블:
  - person_master   : 인물 마스터 (TMDB/KOBIS 연결)
  - content_credits : 콘텐츠-인물 관계 (역할 포함)
"""

import enum

from sqlalchemy import Column, String, Integer, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from shared.database import Base


class CreditRole(str, enum.Enum):
    director = "director"
    actor = "actor"
    writer = "writer"
    producer = "producer"
    composer = "composer"
    cinematographer = "cinematographer"
    editor = "editor"
    other = "other"


class PersonMaster(Base):
    """인물 마스터 — 중복 병합(merge) 지원"""
    __tablename__ = "person_master"

    id = Column(Integer, primary_key=True, index=True)
    name_ko = Column(String(200), nullable=False, index=True)
    name_en = Column(String(200), index=True)
    birth_year = Column(Integer)
    nationality = Column(String(100))

    # 외부 시스템 연결 키
    tmdb_person_id = Column(Integer, unique=True, nullable=True, index=True)
    kobis_person_nm = Column(String(200))          # KOBIS는 이름 기반 매핑

    # 병합 지원: 중복 인물 발견 시 canonical_id로 통합
    canonical_id = Column(Integer, ForeignKey("person_master.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    credits = relationship("ContentCredit", back_populates="person")
    # 중복 항목들 (이 인물이 canonical인 경우 → 나를 가리키는 목록)
    duplicates = relationship(
        "PersonMaster",
        foreign_keys=[canonical_id],
        back_populates="canonical_person",
    )
    # 이 인물이 통합된 원본 인물
    canonical_person = relationship(
        "PersonMaster",
        foreign_keys=[canonical_id],
        back_populates="duplicates",
        remote_side="PersonMaster.id",
    )


class ContentCredit(Base):
    """콘텐츠-인물 크레딧 관계"""
    __tablename__ = "content_credits"

    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(Integer, ForeignKey("contents.id"), nullable=False, index=True)
    person_id = Column(Integer, ForeignKey("person_master.id"), nullable=False, index=True)
    role = Column(Enum(CreditRole, name="creditrole"), nullable=False)
    character_name = Column(String(300))  # 배우의 극중 캐릭터명
    cast_order = Column(Integer)          # 크레딧 순서 (주연 1번, 조연 2번...)
    source = Column(String(20), default="cp")  # cp/ai/kobis/tmdb/manual
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    content = relationship("Content", back_populates="credits")
    person = relationship("PersonMaster", back_populates="credits")
