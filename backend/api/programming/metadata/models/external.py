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
    kmdb = "kmdb"  # 한국영상자료원 KMDb
    omdb = "omdb"  # OMDb — IMDb 글로벌 보완 (Phase C)
    websearch = "websearch"    # WebSearch (Brave/SerpAPI/Gemini/Ollama+DDG) — Phase D
    wikidata = "wikidata"      # Wikidata 구조화 fact (RAG)
    wikipedia = "wikipedia"    # Wikipedia intro 텍스트 (RAG)
    manual = "manual"          # 수동 입력
    bulk_upload = "bulk_upload"  # CSV/Excel 일괄 업로드
    medisearch = "medisearch"    # MediSearch 온디맨드 메타 검색


class AITaskType(str, enum.Enum):
    synopsis = "synopsis"               # 시놉시스 생성
    genre = "genre"                     # 장르 분류
    tagging = "tagging"                 # 감성·태그 분류
    rating = "rating"                   # 시청등급 제안
    entity = "entity"                   # 엔티티 추출 (인물/키워드)
    quality = "quality"                 # 품질 평가
    translate_synopsis = "translate_synopsis"   # 줄거리 ko↔en 번역 (Phase1)
    short_synopsis = "short_synopsis"           # 줄거리 요약 (Phase1)
    genre_normalized = "genre_normalized"       # 표준 장르 분류 (Phase1)
    mood_tags = "mood_tags"                     # 감성 태그 분류 (Phase1)
    keywords = "keywords"                       # 키워드 추출 (Phase1)
    facet_analysis = "facet_analysis"           # MediSearch facet 평가 (멀티소스 검색→Ollama→병합)


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
    input_hash = Column(String(64), index=True)  # SHA-256(content_id+task+input) — 캐시 키
    processed_at = Column(DateTime(timezone=True), server_default=func.now())

    content = relationship("Content", back_populates="ai_results")


class FacetBatchRun(Base):
    """
    MediSearch facet 배치 실행 추적 — 콘텐츠별 facet_analysis 일괄 처리 단위
    run 1건 = beat/수동 트리거 1회. 결과 자체는 content_ai_results에 저장.
    """
    __tablename__ = "facet_batch_runs"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)  # pending/running/done/failed/cancelled
    trigger = Column(String(20), nullable=False, default="manual")  # beat | manual
    total_count = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    skipped_count = Column(Integer, nullable=False, default=0)
    error_log = Column(JSON)   # [{content_id, error}, ...]
    params = Column(JSON)      # {limit, content_ids, force, ...} 트리거 시점 인자
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True))


class FacetEvent(Base):
    """
    facet 배치 실시간 진행 이벤트 — FacetPolicy.log_enabled=True 일 때만 기록.
    대시보드 실시간 로그 창의 since-id 커서 폴링 대상 (StageEvent 패턴 축약판).
    """
    __tablename__ = "facet_events"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("facet_batch_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    content_id = Column(Integer, nullable=True, index=True)  # batch_* 이벤트는 None
    event_type = Column(String(30), nullable=False, index=True)  # batch_started/item_started/item_success/item_failed/batch_done
    message = Column(String(500), nullable=True)
    detail = Column(JSON, nullable=True)  # {confidence, reason, ...}
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FacetPolicy(Base):
    """
    facet 배치 전역 정책 — EnrichPolicy 패턴 단일 행(id=1).
    log_enabled: facet_events 실시간 로깅 on/off (off 시 이벤트 미기록, 카운터는 항상 유지).
    """
    __tablename__ = "facet_policy"

    id = Column(Integer, primary_key=True, default=1)
    log_enabled = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AiTaskSetting(Base):
    """
    AI Task 항목별 on/off 설정 — ADR-007 B4
    task_name = AITaskType value 문자열 (예: "translate_synopsis")
    """
    __tablename__ = "ai_task_settings"

    task_name = Column(String(100), primary_key=True)
    enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EnrichPolicy(Base):
    """
    보완 단계 전역 정책 — ADR-008 (0032 마이그레이션에서 컬럼 rename)
    단일 행(id=1).
    use_cache_db  : 보완 시 내부 캐시 DB(TMDB/KMDB) 조회 여부
    use_websearch : WebSearch 사용 여부
    """
    __tablename__ = "enrich_policy"

    id = Column(Integer, primary_key=True, default=1)
    use_cache_db = Column(Boolean, nullable=False, default=False)
    confidence_threshold = Column(Float, nullable=False, default=0.90)
    use_websearch = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class StageAutoPolicy(Base):
    """
    단계별 자동 실행 정책 — ADR-009. 단일 행(id=1).
    advance-out 정렬: s1=생성→보완, s2=보완→AI, s3=AI→검수, s4=검수→승인, s5=승인→게시.
    전부 기본 False → 자동 전이 없음(단계별 수동 테스트 안전).
    """
    __tablename__ = "stage_auto_policy"

    id = Column(Integer, primary_key=True, default=1)
    s1_auto = Column(Boolean, nullable=False, default=False)
    s2_auto = Column(Boolean, nullable=False, default=False)
    s3_auto = Column(Boolean, nullable=False, default=False)
    s4_auto = Column(Boolean, nullable=False, default=False)
    s5_auto = Column(Boolean, nullable=False, default=False)
    s6_auto = Column(Boolean, nullable=False, default=False)
    s4_quality_threshold = Column(Float, nullable=False, default=90.0)  # S4 자동 승인 최소 quality_score
    # AUTO 워커 제어 (ADR-010)
    auto_tick_enabled = Column(Boolean, nullable=False, default=True, server_default="true")  # tick 마스터 스위치
    batch_size = Column(Integer, nullable=False, default=20, server_default="20")  # 태스크당 처리 상한
    ai_concurrency = Column(Integer, nullable=False, default=2, server_default="2")  # AI 동시 처리 상한
    ai_visibility_timeout = Column(Integer, nullable=False, default=600, server_default="600")  # claim 재확보 임계(초)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
