"""series meta columns — total_seasons/total_episodes/first_air_date/last_air_date/air_status/networks on content_metadata

Revision ID: 0038
Revises: 0037
Create Date: 2026-06-05
"""
import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content_metadata", sa.Column("total_seasons", sa.Integer(), nullable=True))
    op.add_column("content_metadata", sa.Column("total_episodes", sa.Integer(), nullable=True))
    op.add_column("content_metadata", sa.Column("first_air_date", sa.Date(), nullable=True))
    op.add_column("content_metadata", sa.Column("last_air_date", sa.Date(), nullable=True))
    op.add_column("content_metadata", sa.Column("air_status", sa.String(50), nullable=True))
    op.add_column("content_metadata", sa.Column("networks", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("content_metadata", "networks")
    op.drop_column("content_metadata", "air_status")
    op.drop_column("content_metadata", "last_air_date")
    op.drop_column("content_metadata", "first_air_date")
    op.drop_column("content_metadata", "total_episodes")
    op.drop_column("content_metadata", "total_seasons")
