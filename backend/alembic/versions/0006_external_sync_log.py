"""tmdb_sync_log → external_sync_log + external_source 컬럼

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    # 1. 테이블 rename
    op.rename_table("tmdb_sync_log", "external_sync_log")

    # 2. external_source 컬럼 추가 (nullable — 기존 행은 backfill 로 채움)
    op.add_column(
        "external_sync_log",
        sa.Column("external_source", sa.String(50), nullable=True),
    )

    # 3. 기존 행 backfill — 모두 tmdb
    op.execute("UPDATE external_sync_log SET external_source = 'tmdb'")

    # 4. started_at / external_source 복합 인덱스
    op.create_index("ix_external_sync_log_external_source",
                    "external_sync_log", ["external_source"])


def downgrade():
    op.drop_index("ix_external_sync_log_external_source", "external_sync_log")
    op.drop_column("external_sync_log", "external_source")
    op.rename_table("external_sync_log", "tmdb_sync_log")
