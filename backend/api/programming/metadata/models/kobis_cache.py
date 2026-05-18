"""
KOBIS 로컬 캐시 모델

테이블:
  - kobis_movie_cache : KOBIS 영화 메타 캐시 (PK = movieCd)
"""

from sqlalchemy import Column, Date, Integer, JSON, String
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP

from shared.database import Base


class KobisMovieCache(Base):
    __tablename__ = "kobis_movie_cache"

    movie_cd = Column(String(20), primary_key=True)   # KOBIS movieCd
    title = Column(String(500), nullable=False, index=True)
    title_en = Column(String(500))
    open_dt = Column(Date, index=True)                # 개봉일
    prdt_year = Column(Integer, index=True)           # 제작연도
    type_nm = Column(String(100))                     # 영화 유형
    prdt_stat_nm = Column(String(100))                # 제작상태
    nation_alt = Column(String(200))                  # 국가(복수)
    genre_alt = Column(String(200))                   # 장르(복수)
    rep_nation_nm = Column(String(100))               # 대표국가
    rep_genre_nm = Column(String(100))                # 대표장르
    directors = Column(JSON)                          # [{peopleNm, peopleNmEn}, ...]
    raw_json = Column(JSON)                           # KOBIS API 원본 응답

    first_fetched_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    last_fetched_at = Column(TIMESTAMP(timezone=True), server_default=func.now(),
                             onupdate=func.now(), nullable=False)
