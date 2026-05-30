"""contentstatus + pipelinestage enum rename — ADR-007 단계 재정의

Revision ID: 0027
Revises: 0026
Create Date: 2026-05-29

contentstatus 변경:
  waiting    → raw       (CP 수신 초기)
  processing → enriched  (외부 회수 완료)
  staging    → ai        (AI 처리 완료)
  review / approved / rejected 유지

pipelinestage 변경 (실행 순서 반영):
  s3_llm_extract    → s6_llm_extract    (WebSearch 이후 실행)
  s4_source_match   → s3_source_match
  s5_gap_detect     → s4_gap_detect
  s6_websearch_fill → s5_websearch_fill
"""
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # contentstatus
    op.execute("ALTER TYPE contentstatus RENAME VALUE 'waiting'    TO 'raw'")
    op.execute("ALTER TYPE contentstatus RENAME VALUE 'processing' TO 'enriched'")
    op.execute("ALTER TYPE contentstatus RENAME VALUE 'staging'    TO 'ai'")

    # pipelinestage — s3→s6 먼저 (s6 자리가 비어야 s6_websearch→s5 로 이동 가능)
    op.execute("ALTER TYPE pipelinestage RENAME VALUE 's3_llm_extract'    TO 's6_llm_extract'")
    op.execute("ALTER TYPE pipelinestage RENAME VALUE 's4_source_match'   TO 's3_source_match'")
    op.execute("ALTER TYPE pipelinestage RENAME VALUE 's5_gap_detect'     TO 's4_gap_detect'")
    op.execute("ALTER TYPE pipelinestage RENAME VALUE 's6_websearch_fill' TO 's5_websearch_fill'")


def downgrade() -> None:
    # pipelinestage 역순
    op.execute("ALTER TYPE pipelinestage RENAME VALUE 's5_websearch_fill' TO 's6_websearch_fill'")
    op.execute("ALTER TYPE pipelinestage RENAME VALUE 's4_gap_detect'     TO 's5_gap_detect'")
    op.execute("ALTER TYPE pipelinestage RENAME VALUE 's3_source_match'   TO 's4_source_match'")
    op.execute("ALTER TYPE pipelinestage RENAME VALUE 's6_llm_extract'    TO 's3_llm_extract'")

    # contentstatus
    op.execute("ALTER TYPE contentstatus RENAME VALUE 'raw'      TO 'waiting'")
    op.execute("ALTER TYPE contentstatus RENAME VALUE 'enriched' TO 'processing'")
    op.execute("ALTER TYPE contentstatus RENAME VALUE 'ai'       TO 'staging'")
