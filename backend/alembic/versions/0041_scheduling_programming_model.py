"""scheduling programming model — programming_node_sets / programming_nodes / programming_links + 4 ENUM

Revision ID: 0041
Revises: 0040
Create Date: 2026-06-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 4 ENUM 타입 생성 ──────────────────────────────────────────────
    op.execute(sa.text(
        "CREATE TYPE node_kind AS ENUM ('container', 'rule', 'rank', 'manual')"
    ))
    op.execute(sa.text(
        "CREATE TYPE child_type AS ENUM ('node', 'content')"
    ))
    op.execute(sa.text(
        "CREATE TYPE link_source AS ENUM ('manual', 'ai', 'rule')"
    ))
    op.execute(sa.text(
        "CREATE TYPE link_status AS ENUM ('active', 'suggested', 'rejected')"
    ))

    # ── programming_node_sets ─────────────────────────────────────────
    op.execute(sa.text("""
        CREATE TABLE programming_node_sets (
            id              SERIAL PRIMARY KEY,
            name            VARCHAR(200) NOT NULL,
            description     VARCHAR(1000),
            status          VARCHAR(20)  NOT NULL DEFAULT 'draft',
            published_at    TIMESTAMPTZ,
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """))

    # ── programming_nodes ────────────────────────────────────────────
    op.execute(sa.text("""
        CREATE TABLE programming_nodes (
            id              SERIAL PRIMARY KEY,
            set_id          INTEGER REFERENCES programming_node_sets(id) ON DELETE SET NULL,
            kind            node_kind NOT NULL,
            name            VARCHAR(200) NOT NULL,
            slug            VARCHAR(220),
            headline_copy   VARCHAR(200),
            sub_copy        VARCHAR(300),
            theme_features  JSONB,
            rule_query      JSONB,
            rank_source     VARCHAR(50),
            rank_limit      INTEGER,
            window_start    DATE,
            window_end      DATE,
            is_active       BOOLEAN NOT NULL DEFAULT true,
            is_draft        BOOLEAN NOT NULL DEFAULT false,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    op.create_index("ix_programming_nodes_set_id", "programming_nodes", ["set_id"])
    op.create_index("ix_programming_nodes_kind", "programming_nodes", ["kind"])

    # ── programming_links ────────────────────────────────────────────
    op.execute(sa.text("""
        CREATE TABLE programming_links (
            id                  SERIAL PRIMARY KEY,
            parent_node_id      INTEGER NOT NULL REFERENCES programming_nodes(id) ON DELETE CASCADE,
            child_type          child_type NOT NULL,
            child_node_id       INTEGER REFERENCES programming_nodes(id) ON DELETE CASCADE,
            child_content_id    INTEGER REFERENCES contents(id) ON DELETE CASCADE,
            sort_order          INTEGER NOT NULL DEFAULT 0,
            is_pinned           BOOLEAN NOT NULL DEFAULT false,
            window_start        DATE,
            window_end          DATE,
            copy_override       JSONB,
            source              link_source NOT NULL DEFAULT 'manual',
            confidence          FLOAT,
            status              link_status NOT NULL DEFAULT 'active',
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_programming_links_child_xor
                CHECK ((child_node_id IS NULL) != (child_content_id IS NULL)),
            CONSTRAINT uq_link_parent_child_node
                UNIQUE (parent_node_id, child_node_id),
            CONSTRAINT uq_link_parent_child_content
                UNIQUE (parent_node_id, child_content_id)
        )
    """))
    op.create_index("ix_programming_links_parent_node_id", "programming_links", ["parent_node_id"])
    op.create_index("ix_programming_links_child_content_id", "programming_links", ["child_content_id"])
    op.create_index("ix_programming_links_parent_sort", "programming_links", ["parent_node_id", "sort_order"])


def downgrade() -> None:
    op.drop_index("ix_programming_links_parent_sort", table_name="programming_links")
    op.drop_index("ix_programming_links_child_content_id", table_name="programming_links")
    op.drop_index("ix_programming_links_parent_node_id", table_name="programming_links")
    op.drop_table("programming_links")

    op.drop_index("ix_programming_nodes_kind", table_name="programming_nodes")
    op.drop_index("ix_programming_nodes_set_id", table_name="programming_nodes")
    op.drop_table("programming_nodes")

    op.drop_table("programming_node_sets")

    op.execute(sa.text("DROP TYPE link_status"))
    op.execute(sa.text("DROP TYPE link_source"))
    op.execute(sa.text("DROP TYPE child_type"))
    op.execute(sa.text("DROP TYPE node_kind"))
