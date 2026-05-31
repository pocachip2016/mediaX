"""stage_auto_policy — 단계별 자동 실행 정책 (단일 행, 전부 default False)

Revision ID: 0033
Revises: 0032
Create Date: 2026-05-31
"""
import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stage_auto_policy",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("s1_auto", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("s2_auto", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("s3_auto", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("s4_auto", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("s5_auto", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("s6_auto", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("stage_auto_policy")
