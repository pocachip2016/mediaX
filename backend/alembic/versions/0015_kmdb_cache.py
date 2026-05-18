"""KMDB 영화 캐시 테이블 추가 + TmdbSyncSource에 kmdb_daily/kmdb_backfill 추가

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-18

변경 내용:
  - kmdb_movie_cache : 한국 영화 메타 캐시 (PK = DOCID)
  - tmdbsyncsource ENUM에 kmdb_daily / kmdb_backfill 추가 (PostgreSQL)
"""

from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        now_default = "CURRENT_TIMESTAMP"
    else:
        now_default = "now()"

    # ── TmdbSyncSource ENUM 확장 (PostgreSQL only) ─────────────────────
    if dialect == "postgresql":
        op.execute("ALTER TYPE tmdbsyncsource ADD VALUE IF NOT EXISTS 'kmdb_daily'")
        op.execute("ALTER TYPE tmdbsyncsource ADD VALUE IF NOT EXISTS 'kmdb_backfill'")

    # ── kmdb_movie_cache ───────────────────────────────────────────────
    op.create_table(
        "kmdb_movie_cache",
        sa.Column("docid", sa.String(50), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("title_eng", sa.String(500)),
        sa.Column("title_org", sa.String(500)),
        sa.Column("prod_year", sa.Integer),
        sa.Column("nation", sa.String(200)),
        sa.Column("genre", sa.String(200)),
        sa.Column("runtime", sa.Integer),
        sa.Column("poster_url", sa.Text),
        sa.Column("synopsis", sa.Text),
        sa.Column("directors", sa.JSON),
        sa.Column("actors", sa.JSON),
        sa.Column("raw_json", sa.JSON),
        sa.Column("first_fetched_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text(now_default), nullable=False),
        sa.Column("last_fetched_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text(now_default), nullable=False),
    )
    op.create_index("ix_kmdb_movie_cache_title", "kmdb_movie_cache", ["title"])
    op.create_index("ix_kmdb_movie_cache_prod_year", "kmdb_movie_cache", ["prod_year"])
    op.create_index("ix_kmdb_movie_cache_last_fetched_at", "kmdb_movie_cache", ["last_fetched_at"])


def downgrade() -> None:
    op.drop_index("ix_kmdb_movie_cache_last_fetched_at", "kmdb_movie_cache")
    op.drop_index("ix_kmdb_movie_cache_prod_year", "kmdb_movie_cache")
    op.drop_index("ix_kmdb_movie_cache_title", "kmdb_movie_cache")
    op.drop_table("kmdb_movie_cache")
    # PostgreSQL ENUM 값 제거는 불가 (PostgreSQL 제약)
