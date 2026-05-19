# Step 15: mh-fe-recommend (Phase E)

> Milestone: dev-meta-hierarchy

## 읽어야 할 파일

- `docs/dev/meta-hierarchy/fe-design.md` § 5 (추천 검수 — 외부소스 획득 + 3단 레이어 설계 전체)
- `apps/web/app/(main)/programming/contents/[id]/recommend/page.tsx` (현재 190줄)
- `apps/web/components/contents/recommend/ShortMetaGrid.tsx` (3단 레이어 핵심 — 재사용)
- `apps/web/components/contents/recommend/cells/{DiffCell,RecomCell,MetaCell}.tsx`
- `apps/web/components/contents/recommend/StickyActionBar.tsx`
- `apps/web/lib/api.ts` (RecommendationsOut, triggerEnrich, getRecommendations)
- `.claude/verify.sh` (mh-fe-recommend case 추가 위치)

## 작업

`fe-design.md §5` 설계를 구현한다. 백엔드 변경 없음 (enrich·recommendations API 재사용,
tv-type 외부조회 라우팅은 Phase A 에서 이미 완료).

### 15.A — ExternalSourcePanel (신규)

- `apps/web/components/contents/recommend/ExternalSourcePanel.tsx`
  - props: `content: ContentDetail` (Step 14 의 content_type/parent_id 활용)
  - movie: TMDB/KMDB/KOBIS/Watcha/WebSearch 체크박스 (5소스)
  - tv-type(series/season/episode): KMDB·KOBIS ⊘ 비활성 + "시리즈 조상 단위 조회" 라벨
  - `metadataApi.triggerEnrich(contentId)` 호출 + 진행 배지(✓/⏳/✗)
  - 완료 시 `onComplete()` → 추천 재조회

### 15.B — InheritedLockCell + 상속 분기 (신규 + ShortMetaGrid prop)

- `apps/web/components/contents/recommend/cells/InheritedLockCell.tsx`
  - 🔒 잠금 셀 — "시리즈에서 상속" 표시, ②③열 대체
- `ShortMetaGrid.tsx` 수정
  - prop `inheritedFields: string[]` 추가 (Step 14 의 `inherited_meta` 키 기반)
  - 상속 필드 행은 DiffCell/RecomCell 대신 `InheritedLockCell` 렌더
  - "Missing" 표기 금지 — 빈 상속 필드도 "상속"으로 표기

### 15.C — SeriesImpactBanner + StickyActionBar 분기 (신규 + 수정)

- `apps/web/components/contents/recommend/SeriesImpactBanner.tsx`
  - series 노드 검수 시 "승인 시 하위 N 시즌 · M 에피소드 상속 갱신" 경고
  - children 수는 Step 14 의 hierarchy fetch 재사용
- `StickyActionBar.tsx` 수정
  - season/episode: 브레드크럼 표시 (Step 14 `BreadcrumbNav` 재사용)
  - episode: "→ 시리즈 검수로 이동" 링크

### 15.D — recommend/page.tsx 통합

- `apps/web/app/(main)/programming/contents/[id]/recommend/page.tsx`
  - `content_type` 분기: movie=평면 / tv-type=상속·브레드크럼
  - `ExternalSourcePanel` 삽입 (PosterRow 위)
  - series 노드면 `SeriesImpactBanner` 표시
  - `inheritedFields` 계산 → `ShortMetaGrid` 전달

### 15.E — BulkReviewQueue (신규)

- `apps/web/components/contents/BulkReviewQueue.tsx`
  - movie bulk: 평면 큐 (인덴트 없음)
  - series bulk: 계층 인덴트 큐 (시리즈 우선 동선, 시즌 "상속(자동)" 스킵)
  - 필터 [전체/검수대기/상속/충돌] · 정렬 계층순
  - 행 클릭 → `/contents/{id}/recommend` 진입
  - 진입점: bulk upload 결과 패널 "추천 검수 →" 링크 (Step 13 결과 패널 연계)

### 15.F — verify.sh

- `.claude/verify.sh` — `mh-fe-recommend` case 추가

## Acceptance Criteria

```bash
bash .claude/verify.sh mh-fe-recommend
```

- `ExternalSourcePanel.tsx`, `InheritedLockCell.tsx`, `SeriesImpactBanner.tsx`, `BulkReviewQueue.tsx` 파일 존재
- `recommend/page.tsx` 에 content_type 분기 + ExternalSourcePanel 통합
- `ShortMetaGrid` 에 `inheritedFields` prop 존재
- movie → 5소스 / tv-type → KMDB·KOBIS ⊘ 분기 (grep)
- typecheck pass · lint 에러 없음
- 기존 recommend 흐름(승인/반려/포스터/Apply) 회귀 없음

## 금지사항

- 새 3단 레이아웃 발명 금지 — `ShortMetaGrid` 3열 재사용
- 상속 필드 복사 prefill 금지 (D3) — 🔒 잠금만
- tv-type 에 KMDB/KOBIS 조회 노출 금지 (ADR D2)
- 새 URL 라우트 금지 — `/contents/{id}/recommend` 유지
- 시즌 노드 강제 검수 금지 — 상속 시즌 "자동" 스킵 허용
- 백엔드 enrich/recommendations API 변경 금지
