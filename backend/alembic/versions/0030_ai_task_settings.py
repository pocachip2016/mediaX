"""AI Task 설정 테이블 추가 — ADR-007 B4 항목별 on/off

Revision ID: 0030
Revises: 0029
Create Date: 2026-05-30

ai_task_settings:
  task_name  VARCHAR(100) PK   — AITaskType value
  enabled    BOOLEAN           — on/off (기본 true)
  updated_at TIMESTAMPTZ
"""
from alembic import op
import sqlalchemy as sa


revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_task_settings",
        sa.Column("task_name", sa.String(100), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # 기본 시드: 등록된 모든 task enabled=true
    op.execute("""
        INSERT INTO ai_task_settings (task_name, enabled) VALUES
        ('translate_synopsis', true),
        ('short_synopsis', true),
        ('genre_normalized', true),
        ('mood_tags', true),
        ('keywords', true)
        ON CONFLICT (task_name) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table("ai_task_settings")
