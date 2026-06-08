"""drop legacy category tables — categories, content_categories, category_sets

All tree/mapping logic has migrated to programming_nodes + programming_links.
These tables are no longer referenced by application code.

Revision ID: 0044
Revises: 0043
Create Date: 2026-06-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 의존 순서: content_categories → categories → category_sets
    op.drop_index("ix_content_categories_category_id", table_name="content_categories")
    op.drop_index("ix_content_categories_content_id", table_name="content_categories")
    op.drop_table("content_categories")

    op.drop_index("ix_categories_set_id", table_name="categories")
    op.drop_index("ix_categories_parent_sort", table_name="categories")
    op.drop_index("ix_categories_parent_id", table_name="categories")
    op.drop_table("categories")

    op.drop_table("category_sets")


def downgrade() -> None:
    op.create_table(
        "category_sets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("set_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(120), nullable=True),
        sa.Column("depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["parent_id"], ["categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["set_id"], ["category_sets.id"], ondelete="CASCADE", name="fk_categories_set_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_categories_parent_id", "categories", ["parent_id"])
    op.create_index("ix_categories_parent_sort", "categories", ["parent_id", "sort_order"])
    op.create_index("ix_categories_set_id", "categories", ["set_id"])

    op.create_table(
        "content_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_id"], ["contents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_id", "category_id", name="uq_content_category"),
    )
    op.create_index("ix_content_categories_content_id", "content_categories", ["content_id"])
    op.create_index("ix_content_categories_category_id", "content_categories", ["category_id"])
