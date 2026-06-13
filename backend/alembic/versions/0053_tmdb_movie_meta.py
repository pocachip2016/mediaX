"""tmdb_movie_meta — MediSearch 기본 메타 보강 결과 (story 저작권 가드 적용)

Revision ID: 0053
Revises: 0052
Create Date: 2026-06-13
"""
import sqlalchemy as sa
from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tmdb_movie_meta",
        sa.Column("tmdb_id",      sa.BigInteger(), sa.ForeignKey("tmdb_movie_cache.id"), primary_key=True),
        sa.Column("status",       sa.String(20), nullable=False),   # success | skipped | failed
        sa.Column("meta_json",    sa.JSON(), nullable=True),         # story 제거된 구조화 메타
        sa.Column("confidence",   sa.Float(), nullable=True),
        sa.Column("source_count", sa.Integer(), nullable=True),
        sa.Column("enriched_at",  sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error",   sa.String(500), nullable=True),
    )
    op.create_index("ix_tmdb_movie_meta_status",      "tmdb_movie_meta", ["status"])
    op.create_index("ix_tmdb_movie_meta_enriched_at", "tmdb_movie_meta", ["enriched_at"])


def downgrade() -> None:
    op.drop_table("tmdb_movie_meta")
