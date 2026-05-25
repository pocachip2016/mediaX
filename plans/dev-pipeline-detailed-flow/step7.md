# Step 7: dpf-timeline-fe (Phase D)

> Milestone: dev-pipeline-detailed-flow

## FE 설계 워크플로우
wireframes.md "View 2 — Content Timeline V2" 참조.

- 위치: unified shell(`/contents/[id]?mode=view`) 좌측 컬럼 하단 (Accordion 1개 추가)
- 9 stage dot + sub-source 트리 (`┬├└`)
- 상태 아이콘: `● ◐ ○ ⚠ ⛔ ⏭ ↻`
- 행 클릭 → 하단 Accordion 에 raw payload(JSON), provider 응답, error trace

## 작업
- `components/contents/shell/ContentTimelineV2.tsx` (신규)
  - props: `{ contentId }`, fetch `/api/contents/{id}/timeline` v2
  - 9 stage 세로 리스트 + sub-source 트리
  - 클릭 시 Accordion expand (raw JSON, error)
  - footer: `[▶ S{n}→S{n+1} 진행]` `[⏪ 재실행]` `[⛔ 반려]` `[⚠ 실패]`
- `components/contents/shell/ContentShell.tsx` — 좌측 컬럼 7요소 + V2 timeline 추가 (8요소)
- `lib/api.ts` — `metadataApi.getTimelineV2(id)` (v1 와 별도 메서드, 점진 cutover)
- 기존 `ContentPipelineTimeline` (TEST_PIPELINE 콘솔용)은 보존 — 6 stage 검증용
- tsc clean

## 제약
- 좌측 컬럼이 길어지면 collapsed 기본값 + 운영자 선호 저장(localStorage)
- timeline v1 호출 사이트는 그대로 두고, view 모드에서만 V2 사용
- Acceptance: 시드 1건의 S1~S7 진행이 정확히 표시되는지 manual QA

## Acceptance Criteria
```bash
/verify dpf-timeline-fe
```
