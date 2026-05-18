"""Add kobis_movie_cache table

Revision ID: 0020
Revises: 0019
Create Date: 2026-05-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    now_default = "now()" if bind.dialect.name == "postgresql" else "CURRENT_TIMESTAMP"

    op.create_table(
        "kobis_movie_cache",
        sa.Column("movie_cd", sa.String(20), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("title_en", sa.String(500)),
        sa.Column("open_dt", sa.Date),
        sa.Column("prdt_year", sa.Integer),
        sa.Column("type_nm", sa.String(100)),
        sa.Column("prdt_stat_nm", sa.String(100)),
        sa.Column("nation_alt", sa.String(200)),
        sa.Column("genre_alt", sa.String(200)),
        sa.Column("rep_nation_nm", sa.String(100)),
        sa.Column("rep_genre_nm", sa.String(100)),
        sa.Column("directors", sa.JSON),
        sa.Column("raw_json", sa.JSON),
        sa.Column("first_fetched_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text(now_default), nullable=False),
        sa.Column("last_fetched_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text(now_default), nullable=False),
    )
    op.create_index("ix_kobis_movie_cache_title", "kobis_movie_cache", ["title"])
    op.create_index("ix_kobis_movie_cache_prdt_year", "kobis_movie_cache", ["prdt_year"])
    op.create_index("ix_kobis_movie_cache_open_dt", "kobis_movie_cache", ["open_dt"])


def downgrade() -> None:
    op.drop_index("ix_kobis_movie_cache_open_dt", "kobis_movie_cache")
    op.drop_index("ix_kobis_movie_cache_prdt_year", "kobis_movie_cache")
    op.drop_index("ix_kobis_movie_cache_title", "kobis_movie_cache")
    op.drop_table("kobis_movie_cache")
