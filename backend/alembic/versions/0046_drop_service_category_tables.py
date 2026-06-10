"""drop service_categories + service_category_items (큐레이션 노드 어댑터 전환 완료)

Revision ID: 0046
Revises: 0045
Create Date: 2026-06-09
"""
import sqlalchemy as sa
from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_cat_item_rank", table_name="service_category_items")
    op.drop_constraint("uq_cat_item_content", "service_category_items", type_="unique")
    op.drop_table("service_category_items")
    op.drop_table("service_categories")


def downgrade() -> None:
    op.create_table(
        "service_categories",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category_type", sa.String(50), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("headline_copy", sa.String(200), nullable=True),
        sa.Column("sub_copy", sa.String(300), nullable=True),
        sa.Column("theme_features", sa.JSON, nullable=True),
        sa.Column("source_mode", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("reference_external_id", sa.String(200), nullable=True),
        sa.Column("is_draft", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "service_category_items",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("service_categories.id"), nullable=False),
        sa.Column("content_id", sa.Integer(), sa.ForeignKey("contents.id"), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("added_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_cat_item_rank", "service_category_items", ["category_id", "rank"])
    op.create_unique_constraint("uq_cat_item_content", "service_category_items", ["category_id", "content_id"])
