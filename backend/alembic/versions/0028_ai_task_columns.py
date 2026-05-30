"""AI Task 컬럼 추가 — ADR-007 Phase1 AiTask 프레임워크

Revision ID: 0028
Revises: 0027
Create Date: 2026-05-30

content_metadata:
  + synopsis_ko     TEXT        한국어 줄거리
  + synopsis_en     TEXT        영어 줄거리
  + short_synopsis  TEXT        2~3문장 요약
  + tagline         TEXT        홍보 한 줄 문구 (Phase2)

content_ai_results:
  + input_hash      VARCHAR(64) SHA-256 캐시 키

aitasktype enum:
  + translate_synopsis, short_synopsis, genre_normalized, mood_tags, keywords
"""
from alembic import op
import sqlalchemy as sa


revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # content_metadata 컬럼 추가
    with op.batch_alter_table("content_metadata") as batch_op:
        batch_op.add_column(sa.Column("synopsis_ko", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("synopsis_en", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("short_synopsis", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("tagline", sa.Text(), nullable=True))

    # content_ai_results 컬럼 추가
    with op.batch_alter_table("content_ai_results") as batch_op:
        batch_op.add_column(sa.Column("input_hash", sa.String(64), nullable=True, index=True))

    # aitasktype enum 확장 (PostgreSQL)
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        new_values = [
            "translate_synopsis",
            "short_synopsis",
            "genre_normalized",
            "mood_tags",
            "keywords",
        ]
        for val in new_values:
            op.execute(f"ALTER TYPE aitasktype ADD VALUE IF NOT EXISTS '{val}'")


def downgrade() -> None:
    with op.batch_alter_table("content_ai_results") as batch_op:
        batch_op.drop_column("input_hash")

    with op.batch_alter_table("content_metadata") as batch_op:
        batch_op.drop_column("tagline")
        batch_op.drop_column("short_synopsis")
        batch_op.drop_column("synopsis_en")
        batch_op.drop_column("synopsis_ko")
