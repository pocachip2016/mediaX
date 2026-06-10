"""tmdb_movie_facets — MediSearch facet 평가 결과 (TMDB 캐시 모집단 SSOT)

Revision ID: 0051
Revises: 0050
Create Date: 2026-06-10
"""
import sqlalchemy as sa
from alembic import op

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tmdb_movie_facets",
        sa.Column("tmdb_id",           sa.BigInteger(), sa.ForeignKey("tmdb_movie_cache.id"), primary_key=True),
        sa.Column("status",            sa.String(20), nullable=False),  # success | skipped | failed
        sa.Column("facet_json",        sa.JSON(), nullable=True),
        sa.Column("confidence",        sa.Float(), nullable=True),
        sa.Column("source_count",      sa.Integer(), nullable=True),
        sa.Column("attempt_count",     sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evaluated_at",      sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error",        sa.String(500), nullable=True),
    )
    op.create_index("ix_tmdb_movie_facets_status",       "tmdb_movie_facets", ["status"])
    op.create_index("ix_tmdb_movie_facets_evaluated_at", "tmdb_movie_facets", ["evaluated_at"])


def downgrade() -> None:
    op.drop_table("tmdb_movie_facets")
