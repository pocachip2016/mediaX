# Step 2: three-column-shell (Phase C)

> Milestone: dev-detail-3col-layout

## 읽어야 할 파일
- `plans/dev-detail-3col-layout/step1.md` (Step 1 완료 상태)
- `app/(main)/programming/contents/[id]/page.tsx` — edit/review 분기 (lines 321–381)
- `components/contents/shell/ContentShell.tsx` — 중앙 컬럼에 재사용
- `components/contents/recommend/AISummaryBottom.tsx` — 하단 종합 바에 재사용

## 목표
edit/review 모드를 2컬럼 → 3컬럼으로 전환.
- 좌: PosterPanel (200px)
- 중: ContentShell (1fr) — 현재 상태
- 우: EditPane/ReviewPane (1fr) — Step 4에서 인라인 편집으로 교체 예정
- 하단: AISummaryBottom (전체 너비)

## 작업
1. 신규 `shell/ThreeColumnShell.tsx` 생성 — `poster | current | right | footer` props
2. `page.tsx` edit/review 분기: 기존 2컬럼 flex → ThreeColumnShell 사용
3. AISummaryBottom을 footer prop으로 연결

## 산출
- `components/contents/shell/ThreeColumnShell.tsx` (신규)
- `app/(main)/programming/contents/[id]/page.tsx` (edit/review 분기 수정)

## Acceptance Criteria
```bash
bash /home/ktalpha/Work/mediaX/.claude/verify.sh dev-detail-3col-layout-step2
```
- edit/review URL → 3컬럼(포스터 좌 + 현재상태 중 + 우측 패널) 표시
- 하단 AISummaryBottom 노출
- `npm run typecheck` pass

## 금지사항
- EditPane / ReviewPane 삭제 금지 (Step 4에서 처리)
- ContentShell 내부 수정 금지 (Step 4에서 인라인 편집 추가)
