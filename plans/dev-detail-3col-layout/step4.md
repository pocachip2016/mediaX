# Step 4 — inline-edit

## 목표
edit 모드 중앙 컬럼에 인라인 편집 적용 — `InlineField` + `CurrentStateColumn` 신규, `EditPane` 삭제.

## 변경 파일
- `components/contents/shell/InlineField.tsx` — 신규 (click→input, Enter 저장, Esc 취소)
- `components/contents/shell/CurrentStateColumn.tsx` — 신규 (edit 모드 중앙 컬럼, 필드별 PUT patch)
- `app/(main)/programming/contents/[id]/page.tsx` — edit 모드 current 슬롯 → CurrentStateColumn
- `components/contents/shell/EditPane.tsx` — 삭제

## Acceptance
- edit URL에서 중앙 컬럼 필드 클릭 시 input 전환, Enter/저장 버튼으로 PUT 저장
- review URL에서 중앙 컬럼은 기존 ContentShell 유지 (read-only)
- `npm run typecheck` pass

## 완료
typecheck pass (2026-05-20)
