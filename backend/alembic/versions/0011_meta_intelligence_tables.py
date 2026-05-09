"""meta_intelligence 테이블 신설 + ExternalSourceType ENUM 에 kmdb 추가

테이블:
  - metadata_candidates  : 정규화된 외부 후보 메타
  - match_edges          : candidate ↔ Content 매칭 (점수 + 사유)
  - field_suggestions    : 필드 단위 raw 후보값
  - field_resolutions    : (content_id, field_name) 당 결정 1행 — audit trail
  - seed_candidates      : 신규 콘텐츠 후보 (Phase C 에서 본격 사용)

ENUM 확장:
  - externalsourcetype += 'kmdb'  (한국영상자료원)

external_sync_log 컬럼 추가:
  - auto_resolved_count  : 해당 sync 사이클의 자동 확정 field_resolution 수
  - manual_review_count  : 검수 큐로 들어간 수

참조: docs/dev/meta-intelligence.md

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-09
"""
import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # 1. ExternalSourceType ENUM 에 kmdb 추가 (PostgreSQL 전용)
    if is_pg:
        op.execute("ALTER TYPE externalsourcetype ADD VALUE IF NOT EXISTS 'kmdb'")

    # 2. metadata_candidates — 정규화된 외부 후보 메타
    op.create_table(
        "metadata_candidates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_external_id", sa.String(255), nullable=False),
        sa.Column("source_url", sa.String(2000)),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("title_norm", sa.String(500), nullable=False),
        sa.Column("original_title", sa.String(500)),
        sa.Column("year", sa.Integer()),
        sa.Column("content_type", sa.String(20)),
        sa.Column("synopsis", sa.Text()),
        sa.Column("poster_url", sa.String(2000)),
        sa.Column("cast_json", sa.JSON()),
        sa.Column("director_json", sa.JSON()),
        sa.Column("genre_json", sa.JSON()),
        sa.Column("external_ids_json", sa.JSON()),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.UniqueConstraint("source_type", "source_external_id", name="uq_candidate_source"),
    )
    op.create_index("ix_metadata_candidates_source_type", "metadata_candidates", ["source_type"])
    op.create_index("ix_metadata_candidates_title_year", "metadata_candidates", ["title_norm", "year"])
    op.create_index("ix_metadata_candidates_fetched_at", "metadata_candidates", ["fetched_at"])
    op.create_index("ix_metadata_candidates_status", "metadata_candidates", ["status"])

    # 3. match_edges — candidate ↔ Content 매칭
    op.create_table(
        "match_edges",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("candidate_id", sa.Integer(),
                  sa.ForeignKey("metadata_candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_id", sa.Integer(),
                  sa.ForeignKey("contents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("reasons_json", sa.JSON(), nullable=False),
        sa.Column("sub_scores_json", sa.JSON()),
        sa.Column("decided", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("decided_by", sa.String(100)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("candidate_id", "content_id", name="uq_match_edge"),
    )
    op.create_index("ix_match_edges_candidate_id", "match_edges", ["candidate_id"])
    op.create_index("ix_match_edges_content_id", "match_edges", ["content_id"])
    op.create_index("ix_match_edges_score", "match_edges", ["score"])

    # 4. field_suggestions — 필드 단위 raw 후보
    op.create_table(
        "field_suggestions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("content_id", sa.Integer(),
                  sa.ForeignKey("contents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_name", sa.String(50), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("source_candidate_id", sa.Integer(),
                  sa.ForeignKey("metadata_candidates.id", ondelete="SET NULL")),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_field_suggestions_content_field", "field_suggestions",
                    ["content_id", "field_name"])
    op.create_index("ix_field_suggestions_status", "field_suggestions", ["status"])

    # 5. field_resolutions — (content_id, field_name) 당 결정 1행
    op.create_table(
        "field_resolutions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("content_id", sa.Integer(),
                  sa.ForeignKey("contents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_name", sa.String(50), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("chosen_value_json", sa.JSON()),
        sa.Column("chosen_suggestion_ids", sa.JSON()),
        sa.Column("agreement_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("agreeing_sources_json", sa.JSON()),
        sa.Column("merge_method", sa.String(20)),
        sa.Column("applied_to_content", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("decided_by", sa.String(100)),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("content_id", "field_name", name="uq_field_resolution"),
    )
    op.create_index("ix_field_resolutions_content_id", "field_resolutions", ["content_id"])
    op.create_index("ix_field_resolutions_decision", "field_resolutions", ["decision"])
    op.create_index("ix_field_resolutions_applied", "field_resolutions", ["applied_to_content"])

    # 6. seed_candidates — 신규 콘텐츠 후보
    op.create_table(
        "seed_candidates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("candidate_id", sa.Integer(),
                  sa.ForeignKey("metadata_candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(20)),
        sa.Column("evidence_urls_json", sa.JSON()),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("reason_json", sa.JSON()),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending_review"),
        sa.Column("created_content_id", sa.Integer(),
                  sa.ForeignKey("contents.id", ondelete="SET NULL")),
        sa.Column("decided_by", sa.String(100)),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_seed_candidates_status", "seed_candidates", ["status"])
    op.create_index("ix_seed_candidates_created_at", "seed_candidates", ["created_at"])

    # 7. external_sync_log 모니터링 컬럼 추가
    op.add_column("external_sync_log",
                  sa.Column("auto_resolved_count", sa.Integer(), server_default="0"))
    op.add_column("external_sync_log",
                  sa.Column("manual_review_count", sa.Integer(), server_default="0"))


def downgrade():
    op.drop_column("external_sync_log", "manual_review_count")
    op.drop_column("external_sync_log", "auto_resolved_count")

    op.drop_index("ix_seed_candidates_created_at", table_name="seed_candidates")
    op.drop_index("ix_seed_candidates_status", table_name="seed_candidates")
    op.drop_table("seed_candidates")

    op.drop_index("ix_field_resolutions_applied", table_name="field_resolutions")
    op.drop_index("ix_field_resolutions_decision", table_name="field_resolutions")
    op.drop_index("ix_field_resolutions_content_id", table_name="field_resolutions")
    op.drop_table("field_resolutions")

    op.drop_index("ix_field_suggestions_status", table_name="field_suggestions")
    op.drop_index("ix_field_suggestions_content_field", table_name="field_suggestions")
    op.drop_table("field_suggestions")

    op.drop_index("ix_match_edges_score", table_name="match_edges")
    op.drop_index("ix_match_edges_content_id", table_name="match_edges")
    op.drop_index("ix_match_edges_candidate_id", table_name="match_edges")
    op.drop_table("match_edges")

    op.drop_index("ix_metadata_candidates_status", table_name="metadata_candidates")
    op.drop_index("ix_metadata_candidates_fetched_at", table_name="metadata_candidates")
    op.drop_index("ix_metadata_candidates_title_year", table_name="metadata_candidates")
    op.drop_index("ix_metadata_candidates_source_type", table_name="metadata_candidates")
    op.drop_table("metadata_candidates")

    # PostgreSQL ENUM 값 제거 불가 (PostgreSQL 제약)
