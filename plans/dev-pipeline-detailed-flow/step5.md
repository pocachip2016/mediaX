# Step 5: dpf-board-fe (Phase C)

> Milestone: dev-pipeline-detailed-flow

## FE 설계 워크플로우 (필수)
구현 전 ASCII wireframe 확인 — `docs/dev/dev-pipeline-detailed-flow/wireframes.md` "View 1 — Pipeline Board" 참조.

- Screen purpose: 운영자가 채널 입수 + 9-stage 진행 + 게이트 클릭 1화면에서 파악
- User flow: 상단 채널 카드 4개 → 중단 stage+gate 흐름 → 하단 alerts → 게이트 클릭 → Drawer
- 재사용 컴포넌트:
  - `PipelineStat` (변형: 채널용)
  - `PipelineStageCard` (변형: 9 stage)
  - `GatePanel` (Step 6 — 본 Step 에서는 placeholder)
- 신규 디자인 토큰: 없음 (기존 amber/violet/blue/green/red 재사용)
- 상태: loading / empty / error 3 케이스
- 반응형: 6 stage 가 wrap 되도록 mobile breakpoint 검토

## 작업
- `mediaX-CMS/apps/web/components/contents/pipeline/PipelineBoard.tsx` (신규)
  - 4 채널 카드 grid (24h count + last_at)
  - 9 stage 흐름 (PipelineStageCard 확장)
  - 6 GateButton (count + mode 토글 아이콘 🔒/🤖)
  - alerts 3 badge (failed/rejected/blocked)
- `components/contents/pipeline/ChannelCard.tsx` (신규)
- `components/contents/pipeline/GateButton.tsx` (신규)
  - `<GateButton stage="GATE-3" mode="manual" count={5} onAdvance={openPanel} onToggleMode={...} />`
- `lib/api.ts` — `pipelineApi.getBoard()`, `pipelineApi.toggleGateMode()`
- 기존 `app/(main)/programming/contents/pipeline/page.tsx` — 상단에 `<PipelineBoard />` 추가, 기존 모니터링 카드들은 보존 (Test Console 도 보존)
- tsc clean

## 제약
- ADR-002 의 6-stage 콘솔(`PipelineStageCard` + `ContentPipelineTimeline`)은 **TEST_PIPELINE 전용**으로 유지 — 본 Step 의 9-stage 와 별도 영역
- mock 폴백 포함 (백엔드 없이 UI 확인 가능)

## Acceptance Criteria
```bash
/verify dpf-board-fe
```
