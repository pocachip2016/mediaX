"""Phase D WebSearch — quota log + composite unique + ENUM 확장

테이블:
  - web_search_quota_log : provider별 일별 호출 카운터 + 강제 소진 시점 (Redis → DB 스냅샷)

기존 테이블 변경:
  - web_search_cache.query_hash unique → (query_hash, source) composite unique
    (provider별 동일 쿼리 결과를 분리 캐시하기 위함)

ENUM 확장:
  - externalsourcetype += 'websearch'  (Phase D WebSearch 발굴/보강 결과)

참조: docs/dev/phase-d/_index.md, docs/dev/phase-d/quota-policy.md, docs/dev/phase-d/cache-policy.md

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-16
"""
import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # 1. ExternalSourceType ENUM 에 websearch 추가 (PostgreSQL 전용)
    if is_pg:
        op.execute("ALTER TYPE externalsourcetype ADD VALUE IF NOT EXISTS 'websearch'")

    # 2. web_search_cache — query_hash unique → (query_hash, source) composite unique
    #    provider별 동일 쿼리 결과를 분리 캐시 (Brave 결과 ≠ SerpAPI 결과)
    op.drop_index("ix_web_search_cache_query_hash", table_name="web_search_cache")
    op.create_index(
        "ix_web_search_cache_query_hash",
        "web_search_cache",
        ["query_hash"],
        unique=False,
    )
    op.create_index(
        "ix_web_search_cache_query_hash_source",
        "web_search_cache",
        ["query_hash", "source"],
        unique=True,
    )

    # 3. web_search_quota_log — 일 1회 04:00 KST Beat 가 Redis 카운터 → DB 스냅샷
    op.create_table(
        "web_search_quota_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(20), nullable=False),
        # provider: brave | serpapi | gemini | ollama
        sa.Column("day_kst", sa.String(8), nullable=False),
        # day_kst: YYYYMMDD KST 자정 기준
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("limit_at_time", sa.Integer(), nullable=True),
        # limit_at_time: 스냅샷 시점의 daily_limit (env 변경 추적)
        sa.Column("exhausted_at", sa.DateTime(timezone=True), nullable=True),
        # exhausted_at: 강제 소진 (429 응답 등) 시점, 정상 종료 시 NULL
        sa.Column("snapshot_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("provider", "day_kst", name="uq_web_search_quota_provider_day"),
    )
    op.create_index(
        "ix_web_search_quota_log_day_provider",
        "web_search_quota_log",
        ["day_kst", "provider"],
    )


def downgrade():
    op.drop_index("ix_web_search_quota_log_day_provider", table_name="web_search_quota_log")
    op.drop_table("web_search_quota_log")

    op.drop_index("ix_web_search_cache_query_hash_source", table_name="web_search_cache")
    op.drop_index("ix_web_search_cache_query_hash", table_name="web_search_cache")
    op.create_index(
        "ix_web_search_cache_query_hash",
        "web_search_cache",
        ["query_hash"],
        unique=True,
    )
    # NOTE: websearch ENUM 값은 PostgreSQL 에서 되돌릴 수 없음 (VALUE 제거 미지원)
