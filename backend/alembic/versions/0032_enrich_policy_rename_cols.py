"""enrich_policy rename cols: auto_apply_confirmed→use_cache_db, auto_chain_to_ai→use_websearch

Revision ID: 0032
Revises: 0031
Create Date: 2026-05-30
"""
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("enrich_policy", "auto_apply_confirmed", new_column_name="use_cache_db")
    op.alter_column("enrich_policy", "auto_chain_to_ai",     new_column_name="use_websearch")


def downgrade():
    op.alter_column("enrich_policy", "use_cache_db",  new_column_name="auto_apply_confirmed")
    op.alter_column("enrich_policy", "use_websearch", new_column_name="auto_chain_to_ai")
