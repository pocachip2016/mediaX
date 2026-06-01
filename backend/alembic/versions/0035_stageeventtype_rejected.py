"""stageeventtype에 rejected 추가 (S4 검수 반려)

Revision ID: 0035
Revises: 0034
Create Date: 2026-06-01
"""
from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE stageeventtype ADD VALUE IF NOT EXISTS 'rejected'")


def downgrade():
    # PostgreSQL does not support removing enum values — no-op
    pass
