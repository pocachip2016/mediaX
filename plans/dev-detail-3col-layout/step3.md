# Step 3 — ai-rec-column

> GitHub: —

## 목표
3컬럼 right 슬롯에 `AIRecColumn` 배치 — 필드별 AI 추천 카드 + apply wire.

## 변경 파일
- `components/contents/shell/AIRecColumn.tsx` — 신규 (8 필드 행 · RecomCell · onApply)
- `app/(main)/programming/contents/[id]/page.tsx` — EditPane/ReviewPane → AIRecColumn 교체

## Acceptance
- edit/review URL에서 right 컬럼에 AI 추천 카드 8행 표시
- 개별 적용 버튼 클릭 시 onApply 동작
- `npm run typecheck` pass

## 완료
typecheck pass (2026-05-20)
