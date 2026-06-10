"""MediSearch facet 통합 — aitasktype에 facet_analysis 추가 + facet_batch_runs

Revision ID: 0049
Revises: 0048
Create Date: 2026-06-10
"""
import sqlalchemy as sa
from alembic import op

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. aitasktype enum 확장 (0034 패턴) ───────────────────────────────────
    op.execute("ALTER TYPE aitasktype ADD VALUE IF NOT EXISTS 'facet_analysis'")

    # ── 2. facet_batch_runs 테이블 ─────────────────────────────────────────────
    op.create_table(
        "facet_batch_runs",
        sa.Column("id",            sa.Integer(), primary_key=True),
        sa.Column("status",        sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("trigger",       sa.String(20), nullable=False, server_default="manual"),
        sa.Column("total_count",   sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count",  sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_log",     sa.JSON(), nullable=True),
        sa.Column("params",        sa.JSON(), nullable=True),
        sa.Column("created_at",    sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at",   sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("facet_batch_runs")
    # PostgreSQL은 enum 값 제거를 지원하지 않음 — facet_analysis는 잔류 (no-op)
