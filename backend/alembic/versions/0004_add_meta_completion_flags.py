"""add meta completion flags and video meta fields

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-12

변경 내용:
  content_metadata 테이블에 추가:
  - text_meta_completed  : 글자메타 완료 여부
  - image_meta_completed : 이미지메타 완료 여부
  - video_meta_completed : 영상메타 완료 여부
  - video_resolution     : 영상 해상도 (4K/FHD/HD/SD)
  - video_format         : 영상 포맷 (MP4/TS/MKV)
  - codec_video          : 영상 코덱 (H.264/H.265/AV1)
  - codec_audio          : 오디오 코덱 (AAC/AC3/EAC3)
  - video_bitrate_kbps   : 영상 비트레이트
  - video_duration_seconds : 영상 재생 시간 (초)
  - subtitle_languages   : 자막 언어 목록 (JSON)
  - drm_type             : DRM 타입 (Widevine/PlayReady/FairPlay)
  - preview_clip_url     : 미리보기 클립 URL
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 완료 플래그 3개
    op.add_column("content_metadata", sa.Column("text_meta_completed", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("content_metadata", sa.Column("image_meta_completed", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("content_metadata", sa.Column("video_meta_completed", sa.Boolean(), nullable=False, server_default="false"))

    # 영상 기술 메타
    op.add_column("content_metadata", sa.Column("video_resolution", sa.String(20), nullable=True))
    op.add_column("content_metadata", sa.Column("video_format", sa.String(20), nullable=True))
    op.add_column("content_metadata", sa.Column("codec_video", sa.String(50), nullable=True))
    op.add_column("content_metadata", sa.Column("codec_audio", sa.String(50), nullable=True))
    op.add_column("content_metadata", sa.Column("video_bitrate_kbps", sa.Integer(), nullable=True))
    op.add_column("content_metadata", sa.Column("video_duration_seconds", sa.Integer(), nullable=True))
    op.add_column("content_metadata", sa.Column("subtitle_languages", sa.JSON(), nullable=True))
    op.add_column("content_metadata", sa.Column("drm_type", sa.String(50), nullable=True))
    op.add_column("content_metadata", sa.Column("preview_clip_url", sa.String(1000), nullable=True))


def downgrade() -> None:
    op.drop_column("content_metadata", "preview_clip_url")
    op.drop_column("content_metadata", "drm_type")
    op.drop_column("content_metadata", "subtitle_languages")
    op.drop_column("content_metadata", "video_duration_seconds")
    op.drop_column("content_metadata", "video_bitrate_kbps")
    op.drop_column("content_metadata", "codec_audio")
    op.drop_column("content_metadata", "codec_video")
    op.drop_column("content_metadata", "video_format")
    op.drop_column("content_metadata", "video_resolution")
    op.drop_column("content_metadata", "video_meta_completed")
    op.drop_column("content_metadata", "image_meta_completed")
    op.drop_column("content_metadata", "text_meta_completed")
