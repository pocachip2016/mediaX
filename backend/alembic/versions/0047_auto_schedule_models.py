"""자동편성 파이프라인 — AutoStage enum + ProgrammingNode AUTO 필드 + SchedulingStageEvent + ScheduleAutoPolicy (ADR-012)

Revision ID: 0047
Revises: 0046
Create Date: 2026-06-09
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. ENUM 타입 생성 ──────────────────────────────────────────────────────
    # create_type=False 객체를 한 번 정의해 명시적 create 후 모든 컬럼에서 재사용한다.
    # (sa.Enum(create_type=False)를 create_table에 새로 넘기면 CREATE TYPE이 중복 emit되어
    #  "type already exists"로 실패하므로, 동일 인스턴스를 공유해 암묵적 생성을 막는다.)
    # auto_stage: ProgrammingNode.auto_stage + SchedulingStageEvent.stage 공용
    auto_stage_enum = postgresql.ENUM(
        "p1_define", "p2_candidate", "p3_match", "p4_autoconfirm", "p5_conflict", "p6_publish",
        name="auto_stage", create_type=False,
    )
    auto_stage_enum.create(op.get_bind(), checkfirst=True)

    # auto_event_type: SchedulingStageEvent.event_type 전용
    auto_event_type_enum = postgresql.ENUM(
        "entered", "completed", "skipped", "failed", "advanced", "rejected",
        name="auto_event_type", create_type=False,
    )
    auto_event_type_enum.create(op.get_bind(), checkfirst=True)

    # ── 2. ProgrammingNode AUTO 추적 필드 ──────────────────────────────────────
    op.add_column("programming_nodes", sa.Column("auto_enabled",    sa.Boolean(),  nullable=False, server_default="false"))
    op.add_column("programming_nodes", sa.Column("auto_stage",      auto_stage_enum, nullable=True))
    op.add_column("programming_nodes", sa.Column("auto_hold",       sa.Boolean(),  nullable=False, server_default="false"))
    op.add_column("programming_nodes", sa.Column("auto_claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("programming_nodes", sa.Column("auto_skipped_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("programming_nodes", sa.Column("schedule_score",  sa.Float(),    nullable=True))

    op.create_index("ix_programming_nodes_auto_enabled", "programming_nodes", ["auto_enabled"])
    op.create_index("ix_programming_nodes_auto_stage",   "programming_nodes", ["auto_stage"])

    # ── 3. SchedulingStageEvent 테이블 ─────────────────────────────────────────
    op.create_table(
        "scheduling_stage_events",
        sa.Column("id",           sa.Integer(), primary_key=True),
        sa.Column("node_id",      sa.Integer(), sa.ForeignKey("programming_nodes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("stage",        auto_stage_enum, nullable=False, index=True),
        sa.Column("event_type",   auto_event_type_enum, nullable=False, index=True),
        sa.Column("source",       sa.String(100), nullable=True),
        sa.Column("started_at",   sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("ended_at",     sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms",   sa.Integer(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("error_text",   sa.Text(), nullable=True),
        sa.Column("actor",        sa.String(100), nullable=False, server_default="system"),
    )
    op.create_index("ix_scheduling_stage_event_node_stage",   "scheduling_stage_events", ["node_id", "stage"])
    op.create_index("ix_scheduling_stage_event_type_started", "scheduling_stage_events", ["event_type", "started_at"])

    # ── 4. ScheduleAutoPolicy 테이블 ──────────────────────────────────────────
    op.create_table(
        "schedule_auto_policy",
        sa.Column("id",                   sa.Integer(), primary_key=True),
        sa.Column("p2_auto",              sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("p3_auto",              sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("p4_auto",              sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("p5_auto",              sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("p6_auto",              sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("confidence_threshold", sa.Float(),   nullable=False, server_default="0.5"),
        sa.Column("auto_tick_enabled",    sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("batch_size",           sa.Integer(), nullable=False, server_default="20"),
        sa.Column("visibility_timeout",   sa.Integer(), nullable=False, server_default="300"),
        sa.Column("updated_at",           sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 싱글톤 초기 행 삽입 (id=1)
    op.execute(
        "INSERT INTO schedule_auto_policy (id) VALUES (1) ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("schedule_auto_policy")
    op.drop_table("scheduling_stage_events")

    op.drop_index("ix_programming_nodes_auto_stage",   table_name="programming_nodes")
    op.drop_index("ix_programming_nodes_auto_enabled", table_name="programming_nodes")
    op.drop_column("programming_nodes", "schedule_score")
    op.drop_column("programming_nodes", "auto_skipped_at")
    op.drop_column("programming_nodes", "auto_claimed_at")
    op.drop_column("programming_nodes", "auto_hold")
    op.drop_column("programming_nodes", "auto_stage")
    op.drop_column("programming_nodes", "auto_enabled")

    op.execute("DROP TYPE IF EXISTS auto_event_type")
    op.execute("DROP TYPE IF EXISTS auto_stage")
