"""external_curations + external_curation_items 테이블 — 외부 큐레이션 섹션 영속화

Revision ID: 0026
Revises: 0025
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_curations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("section_id", sa.String(200), nullable=False),
        sa.Column("section_name", sa.String(300), nullable=False),
        sa.Column("category_type", sa.String(50), nullable=False),
        sa.Column("trend_type", sa.String(20), nullable=False, server_default="ott"),
        sa.Column("season_tag", sa.String(50), nullable=True),
        sa.Column("collected_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("matched_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_count", sa.Integer, nullable=False, server_default="0"),
        sa.UniqueConstraint("channel", "section_id", name="uq_ext_curation_channel_section"),
    )
    op.create_index("ix_ext_curation_channel", "external_curations", ["channel"])

    op.create_table(
        "external_curation_items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("external_curation_id", sa.Integer,
                  sa.ForeignKey("external_curations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_id", sa.Integer,
                  sa.ForeignKey("contents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("external_title", sa.String(300), nullable=False),
        sa.Column("external_rank", sa.Integer, nullable=False),
        sa.Column("production_year", sa.Integer, nullable=True),
        sa.UniqueConstraint("external_curation_id", "external_rank", name="uq_ext_item_rank"),
    )
    op.create_index("ix_ext_item_content_id", "external_curation_items", ["content_id"])


def downgrade() -> None:
    op.drop_index("ix_ext_item_content_id", "external_curation_items")
    op.drop_table("external_curation_items")
    op.drop_index("ix_ext_curation_channel", "external_curations")
    op.drop_table("external_curations")
