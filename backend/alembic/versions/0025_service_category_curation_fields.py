"""service_categories 큐레이션 워크벤치 확장 컬럼

Revision ID: 0025
Revises: 0024
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("service_categories", sa.Column("headline_copy", sa.String(200), nullable=True))
    op.add_column("service_categories", sa.Column("sub_copy", sa.String(300), nullable=True))
    op.add_column("service_categories", sa.Column("theme_features", sa.JSON, nullable=True))
    op.add_column("service_categories", sa.Column("source_mode", sa.String(20), nullable=False, server_default="manual"))
    op.add_column("service_categories", sa.Column("reference_external_id", sa.String(200), nullable=True))
    op.add_column("service_categories", sa.Column("is_draft", sa.Boolean, nullable=False, server_default="false"))


def downgrade() -> None:
    op.drop_column("service_categories", "is_draft")
    op.drop_column("service_categories", "reference_external_id")
    op.drop_column("service_categories", "source_mode")
    op.drop_column("service_categories", "theme_features")
    op.drop_column("service_categories", "sub_copy")
    op.drop_column("service_categories", "headline_copy")
