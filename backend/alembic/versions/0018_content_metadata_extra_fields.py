"""content_metadata: audio_channels + extra_metadata

Revision ID: 0018
Revises: 0017_widen_ai_genre_rating_columns
Create Date: 2026-05-18

추가 컬럼:
  - audio_channels  VARCHAR(20)   — "5.1CH" / "Stereo" / "Atmos"
  - extra_metadata  JSONB (PG) / JSON (SQLite) — 미정 CSV 컬럼 흡수
"""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("content_metadata") as batch_op:
        batch_op.add_column(sa.Column("audio_channels", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("extra_metadata", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("content_metadata") as batch_op:
        batch_op.drop_column("extra_metadata")
        batch_op.drop_column("audio_channels")
