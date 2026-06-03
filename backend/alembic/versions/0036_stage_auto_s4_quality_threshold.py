"""stage_auto_policy에 s4_quality_threshold 추가 (S4 자동 승인 임계값)

Revision ID: 0036
Revises: 0035
Create Date: 2026-06-02
"""
import sqlalchemy as sa
from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "stage_auto_policy",
        sa.Column("s4_quality_threshold", sa.Float(), nullable=False, server_default="90.0"),
    )


def downgrade():
    op.drop_column("stage_auto_policy", "s4_quality_threshold")
