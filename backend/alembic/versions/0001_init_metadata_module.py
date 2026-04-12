"""init metadata module

Revision ID: 0001
Revises:
Create Date: 2026-04-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # cp_email_logs
    op.create_table(
        "cp_email_logs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("message_id", sa.String(500), unique=True, index=True, nullable=True),
        sa.Column("subject", sa.String(1000), nullable=True),
        sa.Column("sender", sa.String(500), nullable=True),
        sa.Column("cp_name", sa.String(200), index=True, nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extracted_titles", sa.JSON(), nullable=True),
        sa.Column("extracted_year", sa.Integer(), nullable=True),
        sa.Column("extracted_quantity", sa.Integer(), nullable=True),
        sa.Column("raw_body", sa.Text(), nullable=True),
        sa.Column("extraction_confidence", sa.Float(), nullable=True),
        sa.Column("processed", sa.Boolean(), default=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # contents
    op.create_table(
        "contents",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("title", sa.String(500), nullable=False, index=True),
        sa.Column("original_title", sa.String(500), nullable=True),
        sa.Column(
            "content_type",
            sa.Enum("movie", "series", "episode", name="contenttype"),
            nullable=False,
            server_default="movie",
        ),
        sa.Column(
            "status",
            sa.Enum("waiting", "processing", "review", "approved", "rejected", name="contentstatus"),
            nullable=False,
            server_default="waiting",
            index=True,
        ),
        sa.Column("cp_name", sa.String(200), index=True, nullable=True),
        sa.Column("cp_email_id", sa.Integer(), sa.ForeignKey("cp_email_logs.id"), nullable=True),
        sa.Column("production_year", sa.Integer(), nullable=True),
        sa.Column("runtime_minutes", sa.Integer(), nullable=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("contents.id"), nullable=True),
        sa.Column("season_number", sa.Integer(), nullable=True),
        sa.Column("episode_number", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, onupdate=sa.text("now()")),
    )

    # content_metadata
    op.create_table(
        "content_metadata",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("content_id", sa.Integer(), sa.ForeignKey("contents.id"), nullable=False, unique=True, index=True),
        sa.Column("cp_synopsis", sa.Text(), nullable=True),
        sa.Column("cp_genre", sa.String(200), nullable=True),
        sa.Column("cp_tags", sa.JSON(), nullable=True),
        sa.Column("cp_cast", sa.JSON(), nullable=True),
        sa.Column("cp_poster_url", sa.String(1000), nullable=True),
        sa.Column("ai_synopsis", sa.Text(), nullable=True),
        sa.Column("ai_genre_primary", sa.String(100), nullable=True),
        sa.Column("ai_genre_secondary", sa.String(100), nullable=True),
        sa.Column("ai_mood_tags", sa.JSON(), nullable=True),
        sa.Column("ai_cast", sa.JSON(), nullable=True),
        sa.Column("ai_rating_suggestion", sa.String(20), nullable=True),
        sa.Column("kobis_movie_cd", sa.String(20), index=True, nullable=True),
        sa.Column("kobis_data", sa.JSON(), nullable=True),
        sa.Column("tmdb_id", sa.Integer(), index=True, nullable=True),
        sa.Column("tmdb_data", sa.JSON(), nullable=True),
        sa.Column("final_synopsis", sa.Text(), nullable=True),
        sa.Column("final_genre", sa.String(200), nullable=True),
        sa.Column("final_tags", sa.JSON(), nullable=True),
        sa.Column("final_cast", sa.JSON(), nullable=True),
        sa.Column(
            "final_source",
            sa.Enum("cp", "ai", "kobis", "tmdb", "manual", name="metasource"),
            nullable=True,
            server_default="ai",
        ),
        sa.Column("quality_score", sa.Float(), default=0.0, index=True),
        sa.Column("score_breakdown", sa.JSON(), nullable=True),
        sa.Column("ai_processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(200), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # external_meta_cache
    op.create_table(
        "external_meta_cache",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("source", sa.String(20), index=True, nullable=True),
        sa.Column("external_id", sa.String(100), index=True, nullable=True),
        sa.Column("query_key", sa.String(500), index=True, nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("external_meta_cache")
    op.drop_table("content_metadata")
    op.drop_table("contents")
    op.drop_table("cp_email_logs")
    op.execute("DROP TYPE IF EXISTS metasource")
    op.execute("DROP TYPE IF EXISTS contentstatus")
    op.execute("DROP TYPE IF EXISTS contenttype")
