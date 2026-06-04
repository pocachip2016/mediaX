"""AI keywords 컬럼 추가 — ADR-007 Phase1 KeywordsTask

Revision ID: 0029
Revises: 0028
Create Date: 2026-05-30

content_metadata:
  + ai_keywords  JSON  추출 키워드 list[str]
"""
from alembic import op
import sqlalchemy as sa


revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("content_metadata") as batch_op:
        batch_op.add_column(sa.Column("ai_keywords", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("content_metadata") as batch_op:
        batch_op.drop_column("ai_keywords")
