"""facet 실시간 이벤트 로그 + 정책 테이블

Revision ID: 0050
Revises: 0049
Create Date: 2026-06-10
"""
import sqlalchemy as sa
from alembic import op

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. facet_policy (EnrichPolicy 패턴, 단일행 id=1) ─────────────────────
    op.create_table(
        "facet_policy",
        sa.Column("id",          sa.Integer(), primary_key=True),
        sa.Column("log_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("updated_at",  sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── 2. facet_events (StageEvent 축약, since-id 커서 폴링용) ───────────────
    op.create_table(
        "facet_events",
        sa.Column("id",         sa.Integer(), primary_key=True),
        sa.Column("run_id",     sa.Integer(), sa.ForeignKey("facet_batch_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("message",    sa.String(500), nullable=True),
        sa.Column("detail",     sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_facet_events_run_id",    "facet_events", ["run_id"])
    op.create_index("ix_facet_events_content_id","facet_events", ["content_id"])
    op.create_index("ix_facet_events_event_type","facet_events", ["event_type"])
    op.create_index("ix_facet_events_created_at","facet_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("facet_events")
    op.drop_table("facet_policy")
