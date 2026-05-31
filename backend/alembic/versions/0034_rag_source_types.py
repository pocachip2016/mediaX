"""externalsourcetype에 wikidata/wikipedia 추가 (RAG field extract)

Revision ID: 0034
Revises: 0033
Create Date: 2026-05-31
"""
from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE externalsourcetype ADD VALUE IF NOT EXISTS 'wikidata'")
    op.execute("ALTER TYPE externalsourcetype ADD VALUE IF NOT EXISTS 'wikipedia'")


def downgrade():
    # PostgreSQL does not support removing enum values — no-op
    pass
