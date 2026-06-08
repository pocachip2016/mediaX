"""category sets — category_sets table + categories.set_id (draft = set_id NULL)

Revision ID: 0043
Revises: 0042
Create Date: 2026-06-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "category_sets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    # categories.set_id — NULL = 작업 디렉토리(draft), N = 세트 N 소속
    op.add_column("categories", sa.Column("set_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_categories_set_id",
        "categories",
        "category_sets",
        ["set_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_categories_set_id", "categories", ["set_id"])


def downgrade() -> None:
    op.drop_index("ix_categories_set_id", table_name="categories")
    op.drop_constraint("fk_categories_set_id", "categories", type_="foreignkey")
    op.drop_column("categories", "set_id")
    op.drop_table("category_sets")
