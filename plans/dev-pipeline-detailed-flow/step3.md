# Step 3: dpf-timeline-api (Phase B)

> Milestone: dev-pipeline-detailed-flow

## 작업
`GET /api/contents/{id}/timeline` v2 — 9-stage + source 분기. 기존 v1 호환 유지(필드 추가만).

산출:
- `backend/api/programming/metadata/router_timeline.py` (확장)
  - 응답 스키마: `ContentTimelineV2` (data-model.md 참조)
  - 9 stage 정규화 (없는 stage 는 status=pending)
  - sub-source 배열 (S4: tmdb/kobis/dam, S6: brave/serpapi/gemini/ollama)
  - latency_ms / error_text / payload 요약 포함
- `backend/api/programming/metadata/schemas_timeline.py` (신규)
  - `StageOut`, `StageSourceOut`, `ContentTimelineV2`
- `backend/tests/test_timeline_v2_api.py` — 6 pytest
  - 빈 콘텐츠 → 9 pending stage
  - 정상 흐름 (S1~S7) → done/active 분기
  - S4 sub-source 3행
  - S6 4-provider 폴백 응답
  - failed/rejected 표기
  - v1 호환 (기존 stages 배열 필드 보존)

## API 응답 예시
data-model.md 의 GET /api/contents/{id}/timeline 섹션 참조.

## Acceptance Criteria
```bash
/verify dpf-timeline-api
```
