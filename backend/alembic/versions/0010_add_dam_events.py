"""dam_events 테이블 추가 — Dam 자산 매핑 피드백 수신 로그

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-09
"""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "dam_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("content_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.String(200), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("match_method", sa.String(50), nullable=True),
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("payload_json", sa.JSON()),
        sa.Column("received_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_dam_events_event_type", "dam_events", ["event_type"])
    op.create_index("ix_dam_events_content_id", "dam_events", ["content_id"])
    op.create_index("ix_dam_events_asset_id", "dam_events", ["asset_id"])
    op.create_index("ix_dam_events_received_at", "dam_events", ["received_at"])


def downgrade():
    op.drop_index("ix_dam_events_received_at", table_name="dam_events")
    op.drop_index("ix_dam_events_asset_id", table_name="dam_events")
    op.drop_index("ix_dam_events_content_id", table_name="dam_events")
    op.drop_index("ix_dam_events_event_type", table_name="dam_events")
    op.drop_table("dam_events")
