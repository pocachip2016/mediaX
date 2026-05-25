# Step 2: dpf-service (Phase B)

> Milestone: dev-pipeline-detailed-flow

## 작업
`record_stage_event()` 헬퍼 + 진입점 5곳에 훅 삽입. status ↔ current_stage 매핑 helper.

산출:
- `backend/api/programming/metadata/service/stage_events.py` (신규)
  - `record_stage_event(db, content_id, stage, event_type, *, source, payload, error, actor, latency_ms)`
  - `derive_status_from_stage(stage) -> ContentStatus` (D3 매핑)
  - `advance_gate(db, gate_id, content_ids, *, simulate, actor)` (idempotent)
  - `get_gate_pending(db, gate_id) -> list[Content]`
- 진입점 5곳 훅 삽입:
  1. `workers/email_poll_task.py` — S1 entered (intake_channel=email_poll)
  2. `api/programming/metadata/router.py::create_content` — S1 entered (manual / bulk_csv via header)
  3. `workers/enrich_metadata_task.py` — S3 entered/completed/failed (source=ollama)
  4. `services/external_match.py::_match_external_sources` — S4 per-source row
  5. `workers/websearch_fill_task.py` — S6 per-provider row + S5 gap detect 결과
- `backend/tests/test_stage_event_service.py` — 4 pytest
  - record_stage_event payload 4KB 캡
  - advance_gate idempotency (If-Match)
  - 5 진입점 훅 발화 검증 (mock provider)
  - derive_status_from_stage 9 stage 매핑

## 제약
- 기존 `Content.status` 갱신 로직 유지. `current_stage` 변경 시 `status` 동기 갱신은 `derive_status_from_stage` 1곳에서만.
- payload_json 4KB 초과 → 핵심 키만 보존 + `_truncated: true`.

## Acceptance Criteria
```bash
/verify dpf-service
```
