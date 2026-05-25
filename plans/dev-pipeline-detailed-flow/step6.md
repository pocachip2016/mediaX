# Step 6: dpf-gate-panel (Phase C)

> Milestone: dev-pipeline-detailed-flow

## FE 설계 워크플로우
wireframes.md "GatePanel (Drawer)" 참조.

- 6 게이트 공통 슬롯 5: 헤더 / 대상 리스트 / Context 패널 / 모드 토글 / 액션
- Context 패널만 게이트별 swap:
  - GATE-1: trusted_cp 화이트리스트 (없으면 일반)
  - GATE-3: provider 우선순위 + quota
  - GATE-5: 검수자 + quality 게이지 + 반려/실패 분기
  - GATE-6: quality≥90 자동 게시 옵션
- 기존 흡수 대상 (TEST_PIPELINE 콘솔의 모듈):
  - `BatchAiTrigger` → GATE-1 Context (참고만, 본체는 신규 GatePanel)
  - `BatchEnrichTrigger` → GATE-3 Context
  - `TestReviewPanel` → GATE-5 Context

## 작업
- `components/contents/pipeline/GatePanel.tsx` (신규, Drawer)
  - props: `{ gateId, mode, onClose, onAdvanced }`
  - 5 슬롯 컴포지션
  - simulate / 선택 진행 / 전체 진행 3 액션
- `components/contents/pipeline/gate-contexts/` (신규)
  - `Gate1Context.tsx`, `Gate3Context.tsx`, `Gate5Context.tsx`, `Gate6Context.tsx`
  - Gate2/Gate4 = auto-only context (간단 안내)
- `lib/api.ts` — `pipelineApi.advanceGate(gateId, { content_ids, simulate, if_match })`
- PipelineBoard `GateButton` → click → `GatePanel` open
- tsc clean

## 제약
- TEST_PIPELINE 콘솔(ADR-002)의 `BatchAiTrigger/BatchEnrichTrigger/TestReviewPanel` 은 **삭제하지 않음** — 검증용으로 보존
- Drawer 는 `@workspace/ui` Sheet 또는 기존 Drawer 컴포넌트 재사용
- 게이트 idempotency: 응답의 `last_stage_event_id` 를 다음 advance 의 If-Match 로 사용

## Acceptance Criteria
```bash
/verify dpf-gate-panel
```
