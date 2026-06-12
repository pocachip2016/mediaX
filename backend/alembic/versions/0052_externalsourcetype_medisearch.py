"""externalsourcetype에 medisearch 추가

Revision ID: 0052
Revises: 0051
Create Date: 2026-06-12
"""
from alembic import op

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE externalsourcetype ADD VALUE IF NOT EXISTS 'medisearch'")


def downgrade() -> None:
    pass  # PG enum 값 제거는 지원 안 함
