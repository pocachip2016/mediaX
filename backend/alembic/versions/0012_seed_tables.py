"""Phase C SEED 테이블 신설 + ExternalSourceType.omdb + MetadataCandidate target_type/id

테이블:
  - content_seeds       : SEED 라이프사이클 (discovered→candidate→under_review→accepted/rejected)
  - seed_discovery_log  : 소스별 발굴 회차 통계

ENUM 확장:
  - externalsourcetype += 'omdb'  (OMDb IMDb 글로벌 보완)

MetadataCandidate 컬럼 추가:
  - target_type VARCHAR(20) DEFAULT 'content'  — content | content_seed
  - target_id   INT NULL                       — content_id 또는 content_seed_id

참조: docs/dev/phase-c/_index.md

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-10
"""
import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # 1. ExternalSourceType ENUM 에 omdb 추가 (PostgreSQL 전용)
    if is_pg:
        op.execute("ALTER TYPE externalsourcetype ADD VALUE IF NOT EXISTS 'omdb'")

    # 2. content_seeds — SEED 라이프사이클 메인 테이블
    op.create_table(
        "content_seeds",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("original_title", sa.String(500), nullable=True),
        sa.Column("content_type", sa.String(20), nullable=True),
        sa.Column("production_year", sa.Integer(), nullable=True),
        sa.Column("poster_url", sa.Text(), nullable=True),
        sa.Column("synopsis", sa.Text(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="candidate"),
        # status: discovered | candidate | under_review | accepted | rejected
        sa.Column("locked_by", sa.String(64), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("promoted_to_content_id", sa.Integer(),
                  sa.ForeignKey("contents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("suspected_match_content_id", sa.Integer(),
                  sa.ForeignKey("contents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("alt_external_ids", sa.JSON(), nullable=False, server_default="{}"),
        sa.UniqueConstraint("source_type", "external_id", name="uq_content_seed_source"),
    )
    op.create_index("ix_content_seeds_status_discovered", "content_seeds",
                    ["status", "discovered_at"])
    op.create_index("ix_content_seeds_content_type_year", "content_seeds",
                    ["content_type", "production_year"])

    # 3. seed_discovery_log — 발굴 회차별 통계
    op.create_table(
        "seed_discovery_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("discovery_mode", sa.String(30), nullable=False),
        # discovery_mode: trending_day | trending_week | upcoming | discover
        #                 new_release | box_office | other
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("total_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_seeds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matched_existing", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("dedup_decision", sa.String(30), nullable=True),
        # dedup_decision: appended_to_content | appended_to_seed | created_seed
        sa.Column("discovery_params", sa.JSON(), nullable=True),
    )
    op.create_index("ix_seed_discovery_log_source_fetched", "seed_discovery_log",
                    ["source_type", "fetched_at"])

    # 4. MetadataCandidate 에 target_type / target_id 추가
    op.add_column("metadata_candidates",
                  sa.Column("target_type", sa.String(20), nullable=False, server_default="content"))
    op.add_column("metadata_candidates",
                  sa.Column("target_id", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("metadata_candidates", "target_id")
    op.drop_column("metadata_candidates", "target_type")

    op.drop_index("ix_seed_discovery_log_source_fetched", table_name="seed_discovery_log")
    op.drop_table("seed_discovery_log")

    op.drop_index("ix_content_seeds_content_type_year", table_name="content_seeds")
    op.drop_index("ix_content_seeds_status_discovered", table_name="content_seeds")
    op.drop_table("content_seeds")
    # NOTE: omdb ENUM 값은 PostgreSQL 에서 되돌릴 수 없음 (VALUE 제거 미지원)
