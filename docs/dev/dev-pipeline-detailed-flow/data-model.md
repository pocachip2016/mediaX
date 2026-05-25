# ADR-006 · Data Model

> Companion to [adr-006-pipeline-stage-model.md]. 스키마 / migration / API.

## Enums

```python
# api/programming/metadata/models.py 추가

class PipelineStage(str, Enum):
    S1_INTAKE          = "s1_intake"
    S2_NORMALIZE       = "s2_normalize"
    S3_LLM_EXTRACT     = "s3_llm_extract"
    S4_SOURCE_MATCH    = "s4_source_match"
    S5_GAP_DETECT      = "s5_gap_detect"
    S6_WEBSEARCH_FILL  = "s6_websearch_fill"
    S7_STAGING         = "s7_staging"
    S8_REVIEW          = "s8_review"
    S9_PUBLISH         = "s9_publish"

class IntakeChannel(str, Enum):
    EMAIL_POLL   = "email_poll"
    MANUAL       = "manual"
    BULK_CSV     = "bulk_csv"
    DAM_WEBHOOK  = "dam_webhook"

class StageEventType(str, Enum):
    ENTERED      = "entered"        # stage 진입
    COMPLETED    = "completed"      # stage 정상 완료
    SKIPPED      = "skipped"        # gap 충분 → S6 스킵 등
    FAILED       = "failed"         # provider error / timeout
    RETRIED      = "retried"        # 재시도 호출
    GATE_OPENED  = "gate_opened"    # 운영자가 다음 stage 로 진행
    ADVANCED     = "advanced"       # gate 통과 후 다음 stage 진입 (system)

class FailureCode(str, Enum):
    NONE                = "none"
    LLM_PARSE_ERROR     = "llm_parse_error"
    TMDB_QUOTA_EXCEEDED = "tmdb_quota_exceeded"
    KOBIS_TIMEOUT       = "kobis_timeout"
    WEBSEARCH_NO_HIT    = "websearch_no_hit"
    INVALID_PAYLOAD     = "invalid_payload"
    SYSTEM_ERROR        = "system_error"
```

## Content 컬럼 추가

```python
class Content:
    # ... 기존 컬럼 ...
    intake_channel: Mapped[IntakeChannel | None]     # nullable — 기존 row 대비
    current_stage:  Mapped[PipelineStage | None]
    failure_code:   Mapped[FailureCode] = mapped_column(default=FailureCode.NONE)
    gate_overrides: Mapped[dict | None] = mapped_column(JSON)
    # gate_overrides 예: {"GATE_1": "auto", "GATE_3": "manual"}
```

`status` 컬럼은 **그대로 유지**. `current_stage → status` 매핑은 service 레이어의 helper 로 처리 (D3 참조).

## StageEvent 테이블 (신규)

```python
class StageEvent(Base):
    __tablename__ = "stage_event"

    id:            Mapped[int]           = mapped_column(primary_key=True)
    content_id:    Mapped[int]           = mapped_column(ForeignKey("content.id", ondelete="CASCADE"), index=True)
    stage:         Mapped[PipelineStage] = mapped_column(index=True)
    source:        Mapped[str | None]    # tmdb/kobis/dam/brave/serpapi/gemini/ollama/user/system
    event_type:    Mapped[StageEventType] = mapped_column(index=True)
    started_at:    Mapped[datetime]      = mapped_column(default=utcnow, index=True)
    ended_at:      Mapped[datetime | None]
    latency_ms:    Mapped[int | None]
    payload_json:  Mapped[dict | None]   = mapped_column(JSON)   # ≤ 4KB enforced
    error_text:    Mapped[str | None]    = mapped_column(Text)
    actor:         Mapped[str]           = mapped_column(default="system")

    # 인덱스
    __table_args__ = (
        Index("ix_stage_event_content_stage", "content_id", "stage"),
        Index("ix_stage_event_event_started", "event_type", "started_at"),
    )
```

**제약**
- `payload_json` 직렬화 후 4KB 초과 시 `_truncated: true` flag + 핵심만 보존
- 30일 후 `event_type IN (entered, completed)` 만 남기고 나머지 압축(별도 archive job, 본 ADR scope 외)

## Alembic Migration 스켈레톤

```python
# alembic/versions/0018_pipeline_stage_model.py
def upgrade():
    # enums
    op.execute("CREATE TYPE pipeline_stage AS ENUM (...)")
    op.execute("CREATE TYPE intake_channel AS ENUM (...)")
    op.execute("CREATE TYPE stage_event_type AS ENUM (...)")
    op.execute("CREATE TYPE failure_code AS ENUM (...)")

    # content 컬럼
    op.add_column("content", sa.Column("intake_channel", ...))
    op.add_column("content", sa.Column("current_stage",  ...))
    op.add_column("content", sa.Column("failure_code",   ..., server_default="none"))
    op.add_column("content", sa.Column("gate_overrides", sa.JSON, nullable=True))

    # stage_event
    op.create_table("stage_event", ...)

    # backfill: 기존 콘텐츠의 current_stage 를 status → stage 역매핑으로 채움
    op.execute("""
      UPDATE content SET current_stage = CASE status
        WHEN 'waiting'    THEN 's1_intake'
        WHEN 'processing' THEN 's3_llm_extract'
        WHEN 'staging'    THEN 's7_staging'
        WHEN 'review'     THEN 's8_review'
        WHEN 'approved'   THEN 's8_review'
        WHEN 'published'  THEN 's9_publish'
        WHEN 'rejected'   THEN 's8_review'
      END
    """)
```

## record_stage_event() 헬퍼

```python
# api/programming/metadata/service/stage_events.py (신규)

def record_stage_event(
    db: Session,
    content_id: int,
    stage: PipelineStage,
    event_type: StageEventType,
    *,
    source: str | None = None,
    payload: dict | None = None,
    error: str | None = None,
    actor: str = "system",
    latency_ms: int | None = None,
) -> StageEvent:
    ...
```

**진입점 5곳에 훅 삽입** (Step 2):
1. `cp_email_poll_task` — S1 entered (intake_channel=email_poll)
2. `create_content()` 라우터 — S1 entered (manual / bulk_csv)
3. `enrich_content_metadata` Celery task — S3 entered/completed/failed
4. `_match_external_sources()` — S4 per-source (tmdb/kobis/dam)
5. `websearch_fill_task` — S6 per-provider (brave/serpapi/gemini/ollama)

## API 신규/확장

### `GET /api/contents/{id}/timeline` (v2)

```json
{
  "content_id": 1234,
  "title": "외계+인 2부",
  "current_stage": "s7_staging",
  "intake_channel": "email_poll",
  "stages": [
    {
      "stage": "s1_intake",
      "status": "done",
      "at": "2026-05-21T14:02:11+09:00",
      "duration_ms": 3200,
      "sources": [{"source": "email_poll", "result": "ok", "detail": {"from": "CGV"}}]
    },
    {
      "stage": "s4_source_match",
      "status": "done",
      "at": "2026-05-21T14:02:20+09:00",
      "sources": [
        {"source": "tmdb",  "result": "hit",  "latency_ms": 412, "detail": {"tmdb_id": 1185528}},
        {"source": "kobis", "result": "miss", "latency_ms": 201},
        {"source": "dam",   "result": "hit",  "latency_ms": 88,  "detail": {"asset_id": 7712}}
      ]
    },
    ...
  ]
}
```

### `GET /api/pipeline/board`

```json
{
  "channels_24h": {
    "email_poll": {"count": 124, "last_at": "...", "status": "ok"},
    "manual":     {"count": 18,  "last_at": "...", "status": "ok"},
    "bulk_csv":   {"count": 237, "last_at": "...", "status": "ok"},
    "dam_webhook":{"count": 33,  "last_at": "...", "status": "ok"}
  },
  "stages": {
    "s1_intake":      {"count": 132},
    "s2_normalize":   {"count": 132},
    "s3_llm_extract": {"count": 12},
    "s4_source_match":{"count": 8},
    "s5_gap_detect":  {"count": 5},
    "s6_websearch_fill":{"count": 21},
    "s7_staging":     {"count": 41},
    "s8_review":      {"count": 23},
    "s9_publish":     {"count": 6,  "total_published": 189}
  },
  "gates": {
    "GATE_1": {"mode": "manual", "pending": 132},
    "GATE_2": {"mode": "auto",   "pending": 8},
    "GATE_3": {"mode": "manual", "pending": 5},
    "GATE_4": {"mode": "auto",   "pending": 21},
    "GATE_5": {"mode": "manual", "pending": 41},
    "GATE_6": {"mode": "manual", "pending": 6}
  },
  "alerts": {
    "failed_queue": 2,
    "rejected_archive": 17,
    "enrichment_blocked": 5
  }
}
```

### `POST /api/pipeline/gate/{gate_id}/advance`

```json
// request
{
  "content_ids": [1234, 1235],   // 비우면 gate 의 모든 대기 콘텐츠
  "simulate": false,
  "actor_token": "..."
}

// response
{
  "advanced": 2,
  "skipped":  0,
  "failed":   0,
  "next_stage": "s6_websearch_fill",
  "events": [{"stage_event_id": 8821}, ...]
}
```

**Idempotency**: `If-Match: <last_stage_event_id>` 헤더로 동시 진행 충돌 차단.

### `GET /api/pipeline/events` (SSE 또는 paging)

가상 스크롤 Live Log 용. `?since=<event_id>&limit=200&stage=&source=&event_type=` 파라미터.

## 백워드 호환

| 기존 코드 | 영향 | 대응 |
|---|---|---|
| `Content.status` 필터 | 무영향 | derived view 로 보존 |
| 검수 큐 `status=staging` | 무영향 | stage=s7_staging 진입 시 status 동시 갱신 |
| ADR-002 의 6-stage 콘솔 | 무영향 | TEST_PIPELINE 격리 데이터만 사용 |
| `/contents/{id}/timeline` v1 호출자 | 응답 확장 (필드 추가만) | 기존 필드 보존, sources 배열 추가 |
