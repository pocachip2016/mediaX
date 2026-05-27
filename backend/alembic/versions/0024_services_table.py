"""services table — OTT/IPTV 출처 SSOT + 5건 seed

Revision ID: 0024
Revises: 0023
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "services",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(datetime('now'))")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(datetime('now'))")),
    )
    op.create_index("ix_services_code", "services", ["code"], unique=True)
    op.create_index("ix_services_kind", "services", ["kind"])

    op.bulk_insert(
        sa.table(
            "services",
            sa.column("code", sa.String),
            sa.column("name", sa.String),
            sa.column("kind", sa.String),
            sa.column("position", sa.Integer),
            sa.column("is_active", sa.Boolean),
        ),
        [
            {"code": "ott_watcha", "name": "Watcha", "kind": "ott", "position": 1, "is_active": True},
            {"code": "ott_netflix", "name": "Netflix", "kind": "ott", "position": 2, "is_active": True},
            {"code": "ott_wave", "name": "Wave", "kind": "ott", "position": 3, "is_active": True},
            {"code": "ott_tving", "name": "Tving", "kind": "ott", "position": 4, "is_active": True},
            {"code": "iptv_genie", "name": "지니TV", "kind": "iptv", "position": 5, "is_active": True},
        ],
    )


def downgrade():
    op.drop_index("ix_services_kind", "services")
    op.drop_index("ix_services_code", "services")
    op.drop_table("services")
