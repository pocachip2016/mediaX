"""web_search_cache 테이블 추가 — Brave/SerpAPI 결과 캐시 (쿼터 보호)

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-09
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "web_search_cache",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("query_hash", sa.String(64), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("results_json", sa.JSON()),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_index("ix_web_search_cache_query_hash", "web_search_cache", ["query_hash"], unique=True)
    op.create_index("ix_web_search_cache_expires_at", "web_search_cache", ["expires_at"])


def downgrade():
    op.drop_index("ix_web_search_cache_expires_at", table_name="web_search_cache")
    op.drop_index("ix_web_search_cache_query_hash", table_name="web_search_cache")
    op.drop_table("web_search_cache")
