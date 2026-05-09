"""content_metadata 레거시 컬럼 제거 — kobis_movie_cd/kobis_data/tmdb_id

ExternalMetaSource가 SSOT로 완성됐으므로 듀얼라이트 기간 종료.

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-09
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    # 인덱스를 먼저 삭제 (SQLite도 named index가 있으면 DROP COLUMN 전에 삭제 필요)
    _drop_index_if_exists("ix_content_metadata_kobis_movie_cd", "content_metadata")
    _drop_index_if_exists("ix_content_metadata_tmdb_id", "content_metadata")
    op.drop_column("content_metadata", "kobis_movie_cd")
    op.drop_column("content_metadata", "kobis_data")
    op.drop_column("content_metadata", "tmdb_id")


def downgrade():
    op.add_column("content_metadata", sa.Column("tmdb_id", sa.Integer(), nullable=True))
    op.add_column("content_metadata", sa.Column("kobis_data", sa.JSON(), nullable=True))
    op.add_column("content_metadata", sa.Column("kobis_movie_cd", sa.String(20), nullable=True))
    op.create_index("ix_content_metadata_kobis_movie_cd", "content_metadata", ["kobis_movie_cd"])
    op.create_index("ix_content_metadata_tmdb_id", "content_metadata", ["tmdb_id"])


def _drop_index_if_exists(index_name: str, table_name: str):
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        result = bind.execute(
            sa.text(f"SELECT name FROM sqlite_master WHERE type='index' AND name='{index_name}'")
        )
        if not result.fetchone():
            return
    try:
        op.drop_index(index_name, table_name=table_name)
    except Exception:
        pass
