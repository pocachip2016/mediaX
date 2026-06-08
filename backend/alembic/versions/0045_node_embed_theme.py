"""node_embed_theme — ProgrammingNode.embed_theme 캐시 컬럼 (bge-m3 1024-dim)

Revision ID: 0045
Revises: 0044
Create Date: 2026-06-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(
        "ALTER TABLE programming_nodes ADD COLUMN IF NOT EXISTS embed_theme JSONB"
    ))


def downgrade() -> None:
    op.execute(sa.text(
        "ALTER TABLE programming_nodes DROP COLUMN IF EXISTS embed_theme"
    ))
