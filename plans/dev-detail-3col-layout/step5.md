# Step 5: row-alignment (Phase F)

> Milestone: dev-detail-3col-layout

## 작업
- `AlignedFieldRows.tsx` 신규 — CurrentStateColumn + AIRecColumn 병합
  - `FieldRow`: `grid-cols-[3rem_1fr_1fr]` 행 내 label / 현재상태 / AI추천 정렬
  - `ColHeaders`: "현재 상태 | AI 추천" 컬럼 헤더 (카드별)
  - 4개 카드: 제목/quality bar 헤더 + 식별정보 + 메타필드 + 시놉시스
  - 빈 자리: AI rec 없는 필드(유형) → `—` 표시
- `ThreeColumnShell.tsx` — `alignedFields` prop 추가 (edit 모드용 2컬럼 경로)
- `page.tsx` — 3중 chained ternary (`view` / `edit` / `review`)
  - edit: `ThreeColumnShell alignedFields=<AlignedFieldRows>`
  - review: `ThreeColumnShell current=<ContentShell> right=<AIRecColumn>` (변경 없음)
- `CurrentStateColumn.tsx` 삭제 (AlignedFieldRows에 통합)

## 산출
- `components/contents/shell/AlignedFieldRows.tsx` (신규)
- `components/contents/shell/ThreeColumnShell.tsx` (alignedFields prop 추가)
- `app/(main)/programming/contents/[id]/page.tsx` (edit 분기 교체)
- `components/contents/shell/CurrentStateColumn.tsx` (삭제)

## Acceptance Criteria
```bash
npm run typecheck  # pass
```
- edit 모드: 연도/국가/상영/CP사/장르/감독/주연/줄거리가 현재상태↔AI추천 행 단위 정렬
- 빈 자리(유형): 우측 AI 추천 열 `—`
- review 모드: 기존 3컬럼 레이아웃 유지
