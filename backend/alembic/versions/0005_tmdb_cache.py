"""TMDB 로컬 캐시 테이블 추가

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-06

변경 내용:
  - tmdb_movie_cache  : 영화 메타 캐시 (PK = TMDB movie_id)
  - tmdb_tv_cache     : TV 시리즈 메타 캐시 (PK = TMDB tv_id)
  - tmdb_person_cache : 인물 메타 캐시 (PK = TMDB person_id)
  - tmdb_sync_log     : 동기화 실행 이력
  - ENUM: tmdbsyncsource, tmdbbsyncstatus (PostgreSQL only)
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        now_default = "datetime('now')"
    else:
        now_default = "now()"

    # ── PostgreSQL ENUM 타입 생성 ───────────────────────────────────────
    if dialect == "postgresql":
        op.execute("""
            DO $$ BEGIN
                CREATE TYPE tmdbsyncsource AS ENUM (
                    'discover_movie', 'discover_tv',
                    'changes_movie', 'changes_tv',
                    'backfill_movie_year', 'backfill_tv_year'
                );
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
        """)
        op.execute("""
            DO $$ BEGIN
                CREATE TYPE tmdbbsyncstatus AS ENUM ('running', 'completed', 'failed');
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
        """)

    # ── tmdb_movie_cache ───────────────────────────────────────────────
    op.create_table(
        "tmdb_movie_cache",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("original_title", sa.String(500)),
        sa.Column("original_language", sa.String(10)),
        sa.Column("release_date", sa.Date),
        sa.Column("runtime", sa.Integer),
        sa.Column("popularity", sa.Float),
        sa.Column("vote_average", sa.Float),
        sa.Column("vote_count", sa.Integer),
        sa.Column("adult", sa.Boolean, default=False),
        sa.Column("poster_path", sa.String(500)),
        sa.Column("backdrop_path", sa.String(500)),
        sa.Column("overview", sa.Text),
        sa.Column("genre_ids", sa.JSON),
        sa.Column("raw_json", sa.JSON),
        sa.Column("first_fetched_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text(now_default), nullable=False),
        sa.Column("last_fetched_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text(now_default), nullable=False),
    )
    op.create_index("ix_tmdb_movie_cache_release_date", "tmdb_movie_cache", ["release_date"])
    op.create_index("ix_tmdb_movie_cache_popularity", "tmdb_movie_cache", ["popularity"])
    op.create_index("ix_tmdb_movie_cache_last_fetched_at", "tmdb_movie_cache", ["last_fetched_at"])

    # ── tmdb_tv_cache ──────────────────────────────────────────────────
    op.create_table(
        "tmdb_tv_cache",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("original_name", sa.String(500)),
        sa.Column("original_language", sa.String(10)),
        sa.Column("first_air_date", sa.Date),
        sa.Column("last_air_date", sa.Date),
        sa.Column("number_of_seasons", sa.Integer),
        sa.Column("number_of_episodes", sa.Integer),
        sa.Column("status", sa.String(100)),
        sa.Column("popularity", sa.Float),
        sa.Column("vote_average", sa.Float),
        sa.Column("vote_count", sa.Integer),
        sa.Column("poster_path", sa.String(500)),
        sa.Column("backdrop_path", sa.String(500)),
        sa.Column("overview", sa.Text),
        sa.Column("genre_ids", sa.JSON),
        sa.Column("raw_json", sa.JSON),
        sa.Column("first_fetched_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text(now_default), nullable=False),
        sa.Column("last_fetched_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text(now_default), nullable=False),
    )
    op.create_index("ix_tmdb_tv_cache_first_air_date", "tmdb_tv_cache", ["first_air_date"])
    op.create_index("ix_tmdb_tv_cache_popularity", "tmdb_tv_cache", ["popularity"])

    # ── tmdb_person_cache ──────────────────────────────────────────────
    op.create_table(
        "tmdb_person_cache",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("also_known_as", sa.JSON),
        sa.Column("birthday", sa.Date),
        sa.Column("deathday", sa.Date),
        sa.Column("profile_path", sa.String(500)),
        sa.Column("popularity", sa.Float),
        sa.Column("raw_json", sa.JSON),
        sa.Column("first_fetched_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text(now_default), nullable=False),
        sa.Column("last_fetched_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text(now_default), nullable=False),
    )

    # ── tmdb_sync_log ──────────────────────────────────────────────────
    if dialect == "postgresql":
        source_type = sa.Enum("discover_movie", "discover_tv",
                               "changes_movie", "changes_tv",
                               "backfill_movie_year", "backfill_tv_year",
                               name="tmdbsyncsource", create_type=False)
        status_type = sa.Enum("running", "completed", "failed",
                               name="tmdbbsyncstatus", create_type=False)
    else:
        source_type = sa.String(50)
        status_type = sa.String(20)

    op.create_table(
        "tmdb_sync_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("source", source_type, nullable=False),
        sa.Column("target_year", sa.Integer),
        sa.Column("target_date", sa.Date),
        sa.Column("status", status_type, nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text(now_default), nullable=False),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("pages_fetched", sa.Integer, default=0),
        sa.Column("items_fetched", sa.Integer, default=0),
        sa.Column("items_inserted", sa.Integer, default=0),
        sa.Column("items_updated", sa.Integer, default=0),
        sa.Column("items_unchanged", sa.Integer, default=0),
        sa.Column("errors", sa.Integer, default=0),
        sa.Column("error_sample", sa.JSON),
    )
    op.create_index("ix_tmdb_sync_log_started_at", "tmdb_sync_log", ["started_at"])
    op.create_index("ix_tmdb_sync_log_source_year", "tmdb_sync_log", ["source", "target_year"])
    op.create_index("ix_tmdb_sync_log_target_date", "tmdb_sync_log", ["target_date"])


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    op.drop_index("ix_tmdb_sync_log_target_date", "tmdb_sync_log")
    op.drop_index("ix_tmdb_sync_log_source_year", "tmdb_sync_log")
    op.drop_index("ix_tmdb_sync_log_started_at", "tmdb_sync_log")
    op.drop_table("tmdb_sync_log")

    op.drop_table("tmdb_person_cache")

    op.drop_index("ix_tmdb_tv_cache_popularity", "tmdb_tv_cache")
    op.drop_index("ix_tmdb_tv_cache_first_air_date", "tmdb_tv_cache")
    op.drop_table("tmdb_tv_cache")

    op.drop_index("ix_tmdb_movie_cache_last_fetched_at", "tmdb_movie_cache")
    op.drop_index("ix_tmdb_movie_cache_popularity", "tmdb_movie_cache")
    op.drop_index("ix_tmdb_movie_cache_release_date", "tmdb_movie_cache")
    op.drop_table("tmdb_movie_cache")

    if dialect == "postgresql":
        op.execute("DROP TYPE IF EXISTS tmdbbsyncstatus")
        op.execute("DROP TYPE IF EXISTS tmdbsyncsource")
