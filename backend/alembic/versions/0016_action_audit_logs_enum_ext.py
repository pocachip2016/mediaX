"""content_action/audit_logs 공식화 + externalsourcetype ENUM 확장

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-18

변경 내용:
  - externalsourcetype ENUM에 bulk_upload / manual 추가
    (SQLite external_meta_sources.source_type 에 실제 존재하는 값이나
     기존 ENUM에 누락되어 있어 Postgres INSERT 시 오류 방지)
  - content_action_logs : Bulk 액션 이력 (undo 지원)
  - content_audit_logs  : 필드별 변경 감시 로그
    (SQLite에서 ORM Base.metadata.create_all 로 직접 생성된 테이블을
     alembic 관리 하에 공식화)
"""

from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # ── externalsourcetype ENUM 확장 (PostgreSQL only) ──────────────────
    if dialect == "postgresql":
        op.execute("ALTER TYPE externalsourcetype ADD VALUE IF NOT EXISTS 'bulk_upload'")
        op.execute("ALTER TYPE externalsourcetype ADD VALUE IF NOT EXISTS 'manual'")

    # ── content_action_logs ─────────────────────────────────────────────
    op.create_table(
        "content_action_logs",
        sa.Column("action_id", sa.String(36), primary_key=True),
        sa.Column("content_ids", sa.JSON, nullable=False),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("before_state", sa.JSON, nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=True),
        sa.Column("reverted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_content_action_logs_action_id",
                    "content_action_logs", ["action_id"])
    op.create_index("ix_content_action_logs_executed_at",
                    "content_action_logs", ["executed_at"])

    # ── content_audit_logs ──────────────────────────────────────────────
    op.create_table(
        "content_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("content_id", sa.Integer(),
                  sa.ForeignKey("contents.id"), nullable=False),
        sa.Column("field", sa.String(100), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("actor", sa.String(200), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=True),
    )
    op.create_index("ix_content_audit_logs_id",
                    "content_audit_logs", ["id"])
    op.create_index("ix_content_audit_logs_content_id",
                    "content_audit_logs", ["content_id"])
    op.create_index("ix_content_audit_logs_at",
                    "content_audit_logs", ["at"])


def downgrade() -> None:
    op.drop_index("ix_content_audit_logs_at", "content_audit_logs")
    op.drop_index("ix_content_audit_logs_content_id", "content_audit_logs")
    op.drop_index("ix_content_audit_logs_id", "content_audit_logs")
    op.drop_table("content_audit_logs")

    op.drop_index("ix_content_action_logs_executed_at", "content_action_logs")
    op.drop_index("ix_content_action_logs_action_id", "content_action_logs")
    op.drop_table("content_action_logs")
    # ENUM 값 제거는 PostgreSQL에서 지원하지 않음
