"""catalog pricing + holdback — pricing / holdback_policies / holdback_schedules / price_change_log

Revision ID: 0040
Revises: 0039
Create Date: 2026-06-06
"""
import sqlalchemy as sa
from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("CREATE TYPE quality_enum AS ENUM ('SD', 'HD', 'FHD', 'UHD_4K')"))
    op.execute(sa.text(
        "CREATE TYPE purchase_type_enum AS ENUM "
        "('single', 'series_episode', 'season_package', 'est_single', 'est_season')"
    ))

    # pricing table — enum columns → raw SQL to avoid double CREATE TYPE from sa.Enum
    op.execute(sa.text("""
        CREATE TABLE pricing (
            id          SERIAL PRIMARY KEY,
            content_id  INTEGER NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
            quality     quality_enum NOT NULL,
            purchase_type purchase_type_enum NOT NULL,
            price       INTEGER NOT NULL,
            currency    VARCHAR(10) NOT NULL DEFAULT 'KRW',
            is_active   BOOLEAN NOT NULL DEFAULT true,
            created_at  TIMESTAMP NOT NULL DEFAULT now(),
            updated_at  TIMESTAMP NOT NULL DEFAULT now(),
            CONSTRAINT uq_pricing_content_quality_type
                UNIQUE (content_id, quality, purchase_type)
        )
    """))
    op.create_index("ix_pricing_content_id", "pricing", ["content_id"])

    op.create_table(
        "holdback_policies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cp_name", sa.String(200), nullable=False),
        sa.Column("window_no", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("offset_days_start", sa.Integer(), nullable=False),
        sa.Column("offset_days_end", sa.Integer(), nullable=True),
        sa.Column("price_rule", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cp_name", "window_no", name="uq_holdback_policy_cp_window"),
    )
    op.create_index("ix_holdback_policies_cp_name", "holdback_policies", ["cp_name"])

    op.create_table(
        "holdback_schedules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_id", sa.Integer(), nullable=False),
        sa.Column("window_no", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("price_id", sa.Integer(), nullable=True),
        sa.Column("source_policy_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["content_id"], ["contents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["price_id"], ["pricing.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_policy_id"], ["holdback_policies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_id", "window_no", name="uq_holdback_schedule_content_window"),
    )
    op.create_index("ix_holdback_schedules_content_id", "holdback_schedules", ["content_id"])
    op.create_index("ix_holdback_schedules_start_date", "holdback_schedules", ["start_date"])

    # price_change_log — enum columns → raw SQL
    op.execute(sa.text("""
        CREATE TABLE price_change_log (
            id            SERIAL PRIMARY KEY,
            content_id    INTEGER NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
            quality       quality_enum NOT NULL,
            purchase_type purchase_type_enum NOT NULL,
            old_price     INTEGER,
            new_price     INTEGER NOT NULL,
            changed_by    VARCHAR(200),
            reason        VARCHAR(500),
            batch_id      VARCHAR(36),
            created_at    TIMESTAMP NOT NULL DEFAULT now()
        )
    """))
    op.create_index("ix_price_change_log_content_id", "price_change_log", ["content_id"])
    op.create_index("ix_price_change_log_batch_id", "price_change_log", ["batch_id"])


def downgrade() -> None:
    op.drop_index("ix_price_change_log_batch_id", table_name="price_change_log")
    op.drop_index("ix_price_change_log_content_id", table_name="price_change_log")
    op.drop_table("price_change_log")

    op.drop_index("ix_holdback_schedules_start_date", table_name="holdback_schedules")
    op.drop_index("ix_holdback_schedules_content_id", table_name="holdback_schedules")
    op.drop_table("holdback_schedules")

    op.drop_index("ix_holdback_policies_cp_name", table_name="holdback_policies")
    op.drop_table("holdback_policies")

    op.drop_index("ix_pricing_content_id", table_name="pricing")
    op.drop_table("pricing")

    op.execute(sa.text("DROP TYPE IF EXISTS purchase_type_enum"))
    op.execute(sa.text("DROP TYPE IF EXISTS quality_enum"))
