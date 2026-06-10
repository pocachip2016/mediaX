"""큐레이션 모듈 — home_slots + curation_banner_plans (ADR-013)

Revision ID: 0048
Revises: 0047
Create Date: 2026-06-09
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. ENUM 타입 생성 ──────────────────────────────────────────────────────
    # create_type=False 객체를 한 번 정의해 명시적 create 후 create_table에서 재사용한다.
    # (sa.Enum(create_type=False)를 create_table에 새로 넘기면 CREATE TYPE이 중복 emit되어
    #  "type already exists"로 실패한다.)
    slot_code_enum = postgresql.ENUM("A", "B", "C", "D", "E", "F", name="slot_code", create_type=False)
    slot_code_enum.create(op.get_bind(), checkfirst=True)

    slot_type_enum = postgresql.ENUM("banner", "theme", "personal", "genre", "ranking", "promo", name="slot_type", create_type=False)
    slot_type_enum.create(op.get_bind(), checkfirst=True)

    curation_device_enum = postgresql.ENUM("all", "tv", "mobile", "web", name="curation_device", create_type=False)
    curation_device_enum.create(op.get_bind(), checkfirst=True)

    time_band_enum = postgresql.ENUM("all", "morning", "afternoon", "evening", "night", name="time_band", create_type=False)
    time_band_enum.create(op.get_bind(), checkfirst=True)

    banner_plan_status_enum = postgresql.ENUM("draft", "review", "approved", "published", name="banner_plan_status", create_type=False)
    banner_plan_status_enum.create(op.get_bind(), checkfirst=True)

    # ── 2. home_slots 테이블 ───────────────────────────────────────────────────
    op.create_table(
        "home_slots",
        sa.Column("id",          sa.Integer(), primary_key=True),
        sa.Column("slot_code",   slot_code_enum, nullable=False),
        sa.Column("slot_type",   slot_type_enum, nullable=False),
        sa.Column("device",      curation_device_enum, nullable=False, server_default="all"),
        sa.Column("time_band",   time_band_enum, nullable=False, server_default="all"),
        sa.Column("position",    sa.Integer(), nullable=False, server_default="0"),
        sa.Column("node_set_id", sa.Integer(), sa.ForeignKey("programming_node_sets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active",   sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at",  sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",  sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_home_slots_slot_code_device_time_band", "home_slots", ["slot_code", "device", "time_band"])

    # ── 3. curation_banner_plans 테이블 ───────────────────────────────────────
    op.create_table(
        "curation_banner_plans",
        sa.Column("id",             sa.Integer(), primary_key=True),
        sa.Column("week_start",     sa.Date(), nullable=False),
        sa.Column("status",         banner_plan_status_enum, nullable=False, server_default="draft"),
        sa.Column("node_set_id",    sa.Integer(), sa.ForeignKey("programming_node_sets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ctr_prediction", sa.Float(), nullable=True),
        sa.Column("reviewer",       sa.String(100), nullable=True),
        sa.Column("reviewed_at",    sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at",   sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at",     sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",     sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("week_start", name="uq_curation_banner_plans_week_start"),
    )


def downgrade() -> None:
    op.drop_table("curation_banner_plans")
    op.drop_index("ix_home_slots_slot_code_device_time_band", table_name="home_slots")
    op.drop_table("home_slots")

    op.execute("DROP TYPE IF EXISTS banner_plan_status")
    op.execute("DROP TYPE IF EXISTS time_band")
    op.execute("DROP TYPE IF EXISTS curation_device")
    op.execute("DROP TYPE IF EXISTS slot_type")
    op.execute("DROP TYPE IF EXISTS slot_code")
