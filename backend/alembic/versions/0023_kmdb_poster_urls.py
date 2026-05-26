"""kmdb_movie_cache — poster_urls / stillcut_urls JSON 컬럼 추가

Revision ID: 0023
Revises: 0022
Create Date: 2026-05-26

기존 poster_url (단일, 하위호환) 은 유지하고
다중 URL 리스트를 JSON 컬럼으로 추가한다.
"""
from alembic import op
import sqlalchemy as sa

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("kmdb_movie_cache", sa.Column("poster_urls", sa.JSON(), nullable=True))
    op.add_column("kmdb_movie_cache", sa.Column("stillcut_urls", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("kmdb_movie_cache", "stillcut_urls")
    op.drop_column("kmdb_movie_cache", "poster_urls")
