# ADR-005 — Content Detail 3-Column Layout

- **Status**: Proposed (2026-05-20)
- **Phase**: dev-detail-3col-layout / Step 0
- **Related**: ADR-003 (unified shell), ADR-004 (api integration — cancelled, 본 ADR에 흡수)

## Context

ADR-003 unified shell 완료 후, 현재 상세 페이지(`/programming/contents/[id]`) 레이아웃은 다음과 같다.

| 모드 | 현재 레이아웃 | 문제점 |
|---|---|---|
| view | 3컬럼 (Poster 200px / ContentShell 1fr / ViewPane 420px) | view 단순 조회에 Diff/추천 노출 → 노이즈 |
| edit | 2컬럼 (ContentShell 380px / EditPane 1fr) | 좌측 정보가 좁고 우측은 폼만 — AI 추천 함께 보기 어려움 |
| review | 2컬럼 (ContentShell 380px / ReviewPane 1fr) | 좌측 정보 좁음 · 검수 결정 시 행 단위 추천 비교 불가 |

사용자 요청: edit/review 시 좌(포스터) 중(현재상태) 우(AI 추천)을 **행 단위로 시각 정렬**하고, 하단에서 **일괄 적용/재생성**.

## D1 — 모드별 레이아웃 결정

| 모드 | 결정 |
|---|---|
| view | **2컬럼** (Poster 200px / ContentShell 1fr). Diff·AI 추천 제거. |
| edit | **3컬럼** (Poster ~20% / 현재상태 ~40% / AI 추천 ~40%) + 하단 AI 종합 바. **인라인 편집** 적용. |
| review | edit와 동일한 3컬럼 + 하단 + 별도 reviewer/memo footer 카드 |

### 인라인 편집 채택 근거
- 별도 EditPane 폼은 동일 데이터를 두 번 표시(좌측 카드 + 우측 input) → 중복
- review와 동일한 시각 구조 유지 → 운영자 컨텍스트 전환 비용 감소
- 클릭→input 전환 패턴은 Excel/Notion 친숙

### dai 흡수 근거
- dai Step 2(mockContent.ts)는 이미 `page.tsx` 119–159 `getRecommendations.catch()` 블록으로 인라인 구현됨
- dai Step 3(E2E)·4(wrap)는 본 plan의 Step 6에서 동일 범위로 처리

## D2 — 변경 범위

### Frontend (mediaX-CMS/apps/web)
**신규**:
- `components/contents/shell/ThreeColumnShell.tsx` — 3컬럼 grid 컨테이너
- `components/contents/shell/CurrentStateColumn.tsx` — 중앙 컬럼 (행 단위 카드)
- `components/contents/shell/AIRecColumn.tsx` — 우측 컬럼 (행 단위 추천)
- `components/contents/shell/InlineField.tsx` — 클릭→input 전환 셀
- `components/contents/shell/ReviewDecisionFooter.tsx` — reviewer/memo + 승인/반려 (review 전용)

**변경**:
- `app/(main)/programming/contents/[id]/page.tsx` — 모드별 분기 단순화
- `components/contents/recommend/ShortMetaGrid.tsx` — 좌/우 분리 가능하게 셀 export

**삭제**:
- `components/contents/shell/ViewPane.tsx`
- `components/contents/shell/EditPane.tsx`
- `components/contents/shell/ReviewPane.tsx`

### Backend
변경 없음. 기존 PUT endpoint(`/api/programming/metadata/contents/{id}`) + recommendations + apply 핸들러 재사용.

## D3 — Step 계획 (7 step)

| Step | 이름 | Phase | 범위 | 모델 |
|---|---|---|---|---|
| 0 | adr-and-cancel-dai | A | ADR-005 + dai 취소 + plan skeleton | Opus |
| 1 | view-mode-simplify | B | view 분기 → 2컬럼, ViewPane 삭제 | Sonnet |
| 2 | three-column-shell | C | ThreeColumnShell + 우측 placeholder | Sonnet |
| 3 | ai-rec-column | D | AIRecColumn 행 단위 카드 + 적용 wire | Sonnet |
| 4 | inline-edit | E | InlineField + EditPane 흡수 → 삭제 | Sonnet |
| 5 | row-alignment | F | 중·우 카드 쌍 높이 정렬 + 빈 자리 처리 | Sonnet |
| 6 | verify-wrap | G | typecheck/E2E + TODO/CLAUDE/CHANGELOG + verify.sh | Haiku |

## D4 — 행 정렬 전략

| 옵션 | 장점 | 단점 |
|---|---|---|
| A. flex + `min-h-*` 동기화 | 단순, 카드 독립 유지 | 동기화 깨지면 시각 어긋남 |
| B. row 단위 grid `grid-cols-[1fr_1fr]` 묶기 | 자동 정렬 | 카드 그룹화 강제 |
| C. CSS subgrid (`grid-template-rows: subgrid`) | 가장 견고 | 브라우저 지원/이해 비용 |

**선택**: **B (row grid)**. ContentShell 내부 카드 6개를 row 단위로 묶고 (Identity / ShortMeta / Synopsis / Accordion) 각 row 안에서 좌·우 셀 배치. Step 5에서 적용.

## D5 — Out of Scope
- container(series/season) 화면 — 본 plan은 leaf(영화/에피소드)만 대상. container는 별도 plan.
- mobile responsive — desktop 1280+ 우선. 후속 plan.
- 다국어 — 모든 라벨 한국어.
- review 모드의 reviewer/memo 영구 저장 — 기존 백엔드 endpoint 재사용.

## D6 — Acceptance Criteria

- view URL(`?mode=` 없음) → 2컬럼, 우측 AI 추천 패널 미노출
- edit URL(`?mode=edit`) → 3컬럼, 중앙 필드 click → 인라인 input 전환 가능, 저장 시 PUT
- review URL(`?mode=review`) → 3컬럼 + 하단 ReviewDecisionFooter, 승인/반려 동작
- 행 정렬: 중·우 카드가 동일 row에서 같은 높이로 표시
- `npm run typecheck` pass
- mock fallback 유지 (백엔드 없이도 화면 동작)

## D7 — Risk & Mitigation

| Risk | Mitigation |
|---|---|
| 인라인 편집 form 검증 분산 | InlineField에 `validate?: (v) => string \| null` prop |
| 카드 높이 동기화 깨짐 | Step 5에서 row grid로 강제 |
| dai 취소 시 진행 정보 손실 | dai index.json 보존 + `cancellation_reason` 필드 추가 |
| ContentShell의 SecondaryAccordion(탭) 우측 정렬 불명확 | 우측 행에 `CastRecCard` 단일 카드만 배치 (탭 무관) |
