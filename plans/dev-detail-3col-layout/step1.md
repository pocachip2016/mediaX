# Step 1: view-mode-simplify (Phase B)

> Milestone: dev-detail-3col-layout

## 읽어야 할 파일
- `plans/dev-detail-3col-layout/step0.md` (ADR-005 결정 사항)
- `app/(main)/programming/contents/[id]/page.tsx` — view 분기 (lines 276-319)
- `components/contents/shell/ViewPane.tsx` — 삭제 대상

## 작업
1. `page.tsx` view 분기: `grid-cols-[200px_1fr_420px]` → `grid-cols-[200px_1fr]`
2. `page.tsx` 에서 `<ViewPane>` JSX + ViewPane import 제거
3. `page.tsx` 에서 ViewPane 관련 handler prop(onApplyAllAuto, onRegenerate, appliedFields, recommendations)은 edit/review 분기에서 여전히 사용 → 제거 금지
4. `ViewPane.tsx` 삭제

## 산출
- `app/(main)/programming/contents/[id]/page.tsx` — view 분기 변경
- `components/contents/shell/ViewPane.tsx` — 삭제

## Acceptance Criteria
```bash
bash /home/ktalpha/Work/mediaX/.claude/verify.sh 1
```
- view URL(`?mode=` 없음) → 우측 AI 추천 패널 미노출, 2컬럼만 표시
- `npm run typecheck` pass

## 금지사항
- edit/review 분기 코드 수정 금지 (Step 2에서 진행)
- appliedFields, recommendations 상태 삭제 금지 (edit/review에서 사용)
