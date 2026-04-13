"""add staging status and content_batch_jobs table

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-12

변경 내용:
  - contents.status ENUM에 'staging' 추가
    (waiting → processing → staging → approved/rejected)
  - content_batch_jobs 신규 테이블 (CSV/엑셀 배치 업로드 이력 추적)
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # ── 1. contentstatus ENUM에 'staging' 추가 ──────────────────────────
    if dialect == "postgresql":
        op.execute("ALTER TYPE contentstatus ADD VALUE IF NOT EXISTS 'staging' AFTER 'processing'")
    # SQLite는 ENUM을 VARCHAR로 처리하므로 ALTER 불필요

    # ── 2. content_batch_jobs 테이블 생성 ───────────────────────────────
    if dialect == "sqlite":
        now_default = "datetime('now')"
    else:
        now_default = "now()"

    op.create_table(
        "content_batch_jobs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("job_name", sa.String(300), nullable=False),
        sa.Column("cp_name", sa.String(200)),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="pending",
        ),  # pending / parsing / processing / done / failed
        sa.Column("file_name", sa.String(500)),
        sa.Column("file_size_bytes", sa.Integer),
        sa.Column("total_count", sa.Integer, server_default="0"),
        sa.Column("parsed_count", sa.Integer, server_default="0"),
        sa.Column("success_count", sa.Integer, server_default="0"),
        sa.Column("failed_count", sa.Integer, server_default="0"),
        sa.Column("error_log", sa.JSON),  # list[{row, error}]
        sa.Column("parse_mode", sa.String(50), server_default="llm"),  # llm | rule
        sa.Column("created_by", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text(now_default)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_content_batch_jobs_status", "content_batch_jobs", ["status"])
    op.create_index("ix_content_batch_jobs_cp_name", "content_batch_jobs", ["cp_name"])


def downgrade() -> None:
    op.drop_index("ix_content_batch_jobs_cp_name", "content_batch_jobs")
    op.drop_index("ix_content_batch_jobs_status", "content_batch_jobs")
    op.drop_table("content_batch_jobs")
    # PostgreSQL ENUM 값 제거는 직접 지원하지 않으므로 주석 처리
    # op.execute("ALTER TYPE contentstatus DROP VALUE 'staging'")  -- not supported in PostgreSQL
