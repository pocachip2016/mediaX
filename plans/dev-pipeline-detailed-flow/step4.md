# Step 4: dpf-board-api (Phase B)

> Milestone: dev-pipeline-detailed-flow

## 작업
파이프라인 보드 API + 게이트 advance + 이벤트 스트림 API.

산출:
- `backend/api/programming/metadata/router_pipeline.py` (신규 또는 확장)
  - `GET /api/pipeline/board` — channels_24h + stages count + gates mode/pending + alerts
  - `POST /api/pipeline/gate/{gate_id}/advance` — idempotent advance (If-Match)
  - `GET /api/pipeline/events` — paging (since=event_id&limit=200&filter=...)
  - `POST /api/pipeline/gate/{gate_id}/mode` — 수동/자동 토글
- `backend/api/programming/metadata/schemas_pipeline.py`
  - `BoardResponse`, `GateAdvanceRequest/Response`, `StageEventOut`, `GateModeRequest`
- `backend/tests/test_pipeline_board_api.py` — 5 pytest
  - board 응답 9 stage + 4 channel
  - gate advance 정상 케이스
  - gate advance If-Match 충돌 시 409
  - gate mode 토글 + gate_overrides 저장
  - events paging since/limit/filter

## SSE 옵션
events 는 1차 paging 으로. WebSocket/SSE 는 Step 8 FE 와 함께 결정 (필요 시 별도 endpoint `/ws/pipeline-events`).

## Acceptance Criteria
```bash
/verify dpf-board-api
```
