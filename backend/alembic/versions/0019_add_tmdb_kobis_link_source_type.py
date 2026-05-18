"""Add tmdb_link and kobis_link to tmdbsyncsource enum

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-18
"""
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE tmdbsyncsource ADD VALUE IF NOT EXISTS 'tmdb_link'")
    op.execute("ALTER TYPE tmdbsyncsource ADD VALUE IF NOT EXISTS 'kobis_link'")


def downgrade():
    # PostgreSQL does not support removing enum values — no-op
    pass
