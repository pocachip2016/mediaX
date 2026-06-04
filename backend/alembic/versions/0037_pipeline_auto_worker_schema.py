"""pipeline auto worker schema — auto_hold/auto_claimed_at/auto_review_skipped_at on contents,
auto_tick_enabled/batch_size/ai_concurrency/ai_visibility_timeout on stage_auto_policy (ADR-010)

Revision ID: 0037
Revises: 0036
Create Date: 2026-06-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade():
    # contents — AUTO 워커 제어 컬럼
    op.add_column("contents", sa.Column("auto_hold", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("contents", sa.Column("auto_review_skipped_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contents", sa.Column("auto_claimed_at", sa.DateTime(timezone=True), nullable=True))

    # stage_auto_policy — 워커 정책 컬럼
    op.add_column("stage_auto_policy", sa.Column("auto_tick_enabled", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("stage_auto_policy", sa.Column("batch_size", sa.Integer(), nullable=False, server_default="20"))
    op.add_column("stage_auto_policy", sa.Column("ai_concurrency", sa.Integer(), nullable=False, server_default="2"))
    op.add_column("stage_auto_policy", sa.Column("ai_visibility_timeout", sa.Integer(), nullable=False, server_default="600"))


def downgrade():
    op.drop_column("contents", "auto_hold")
    op.drop_column("contents", "auto_review_skipped_at")
    op.drop_column("contents", "auto_claimed_at")
    op.drop_column("stage_auto_policy", "auto_tick_enabled")
    op.drop_column("stage_auto_policy", "batch_size")
    op.drop_column("stage_auto_policy", "ai_concurrency")
    op.drop_column("stage_auto_policy", "ai_visibility_timeout")
