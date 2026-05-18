"""content_metadata AI 컬럼 VARCHAR 확장

Revision ID: 0017
Revises: 0016
Create Date: 2026-05-18

변경 내용:
  - ai_genre_primary   VARCHAR(100) → VARCHAR(200)
  - ai_genre_secondary VARCHAR(100) → VARCHAR(200)
  - ai_rating_suggestion VARCHAR(20) → VARCHAR(200)
    (SQLite 실데이터가 기존 제약을 초과 — 마이그레이션 중 StringDataRightTruncation 수정)
"""

from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("content_metadata", "ai_genre_primary",
                    type_=sa.String(200), existing_nullable=True)
    op.alter_column("content_metadata", "ai_genre_secondary",
                    type_=sa.String(200), existing_nullable=True)
    op.alter_column("content_metadata", "ai_rating_suggestion",
                    type_=sa.String(200), existing_nullable=True)


def downgrade() -> None:
    op.alter_column("content_metadata", "ai_rating_suggestion",
                    type_=sa.String(20), existing_nullable=True)
    op.alter_column("content_metadata", "ai_genre_secondary",
                    type_=sa.String(100), existing_nullable=True)
    op.alter_column("content_metadata", "ai_genre_primary",
                    type_=sa.String(100), existing_nullable=True)
