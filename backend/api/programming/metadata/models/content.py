"""
콘텐츠 핵심 모델

테이블:
  - contents         : 콘텐츠 원본 (movie/series/season/episode 계층)
  - content_metadata : AI 처리 메타 + 품질 스코어
  - cp_email_logs    : CP사 이메일 수신 이력
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
    season = "season"
    episode = "episode"


class ContentStatus(str, enum.Enum):
    waiting = "waiting"        # CP 이메일 수신 후 대기
    processing = "processing"  # AI 처리 중
    staging = "staging"        # 에이전틱 검색 완료, 운영자 검토 대기
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
    content_type = Column(
        Enum(ContentType, name="contenttype"),
        nullable=False,
        default=ContentType.movie,
    )
    status = Column(
        Enum(ContentStatus, name="contentstatus"),
        nullable=False,
        default=ContentStatus.waiting,
        index=True,
    )

    # CP사 정보
    cp_name = Column(String(200), index=True)
    cp_email_id = Column(Integer, ForeignKey("cp_email_logs.id"), nullable=True)

    # 영상 기본 정보
    production_year = Column(Integer)
    runtime_minutes = Column(Integer)
    country = Column(String(100))

    # 시리즈 계층 (series → season → episode)
    parent_id = Column(Integer, ForeignKey("contents.id"), nullable=True)
    season_number = Column(Integer)
    episode_number = Column(Integer)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_deleted = Column(Boolean, default=False, index=True)
    locked_fields = Column(JSON, default=list)  # List[str] — 잠금 필드 목록

    # Relationships
    metadata_record = relationship("ContentMetadata", back_populates="content", uselist=False)
    cp_email = relationship("CpEmailLog", back_populates="contents")
    children = relationship("Content", foreign_keys=[parent_id], back_populates="parent")
    parent = relationship(
        "Content",
        foreign_keys=[parent_id],
        back_populates="children",
        remote_side="Content.id",
    )
    genres = relationship("ContentGenre", back_populates="content", cascade="all, delete-orphan")
    tags = relationship("ContentTag", back_populates="content", cascade="all, delete-orphan")
    credits = relationship("ContentCredit", back_populates="content", cascade="all, delete-orphan")
    images = relationship("ContentImage", back_populates="content", cascade="all, delete-orphan")
    # NOTE: external_sources 는 의도적으로 delete cascade 미설정.
    # external_meta_sources 는 TMDB/KOBIS 수집 결과(SSOT·재구축 고비용)이므로
    # 부모 Content 삭제 시 함께 지우면 안 됨. content_id 가 nullable + FK NO ACTION
    # 이므로 기본 cascade(save-update, merge) 동작이 부모 삭제 시 content_id 를
    # NULL 로 비워 행을 보존한다.
    external_sources = relationship(
        "ExternalMetaSource", back_populates="content"
    )
    ai_results = relationship(
        "ContentAIResult", back_populates="content", cascade="all, delete-orphan"
    )


class ContentMetadata(Base):
    """AI 처리된 메타데이터 + 품질 스코어 (기존 구조 유지, 신규 정규화 테이블과 병행)"""
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
    ai_genre_primary = Column(String(200))
    ai_genre_secondary = Column(String(200))
    ai_mood_tags = Column(JSON)     # list[str]
    ai_cast = Column(JSON)
    ai_rating_suggestion = Column(String(200))  # 전체/12세/15세/청불

    # 외부 API 메타 (kobis_movie_cd/kobis_data/tmdb_id → external_meta_sources로 이관)
    tmdb_data = Column(JSON)

    # 최종 확정 메타 (담당자 검수 후)
    final_synopsis = Column(Text)
    final_genre = Column(String(200))
    final_tags = Column(JSON)
    final_cast = Column(JSON)
    final_source = Column(Enum(MetaSource, name="metasource"), default=MetaSource.ai)

    # 품질 스코어링 (콘텐츠 메타 완성도, 0~100 — match_score 와 별도)
    quality_score = Column(Float, default=0.0, index=True)
    # score_breakdown 키: synopsis_completeness, genre_classification,
    # tag_count, external_meta, basic_fields_filled
    score_breakdown = Column(JSON)

    # 메타 완료 플래그 (글자메타 / 이미지메타 / 영상메타)
    text_meta_completed = Column(Boolean, default=False, nullable=False, server_default="false")
    image_meta_completed = Column(Boolean, default=False, nullable=False, server_default="false")
    video_meta_completed = Column(Boolean, default=False, nullable=False, server_default="false")

    # 영상 기술 메타 (신규)
    video_resolution = Column(String(20))       # "4K", "FHD", "HD", "SD"
    video_format = Column(String(20))           # "MP4", "TS", "MKV"
    codec_video = Column(String(50))            # "H.264", "H.265", "AV1"
    codec_audio = Column(String(50))            # "AAC", "AC3", "EAC3"
    video_bitrate_kbps = Column(Integer)
    video_duration_seconds = Column(Integer)
    subtitle_languages = Column(JSON)           # list[str]
    drm_type = Column(String(50))               # "Widevine", "PlayReady", "FairPlay"
    preview_clip_url = Column(String(1000))

    # 업로드 확장 필드
    audio_channels = Column(String(20))              # "5.1CH", "Stereo", "Atmos"
    extra_metadata = Column(JSON)                    # CSV 미매핑 컬럼 흡수 {"헤더": "값"}

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
    message_id = Column(String(500), unique=True, index=True)
    subject = Column(String(1000))
    sender = Column(String(500))
    cp_name = Column(String(200), index=True)
    received_at = Column(DateTime(timezone=True))

    # AI 엔티티 추출 결과
    extracted_titles = Column(JSON)
    extracted_year = Column(Integer)
    extracted_quantity = Column(Integer)
    raw_body = Column(Text)
    extraction_confidence = Column(Float)

    processed = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    contents = relationship("Content", back_populates="cp_email")


class ContentBatchJob(Base):
    """CSV/엑셀 배치 업로드 이력 추적"""
    __tablename__ = "content_batch_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_name = Column(String(300), nullable=False)
    cp_name = Column(String(200), index=True)
    status = Column(String(50), nullable=False, default="pending", index=True)
    # pending / parsing / processing / done / failed

    file_name = Column(String(500))
    file_size_bytes = Column(Integer)
    total_count = Column(Integer, default=0)
    parsed_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    error_log = Column(JSON)   # list[{row, error}]
    parse_mode = Column(String(50), default="llm")  # llm | rule
    created_by = Column(String(200))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True))


class ContentActionLog(Base):
    """Bulk 액션 이력 추적 — undo 기능 지원"""
    __tablename__ = "content_action_logs"

    action_id = Column(String(36), primary_key=True, index=True)  # UUID
    content_ids = Column(JSON, nullable=False)  # List[int]
    action_type = Column(String(50), nullable=False)  # bulk_reprocess, bulk_enrich, ...
    before_state = Column(JSON, nullable=False)  # {id: {status, ...}}
    executed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    reverted_at = Column(DateTime(timezone=True), nullable=True)


class ContentAuditLog(Base):
    """필드별 변경 감시 로그 — promote/apply-fields/lock 등 필드 변경 시 자동 기록"""
    __tablename__ = "content_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(Integer, ForeignKey("contents.id"), nullable=False, index=True)
    field = Column(String(100), nullable=False)  # 필드명 (e.g., "synopsis", "genre")
    old_value = Column(Text, nullable=True)  # 이전 값 (JSON serialized)
    new_value = Column(Text, nullable=True)  # 새 값 (JSON serialized)
    source = Column(String(50), nullable=False)  # promote_ai | apply_external | lock | ...
    actor = Column(String(200), nullable=True)  # 수행자 (사용자명 또는 시스템)
    at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
