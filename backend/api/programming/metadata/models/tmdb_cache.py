"""
TMDB 로컬 캐시 모델 + 외부 소스 동기화 이력

테이블:
  - tmdb_movie_cache  : 영화 메타 캐시 (PK = TMDB movie_id)
  - tmdb_tv_cache     : TV 시리즈 메타 캐시 (PK = TMDB tv_id)
  - tmdb_person_cache : 인물 메타 캐시 (PK = TMDB person_id)
  - external_sync_log : 전 외부소스 동기화 이력 (TMDB·KOBIS 등 공용)
  - web_search_cache  : Brave/SerpAPI 웹 검색 결과 캐시 (쿼터 보호)
"""

import enum
import uuid

from sqlalchemy import (
    BigInteger, Boolean, Column, Date, Float, Integer,
    JSON, String, Text, Enum as SAEnum,
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


ExternalSyncLog = TmdbSyncLog


class WebSearchCache(Base):
    __tablename__ = "web_search_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_hash = Column(String(64), unique=True, nullable=False, index=True)  # SHA-256 hex
    query = Column(Text, nullable=False)
    source = Column(String(20), nullable=False)      # "brave" | "serp" | "none"
    results_json = Column(JSON)
    fetched_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
