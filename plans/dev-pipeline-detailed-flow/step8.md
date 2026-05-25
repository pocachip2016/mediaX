# Step 8: dpf-event-log (Phase D)

> Milestone: dev-pipeline-detailed-flow

## FE 설계 워크플로우
wireframes.md "View 3 — Live Event Log" 참조.

- 신규 페이지 `/monitoring/pipeline/log`
- 가상 스크롤 (수천 행 안정)
- 필터: stage / source / event_type 드롭다운
- 액션: 일시정지 / CSV export / stage throughput / P95 latency 미니 차트

## 작업
- `app/(main)/monitoring/pipeline/log/page.tsx` (신규)
- `components/monitoring/pipeline/StageEventStream.tsx` (신규)
  - `@tanstack/react-virtual` 가상 스크롤
  - polling 2s (또는 SSE — 백엔드 Step 4 에서 결정)
  - `since=last_event_id` 누적
- `components/monitoring/pipeline/StageEventFilters.tsx`
- `components/monitoring/pipeline/ThroughputMiniChart.tsx` — recharts 활용 (이미 사용 중)
- `config/docs.ts` — 모니터링 섹션에 메뉴 추가 ("파이프라인 로그")
- `lib/api.ts` — `pipelineApi.streamEvents({ since, limit, filter })`
- tsc clean

## 제약
- `@tanstack/react-virtual` 미설치 시 `npm i` 필요 — package.json 확인
- 일시정지 토글 시 누적 since 보존
- 1000+ 이벤트 렌더 시 60fps 유지 (manual QA)

## Acceptance Criteria
```bash
/verify dpf-event-log
```
