"""
KMDB 로컬 캐시 모델

테이블:
  - kmdb_movie_cache : 한국 영화 메타 캐시 (PK = DOCID str)
"""

from sqlalchemy import Column, Integer, JSON, String, Text
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP

from shared.database import Base


class KmdbMovieCache(Base):
    __tablename__ = "kmdb_movie_cache"

    docid = Column(String(50), primary_key=True)     # KMDB DOCID (예: "K|00001")
    title = Column(String(500), nullable=False, index=True)
    title_eng = Column(String(500))
    title_org = Column(String(500))
    prod_year = Column(Integer, index=True)
    nation = Column(String(200))
    genre = Column(String(200))
    runtime = Column(Integer)                        # 분
    poster_url = Column(Text)                          # 첫 번째 URL (하위호환)
    poster_urls = Column(JSON)                         # 다중 poster URL 리스트 (|분해)
    stillcut_urls = Column(JSON)                       # 다중 stillcut URL 리스트
    synopsis = Column(Text)
    directors = Column(JSON)                         # [{directorNm, directorEnNm, ...}, ...]
    actors = Column(JSON)                            # [{actorNm, actorEnNm, ...}, ...]
    raw_json = Column(JSON)                          # KMDB Result 원본 응답

    first_fetched_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    last_fetched_at = Column(TIMESTAMP(timezone=True), server_default=func.now(),
                             onupdate=func.now(), nullable=False)
