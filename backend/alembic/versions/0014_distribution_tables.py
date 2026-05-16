"""distribution tables — content_distributions / service_categories / service_category_items / device_variants

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-16
"""
import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "content_distributions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("content_id", sa.Integer(), sa.ForeignKey("contents.id"), nullable=False),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("channel_type", sa.String(20), nullable=False),
        sa.Column("external_id", sa.String(200)),
        sa.Column("available_from", sa.Date()),
        sa.Column("available_until", sa.Date()),
        sa.Column("is_exclusive", sa.Boolean(), server_default=sa.false()),
        sa.Column("popularity_rank", sa.Integer()),
        sa.Column("popularity_score", sa.Float()),
        sa.Column("raw_data", sa.JSON()),
        sa.Column("synced_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("content_id", "channel", name="uq_distribution_content_channel"),
    )
    op.create_index("ix_dist_channel_type", "content_distributions", ["channel", "channel_type"])
    op.create_index("ix_dist_content_id", "content_distributions", ["content_id"])

    op.create_table(
        "service_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category_type", sa.String(50), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "service_category_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("service_categories.id"), nullable=False),
        sa.Column("content_id", sa.Integer(), sa.ForeignKey("contents.id"), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float()),
        sa.Column("added_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("category_id", "content_id", name="uq_cat_item_content"),
    )
    op.create_index("ix_cat_item_rank", "service_category_items", ["category_id", "rank"])

    op.create_table(
        "device_variants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("content_id", sa.Integer(), sa.ForeignKey("contents.id"), nullable=False),
        sa.Column("device_type", sa.String(20), nullable=False),
        sa.Column("resolution", sa.String(20)),
        sa.Column("format", sa.String(20)),
        sa.Column("bitrate_kbps", sa.Integer()),
        sa.Column("drm_type", sa.String(50)),
        sa.Column("is_available", sa.Boolean(), server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("content_id", "device_type", "resolution", name="uq_device_content_type_res"),
    )
    op.create_index("ix_device_content_id", "device_variants", ["content_id"])


def downgrade():
    op.drop_index("ix_device_content_id", "device_variants")
    op.drop_table("device_variants")
    op.drop_index("ix_cat_item_rank", "service_category_items")
    op.drop_table("service_category_items")
    op.drop_table("service_categories")
    op.drop_index("ix_dist_content_id", "content_distributions")
    op.drop_index("ix_dist_channel_type", "content_distributions")
    op.drop_table("content_distributions")
