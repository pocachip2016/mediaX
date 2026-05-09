"""TmdbSyncSource ENUM에 kobis_daily / kobis_backfill 추가

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-09

PostgreSQL: ALTER TYPE tmdbsyncsource ADD VALUE
SQLite: VARCHAR — 추가 DDL 불필요
"""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE tmdbsyncsource ADD VALUE IF NOT EXISTS 'kobis_daily'")
        op.execute("ALTER TYPE tmdbsyncsource ADD VALUE IF NOT EXISTS 'kobis_backfill'")
    # SQLite: tmdbsyncsource는 VARCHAR — 새 값 자동 허용


def downgrade():
    # PostgreSQL ENUM 값 제거는 불가 (PostgreSQL 제약)
    pass
