"""Pipeline stage model — 9-stage + stage_event table (ADR-006)

Revision ID: 0022
Revises: 0021
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PgEnum

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade():
    # ── enum types ────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TYPE pipelinestage AS ENUM (
            's1_intake','s2_normalize','s3_llm_extract','s4_source_match',
            's5_gap_detect','s6_websearch_fill','s7_staging','s8_review','s9_publish'
        )
    """)
    op.execute("""
        CREATE TYPE intakechannel AS ENUM (
            'email_poll','manual','bulk_csv','dam_webhook'
        )
    """)
    op.execute("""
        CREATE TYPE stageeventtype AS ENUM (
            'entered','completed','skipped','failed','retried','gate_opened','advanced'
        )
    """)
    op.execute("""
        CREATE TYPE failurecode AS ENUM (
            'none','llm_parse_error','tmdb_quota_exceeded','kobis_timeout',
            'websearch_no_hit','invalid_payload','system_error'
        )
    """)

    _pipeline_stage   = PgEnum("s1_intake","s2_normalize","s3_llm_extract","s4_source_match","s5_gap_detect","s6_websearch_fill","s7_staging","s8_review","s9_publish", name="pipelinestage", create_type=False)
    _intake_channel   = PgEnum("email_poll","manual","bulk_csv","dam_webhook", name="intakechannel", create_type=False)
    _stage_event_type = PgEnum("entered","completed","skipped","failed","retried","gate_opened","advanced", name="stageeventtype", create_type=False)
    _failure_code     = PgEnum("none","llm_parse_error","tmdb_quota_exceeded","kobis_timeout","websearch_no_hit","invalid_payload","system_error", name="failurecode", create_type=False)

    # ── content 컬럼 4개 ───────────────────────────────────────────────────────
    op.add_column("contents", sa.Column("intake_channel", _intake_channel,   nullable=True))
    op.add_column("contents", sa.Column("current_stage",  _pipeline_stage,   nullable=True))
    op.add_column("contents", sa.Column("failure_code",   _failure_code,     nullable=False, server_default="none"))
    op.add_column("contents", sa.Column("gate_overrides", sa.JSON,           nullable=True))

    # ── stage_event 테이블 ────────────────────────────────────────────────────
    op.create_table(
        "stage_event",
        sa.Column("id",           sa.Integer,  primary_key=True),
        sa.Column("content_id",   sa.Integer,  sa.ForeignKey("contents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage",        _pipeline_stage,   nullable=False),
        sa.Column("event_type",   _stage_event_type, nullable=False),
        sa.Column("source",       sa.String(100), nullable=True),
        sa.Column("started_at",   sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("ended_at",     sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms",   sa.Integer, nullable=True),
        sa.Column("payload_json", sa.JSON,    nullable=True),
        sa.Column("error_text",   sa.Text,    nullable=True),
        sa.Column("actor",        sa.String(100), nullable=False, server_default="system"),
    )
    op.create_index("ix_stage_event_content_id",      "stage_event", ["content_id"])
    op.create_index("ix_stage_event_stage",            "stage_event", ["stage"])
    op.create_index("ix_stage_event_event_type",       "stage_event", ["event_type"])
    op.create_index("ix_stage_event_started_at",       "stage_event", ["started_at"])
    op.create_index("ix_stage_event_content_stage",    "stage_event", ["content_id", "stage"])
    op.create_index("ix_stage_event_event_started",    "stage_event", ["event_type", "started_at"])

    # ── backfill: 기존 content.status → current_stage 역매핑 ─────────────────
    op.execute("""
        UPDATE contents SET current_stage = CASE status
            WHEN 'waiting'    THEN 's1_intake'::pipelinestage
            WHEN 'processing' THEN 's3_llm_extract'::pipelinestage
            WHEN 'staging'    THEN 's7_staging'::pipelinestage
            WHEN 'review'     THEN 's8_review'::pipelinestage
            WHEN 'approved'   THEN 's8_review'::pipelinestage
            WHEN 'rejected'   THEN 's8_review'::pipelinestage
            ELSE NULL
        END
        WHERE current_stage IS NULL
    """)


def downgrade():
    op.drop_index("ix_stage_event_event_started",  table_name="stage_event")
    op.drop_index("ix_stage_event_content_stage",  table_name="stage_event")
    op.drop_index("ix_stage_event_started_at",     table_name="stage_event")
    op.drop_index("ix_stage_event_event_type",     table_name="stage_event")
    op.drop_index("ix_stage_event_stage",          table_name="stage_event")
    op.drop_index("ix_stage_event_content_id",     table_name="stage_event")
    op.drop_table("stage_event")
    op.drop_column("contents", "gate_overrides")
    op.drop_column("contents", "failure_code")
    op.drop_column("contents", "current_stage")
    op.drop_column("contents", "intake_channel")
    op.execute("DROP TYPE IF EXISTS failurecode")
    op.execute("DROP TYPE IF EXISTS stageeventtype")
    op.execute("DROP TYPE IF EXISTS intakechannel")
    op.execute("DROP TYPE IF EXISTS pipelinestage")
