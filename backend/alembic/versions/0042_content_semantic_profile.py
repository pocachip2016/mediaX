"""content_semantic_profile — ingest-time CUP (facets / keywords / embed_synopsis / embed_dialogue / embed_visual / essence / provenance)

Revision ID: 0042
Revises: 0041
Create Date: 2026-06-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        CREATE TABLE content_semantic_profiles (
            id              SERIAL PRIMARY KEY,
            content_id      INTEGER NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
            facets          JSONB,
            keywords        JSONB,
            embed_synopsis  JSONB,
            embed_dialogue  JSONB,
            embed_visual    JSONB,
            essence         TEXT,
            provenance      JSONB,
            model_version   VARCHAR(80),
            computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_content_semantic_profile_content_id UNIQUE (content_id)
        )
    """))
    op.create_index("ix_content_semantic_profiles_content_id", "content_semantic_profiles", ["content_id"])


def downgrade() -> None:
    op.drop_index("ix_content_semantic_profiles_content_id", table_name="content_semantic_profiles")
    op.execute(sa.text("DROP TABLE IF EXISTS content_semantic_profiles"))
