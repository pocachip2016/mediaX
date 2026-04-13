"""
이미지 모델

테이블:
  - content_images : 콘텐츠 이미지 (포스터/썸네일/스틸컷/배너)
"""

import enum

from sqlalchemy import Column, String, Integer, DateTime, Enum, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from shared.database import Base


class ImageType(str, enum.Enum):
    poster = "poster"          # 메인 포스터
    thumbnail = "thumbnail"    # 목록용 썸네일
    stillcut = "stillcut"      # 스틸컷
    banner = "banner"          # 배너 (가로형)
    logo = "logo"              # 로고 이미지


class ContentImage(Base):
    """콘텐츠 이미지"""
    __tablename__ = "content_images"

    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(Integer, ForeignKey("contents.id"), nullable=False, index=True)
    image_type = Column(Enum(ImageType, name="imagetype"), nullable=False, index=True)
    url = Column(String(2000), nullable=False)
    width = Column(Integer)
    height = Column(Integer)
    source = Column(String(20), default="cp")   # cp/tmdb/manual
    is_primary = Column(Boolean, default=False)  # 대표 이미지 여부
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    content = relationship("Content", back_populates="images")
