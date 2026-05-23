"""Add cache_inserted / cache_updated to external_sync_log

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "external_sync_log",
        sa.Column("cache_inserted", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "external_sync_log",
        sa.Column("cache_updated", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("external_sync_log", "cache_updated")
    op.drop_column("external_sync_log", "cache_inserted")
