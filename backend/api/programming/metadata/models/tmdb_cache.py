"""
TMDB 로컬 캐시 모델 + 외부 소스 동기화 이력

테이블:
  - tmdb_movie_cache  : 영화 메타 캐시 (PK = TMDB movie_id)
  - tmdb_movie_facets : MediSearch facet 평가 결과 (PK = TMDB movie_id)
  - tmdb_tv_cache     : TV 시리즈 메타 캐시 (PK = TMDB tv_id)
  - tmdb_person_cache : 인물 메타 캐시 (PK = TMDB person_id)
  - external_sync_log : 전 외부소스 동기화 이력 (TMDB·KOBIS 등 공용)
  - web_search_cache  : Brave/SerpAPI 웹 검색 결과 캐시 (쿼터 보호)
"""

import enum
import uuid

from sqlalchemy import (
    BigInteger, Boolean, Column, Date, Float, ForeignKey, Integer,
    JSON, String, Text, Enum as SAEnum, UniqueConstraint,
)
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP

from shared.database import Base
from api.programming.metadata.models.external import ExternalSourceType


def _new_uuid() -> str:
    return str(uuid.uuid4())


class TmdbSyncSource(str, enum.Enum):
    discover_movie = "discover_movie"
    discover_tv = "discover_tv"
    changes_movie = "changes_movie"
    changes_tv = "changes_tv"
    backfill_movie_year = "backfill_movie_year"
    backfill_tv_year = "backfill_tv_year"
    kobis_daily = "kobis_daily"
    kobis_backfill = "kobis_backfill"
    kmdb_daily = "kmdb_daily"
    kmdb_backfill = "kmdb_backfill"
    tmdb_link = "tmdb_link"
    kobis_link = "kobis_link"
    kmdb_link = "kmdb_link"
    llm_merge = "llm_merge"


class TmdbSyncStatus(str, enum.Enum):
    running = "running"
    completed = "completed"
    failed = "failed"


class TmdbMovieCache(Base):
    __tablename__ = "tmdb_movie_cache"

    id = Column(BigInteger, primary_key=True)       # TMDB movie_id
    title = Column(String(500), nullable=False)
    original_title = Column(String(500))
    original_language = Column(String(10))
    release_date = Column(Date, index=True)
    runtime = Column(Integer)                       # 분
    popularity = Column(Float, index=True)
    vote_average = Column(Float)
    vote_count = Column(Integer)
    adult = Column(Boolean, default=False)
    poster_path = Column(String(500))               # /xxxx.jpg — TMDB base URL 조합 필요
    backdrop_path = Column(String(500))
    overview = Column(Text)
    genre_ids = Column(JSON)                        # [28, 12, ...]
    raw_json = Column(JSON)                         # TMDB /movie/{id} 전체 응답

    first_fetched_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    last_fetched_at = Column(TIMESTAMP(timezone=True), server_default=func.now(),
                             onupdate=func.now(), nullable=False)


class TmdbMovieFacet(Base):
    """MediSearch facet 평가 결과 — TMDB 캐시 모집단 SSOT.

    contents 등록 여부와 무관하게 tmdb_id 키로 저장.
    Content 매핑이 있으면 content_ai_results 에도 dual-write (facet_tasks).

    status:
      success — facet_json 보유
      skipped — 나무위키 문서 부재 등 영구 제외 (재선정 안 함, force 시에만)
      failed  — 일시 오류, FACET_RETRY_BACKOFF_DAYS 백오프 후 FACET_MAX_ATTEMPTS 까지 재시도
    """
    __tablename__ = "tmdb_movie_facets"

    tmdb_id = Column(BigInteger, ForeignKey("tmdb_movie_cache.id"), primary_key=True)
    status = Column(String(20), nullable=False, index=True)  # success | skipped | failed
    facet_json = Column(JSON)
    confidence = Column(Float)
    source_count = Column(Integer)
    attempt_count = Column(Integer, nullable=False, default=0, server_default="0")
    last_attempted_at = Column(TIMESTAMP(timezone=True))
    evaluated_at = Column(TIMESTAMP(timezone=True), index=True)
    last_error = Column(String(500))


class TmdbMovieMeta(Base):
    """MediSearch 기본 메타 보강 결과 — TMDB 캐시 모집단 SSOT.

    facet 평가(evaluate_tmdb_facet)와 동일 run에서 include_meta=True로 수집.
    저작권 가드 적용: story 필드 제거 후 저장 (나무위키 파생 창의물 영속 금지).

    status:
      success — meta_json 보유 (구조화 provider 기반, confidence 유효)
      skipped — 응답 metadata 없음 또는 빈 값
      failed  — include_meta 응답 파싱/저장 오류
    """
    __tablename__ = "tmdb_movie_meta"

    tmdb_id = Column(BigInteger, ForeignKey("tmdb_movie_cache.id"), primary_key=True)
    status = Column(String(20), nullable=False, index=True)  # success | skipped | failed
    meta_json = Column(JSON)                                  # story 제거된 구조화 메타
    confidence = Column(Float)
    source_count = Column(Integer)
    enriched_at = Column(TIMESTAMP(timezone=True), index=True)
    last_error = Column(String(500))


class TmdbTvCache(Base):
    __tablename__ = "tmdb_tv_cache"

    id = Column(BigInteger, primary_key=True)       # TMDB tv_id
    name = Column(String(500), nullable=False)
    original_name = Column(String(500))
    original_language = Column(String(10))
    first_air_date = Column(Date, index=True)
    last_air_date = Column(Date)
    number_of_seasons = Column(Integer)
    number_of_episodes = Column(Integer)
    status = Column(String(100))                    # "Ended", "Returning Series" 등
    popularity = Column(Float, index=True)
    vote_average = Column(Float)
    vote_count = Column(Integer)
    poster_path = Column(String(500))
    backdrop_path = Column(String(500))
    overview = Column(Text)
    genre_ids = Column(JSON)
    raw_json = Column(JSON)

    first_fetched_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    last_fetched_at = Column(TIMESTAMP(timezone=True), server_default=func.now(),
                             onupdate=func.now(), nullable=False)


class TmdbPersonCache(Base):
    __tablename__ = "tmdb_person_cache"

    id = Column(BigInteger, primary_key=True)       # TMDB person_id
    name = Column(String(300), nullable=False)
    also_known_as = Column(JSON)                    # ["홍길동", "Hong Gildong", ...]
    birthday = Column(Date)
    deathday = Column(Date)
    profile_path = Column(String(500))
    popularity = Column(Float)
    raw_json = Column(JSON)

    first_fetched_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    last_fetched_at = Column(TIMESTAMP(timezone=True), server_default=func.now(),
                             onupdate=func.now(), nullable=False)


class TmdbSyncLog(Base):
    __tablename__ = "external_sync_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), nullable=False, default=_new_uuid)
    # TMDB 전용 sync 종류 (backfill_movie_year / changes_movie / discover_movie 등)
    source = Column(SAEnum(TmdbSyncSource, name="tmdbsyncsource"), nullable=False)
    # 어떤 외부 소스의 sync 인지 (tmdb / kobis / …) — step3에서 추가
    external_source = Column(SAEnum(ExternalSourceType, name="externalsourcetype",
                                    create_type=False), nullable=True, index=True)
    target_year = Column(Integer)                   # 백필 연도 슬라이싱
    target_date = Column(Date)                      # Daily changes 날짜

    status = Column(SAEnum(TmdbSyncStatus, name="tmdbbsyncstatus"), nullable=False,
                    default=TmdbSyncStatus.running)

    started_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False,
                        index=True)
    finished_at = Column(TIMESTAMP(timezone=True))

    pages_fetched = Column(Integer, default=0)
    items_fetched = Column(Integer, default=0)
    items_inserted = Column(Integer, default=0)
    items_updated = Column(Integer, default=0)
    items_unchanged = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    error_sample = Column(JSON)                     # 최초 5개 에러 메시지

    cache_inserted = Column(Integer, default=0)     # kobis/kmdb_movie_cache 신규 행 수
    cache_updated = Column(Integer, default=0)      # kobis/kmdb_movie_cache 갱신 행 수


ExternalSyncLog = TmdbSyncLog


class WebSearchCache(Base):
    __tablename__ = "web_search_cache"
    __table_args__ = (
        UniqueConstraint("query_hash", "source", name="ix_web_search_cache_query_hash_source"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_hash = Column(String(64), nullable=False, index=True)  # SHA-256 hex
    query = Column(Text, nullable=False)
    source = Column(String(20), nullable=False)      # provider: brave | serpapi | gemini | ollama
    results_json = Column(JSON)
    fetched_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False, index=True)


class WebSearchQuotaLog(Base):
    """
    Phase D — provider별 일별 호출 카운터 스냅샷 (Redis → DB).

    Beat 04:00 KST 가 매일 Redis 카운터를 읽어 1행 INSERT.
    강제 소진 (429 응답) 발생 시점에 exhausted_at 즉시 UPDATE.
    """
    __tablename__ = "web_search_quota_log"
    __table_args__ = (
        UniqueConstraint("provider", "day_kst", name="uq_web_search_quota_provider_day"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(20), nullable=False)        # brave | serpapi | gemini | ollama
    day_kst = Column(String(8), nullable=False)          # YYYYMMDD
    count = Column(Integer, default=0, nullable=False)
    limit_at_time = Column(Integer, nullable=True)       # 스냅샷 시점 daily_limit
    exhausted_at = Column(TIMESTAMP(timezone=True), nullable=True)
    snapshot_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
