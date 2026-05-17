# dev-recommend-detail-page — 추천 상세 화면 plan

> **목적**: AI 메타 추천 검수를 한 화면에서 끝낼 수 있는 신규 상세 화면 `/programming/contents/[id]/recommend` 신설. 기존 `/contents/[id]` 는 유지 (일반 상세 / A·B 비교).
> **검수 워크플로우**: Review Queue 행 클릭 → 신규 라우트 → sticky 액션바·포스터·짧은메타3단·줄거리·AI종합 한 화면 → 즉시 [✓승인 / ✗반려 / ↻재처리 / ✏편집] 결정.

## 사전 컨텍스트 (모든 step 공통)
- 기존 상세 페이지 (945 lines, 너무 큼): `apps/web/app/(main)/programming/contents/[id]/page.tsx`
- 기존 3패널 컴포넌트 (재사용 또는 참조):
  - `apps/web/components/contents/MetadataDiffPanel.tsx` (234 lines, 필드별 소스 비교)
  - `apps/web/components/contents/MetadataEnrichPanel.tsx` (384 lines, 확정/자동/충돌/미입력 분류)
  - `apps/web/components/contents/VisualAssetCandidatePanel.tsx` (218 lines, Primary+후보+Set Primary)
- API 클라이언트: `apps/web/lib/api.ts` (`metadataApi.getContent`, `getRecommendations`, `imageMetaApi.get`, `posterRecommendApi.*`, `damApi.getAssetsByContent`)
- 기존 핸들러 (재사용): `handleApplyRec`, `handleApplyMultiple`, `handleRegenerate`, `handleApplyExternalFields`, `handleRequestPreviewClip`, `handleLockFields`, `handlePartialReprocess`
- 디자인 시스템: Tailwind v4 (OKLch), `cn()` from `@workspace/ui/lib/utils`, `lucide-react` icons
- 상태 흐름 SSOT: `recommendations` (서버) + `appliedFields: Set<string>` (로컬, Apply 후 즉시 UI 반영)

## 최종 레이아웃 (확정안)

```
┌────────────────────────────────────────────────────────────────────┐
│ ← Review Queue로                          홈/편성/콘텐츠/추천      │
└────────────────────────────────────────────────────────────────────┘
╔════════════════════════════════════════════════════════════════════╗ sticky
║ #5067 기생충 [movie] ⏳검토대기  품질[████████░░] 79                 ║
║ [✓승인][✗반려][↻AI재처리][⟲외부재매칭][🔒잠금][✏편집][▶Preview]    ║
╚════════════════════════════════════════════════════════════════════╝

┌── 포스터 (풀폭, 가로 배치) ──────────────────────────────────────────┐
│  ★ Primary                       후보 (3)                            │
│  [JPG 220×330 TMDB]    [B TMDB] [C DAM] [D MAN]  [Set Primary][AI추천]│
└────────────────────────────────────────────────────────────────────┘

┌── 짧은 메타 3단 ────────────────────────────────────────────────────┐
│  현재 메타       │  Diff (소스 비교)        │  AI 추천                 │
│  ───────────────┼─────────────────────────┼─────────────────────────│
│  🎭 장르         │  Watcha 1.00 드라마/스릴러│  [채택됨 — 다중 일치]    │
│  드라마/스릴러   │  TMDB   0.94 Drama       │                          │
│  ───────────────┼─────────────────────────┼─────────────────────────│
│  🏢 CP사 / ⏱런타임 / 🌐 국가 / 📅 연도 / 🎬 감독 / 👤 주연 ... (총 7행)│
└────────────────────────────────────────────────────────────────────┘

┌── 📖 줄거리 (풀폭, 1 row) ─────────────────────────────────────────┐
│  ▼ 현재 메타  [final · ai · 0.79]                                    │
│  ▼ Diff (3 소스 비교)                                                │
│  ▼ AI 추천: ⚠ 충돌 — 위 3개 중 선택                                  │
└────────────────────────────────────────────────────────────────────┘

┌── ✨ AI Recommendation 종합 ────────────────────────────────────────┐
│  avg confidence 0.82 [▓▓▓▓▓▓▓▓░░]                                  │
│  ✓확정(4) ⚡자동(3) ⚠충돌(1) ❌미입력(0)                              │
│  💡 추천 사유 요약                                                    │
│  [✨ 자동 3건 모두 채택] [↻ AI 재생성] [X 추천 무시]                  │
└────────────────────────────────────────────────────────────────────┘

┌── 보조 정보 (Collapsible, 기본 닫힘) ───────────────────────────────┐
│ ▶ 출연진 (12) / ▶ 외부 소스 (3) / ▶ AI 처리 이력 (8)                │
└────────────────────────────────────────────────────────────────────┘
```

## 산출 파일 (전체 sub-step)
```
apps/web/app/(main)/programming/contents/[id]/recommend/
└── page.tsx                                  # 신규 메인 페이지 (~500 lines)

apps/web/components/contents/recommend/        # 신규 디렉토리
├── StickyActionBar.tsx
├── PosterRow.tsx
├── ShortMetaGrid.tsx                          # 7행 × 3열 + cell wrapper들
├── SynopsisRow.tsx
├── AISummaryBottom.tsx                        # avg conf + 카운트 + 추천사유 + bulk
├── SecondaryInfoAccordion.tsx
└── cells/
    ├── MetaCell.tsx                           # 현재 메타 값 표시
    ├── DiffCell.tsx                           # 소스별 비교
    └── RecomCell.tsx                          # AI 추천 + [개별 적용]

apps/web/lib/recommendDerive.ts                # 신규 헬퍼
                                               # - classifyField (confirmed/auto/conflict/missing)
                                               # - reasonSummary (추천 사유 한 줄)
                                               # - avgConfidence

apps/web/app/(main)/programming/contents/review/page.tsx   # 행 클릭 라우트 변경 (1줄)
```

---

## **1.1** — page-scaffold
**Scope**: 신규 라우트 + 페이지 골격 (sticky bar + 5개 섹션 placeholder + accordion 빈 상태). 기능 X, 레이아웃만.

**파일**:
- `apps/web/app/(main)/programming/contents/[id]/recommend/page.tsx` 신규
- `apps/web/components/contents/recommend/StickyActionBar.tsx` 신규 (placeholder)

**시그니처**:
```tsx
// recommend/page.tsx
export default function ContentRecommendDetailPage() {
  const params = useParams()
  const contentId = Number(params.id)
  const [content, setContent] = useState<ContentDetail | null>(null)
  // ... fetch on mount (기존 [id]/page.tsx 의 useEffect 그대로 import)

  if (loading) return <Spinner />
  if (!content) return <NotFound />
  return (
    <div className="space-y-4">
      <Breadcrumb />
      <StickyActionBar content={content} />
      <PosterRowPlaceholder />              {/* TODO: 1.2 */}
      <ShortMetaGridPlaceholder />          {/* TODO: 1.3 */}
      <SynopsisRowPlaceholder />            {/* TODO: 1.4 */}
      <AISummaryBottomPlaceholder />        {/* TODO: 1.5 */}
      <SecondaryInfoAccordionPlaceholder /> {/* TODO: 1.6 */}
    </div>
  )
}
```

**핵심 규칙**:
- sticky bar: `sticky top-0 z-30 bg-white border-b shadow-sm`
- placeholder 는 `<div className="border border-dashed border-slate-300 rounded-lg p-4 text-sm text-slate-400">{label}</div>`
- 액션 버튼 핸들러는 빈 함수 (다음 step 에서 실제 핸들러 연결)

**verify**: `bash .claude/verify.sh recommend-step1.1`
- 페이지 파일 존재 + StickyActionBar 컴포넌트 import 가능
- 빌드 통과: `cd mediaX-CMS && npm run typecheck`
- 브라우저 `/programming/contents/<id>/recommend` 접속 시 placeholder 5개 + sticky bar 표시

---

## **1.2** — poster-row
**Scope**: 풀폭 포스터 행. Primary 좌측 (220×330) + 후보 그리드 가로 배치 + 우측 액션 ([Set Primary], [✨ AI 추천]).

**파일**:
- `apps/web/components/contents/recommend/PosterRow.tsx` 신규

**시그니처**:
```tsx
type Props = {
  contentId: number
  candidates: PosterCandidateOut[]
  primaryId: number | null
  onSelectPrimary: (id: number) => Promise<void>
  onRecommend: () => Promise<void>
}
export function PosterRow(props: Props): JSX.Element
```

**핵심 규칙**:
- `flex flex-row items-start gap-6 p-5 bg-white rounded-lg border`
- Primary 우측에 source 라벨·해상도·★Primary 배지
- 후보 ≥5장: `flex-wrap` 또는 가로 스크롤 (`overflow-x-auto`)
- 빈 상태: "포스터 후보 없음" + `✨ AI 추천 가져오기` 강조 버튼

**verify**: `bash .claude/verify.sh recommend-step1.2`
- PosterRow 컴포넌트 typecheck 통과
- 페이지에서 Placeholder 제거 후 PosterRow mount
- 브라우저에서 후보 있음/없음 두 케이스 표시 확인 (수동 확인은 verify 시 보고만)

---

## **1.3** — short-meta-3grid
**Scope**: 7 필드 × 3 컬럼 grid (Meta | Diff | AI 추천). 가장 핵심 영역.

**파일**:
- `apps/web/components/contents/recommend/ShortMetaGrid.tsx`
- `apps/web/components/contents/recommend/cells/MetaCell.tsx`
- `apps/web/components/contents/recommend/cells/DiffCell.tsx`
- `apps/web/components/contents/recommend/cells/RecomCell.tsx`
- `apps/web/lib/recommendDerive.ts` (classifyField helper)

**필드 목록** (7개, 표시 순서 고정):
1. 장르 (genres)
2. CP사 (cp_name)
3. 런타임 (runtime)
4. 국가 (country)
5. 제작연도 (production_year)
6. 감독 (director)
7. 주연 (cast)

**시그니처**:
```tsx
// ShortMetaGrid.tsx
type Props = {
  content: ContentDetail
  recommendations: RecommendationsOut | null
  appliedFields: Set<string>
  onApply: (rec: FieldRecommendation, source: SourceFieldRec) => Promise<void>
}

// cells/MetaCell.tsx
type MetaCellProps = { field: string; value: string | null }

// cells/DiffCell.tsx
type DiffCellProps = {
  field: string
  rec: FieldRecommendation | null    // null → "Missing"
  onApply: (source: SourceFieldRec) => Promise<void>
}

// cells/RecomCell.tsx
type RecomCellProps = {
  field: string
  rec: FieldRecommendation | null
  isApplied: boolean
  onApply: (source: SourceFieldRec) => Promise<void>
}

// recommendDerive.ts
export type FieldKind = "confirmed" | "auto" | "conflict" | "missing"
export function classifyField(rec: FieldRecommendation | null): FieldKind
export function reasonSummary(rec: FieldRecommendation): string  // "TMDB 일치 0.94"
```

**Grid 구조**:
- `grid grid-cols-[200px_1fr_1fr] gap-x-4 gap-y-0`
- 첫 행은 컬럼 헤더 (현재 메타 / Diff / AI 추천)
- 각 필드 row 사이 `border-t border-slate-100`
- 행 높이 `minmax(56px, auto)`

**핵심 규칙**:
- `classifyField`:
  - rec === null → `missing`
  - `rec.status === "conflict"` → `conflict`
  - `rec.status === "auto"` AND recs.length ≥ 2 AND min(conf) ≥ 0.90 → `confirmed`
  - else → `auto`
- 채택됨 (isApplied) 셀 → 회색 배지 `[채택됨]`, [개별 적용] 버튼 숨김
- conflict 일 때 RecomCell → "위에서 선택" 안내, DiffCell 에서만 Apply
- Apply 클릭 → 상위 `appliedFields.add(field)` 호출, RecomCell·MetaCell 동시 갱신

**verify**: `bash .claude/verify.sh recommend-step1.3`
- 4 신규 컴포넌트 + helper typecheck 통과
- jest 또는 unit 테스트 (선택): `classifyField` 4 케이스, `reasonSummary` 3 케이스
- 브라우저에서 mock recommendations 로 7 행 표시 + 행 정렬 시각 확인

---

## **1.4** — synopsis-row
**Scope**: 풀폭 줄거리 행. 짧은 메타 3단표 아래 위치. 내부 세로 stack: 현재값 → Diff → AI 추천.

**파일**:
- `apps/web/components/contents/recommend/SynopsisRow.tsx`

**시그니처**:
```tsx
type Props = {
  currentSynopsis: string | null
  rec: FieldRecommendation | null
  isApplied: boolean
  onApply: (source: SourceFieldRec) => Promise<void>
  onEdit: () => void
}
```

**핵심 규칙**:
- `flex flex-col gap-3 p-5 bg-white rounded-lg border`
- 현재 메타 섹션: 줄거리 풀텍스트 + final source 배지 + confidence
- Diff 섹션: 소스별 텍스트 비교 (Watcha / TMDB / AI종합), 각 행에 인라인 `[Apply <소스>]`
- AI 추천 섹션: classifyField 결과 → 충돌이면 "위에서 선택" 안내, 자동이면 `[채택됨]` 또는 `[개별 적용]`
- 긴 텍스트는 max-height 200px + 더보기 토글 (`useState`로 expand)

**verify**: `bash .claude/verify.sh recommend-step1.4`
- typecheck 통과
- 페이지에서 SynopsisRow mount + Diff 3소스 표시 확인

---

## **1.5** — ai-summary-bottom
**Scope**: 페이지 최하단 AI 종합 섹션. avg confidence + 카테고리별 카운트 + 추천 사유 요약 + bulk actions.

**파일**:
- `apps/web/components/contents/recommend/AISummaryBottom.tsx`
- `apps/web/lib/recommendDerive.ts` 확장 (`avgConfidence`, `summarizeByKind`)

**시그니처**:
```tsx
type Props = {
  recommendations: RecommendationsOut
  appliedFields: Set<string>
  onApplyAllAuto: () => Promise<void>
  onRegenerate: () => Promise<void>
  onDismiss: () => void
}

// recommendDerive.ts 확장
export function avgConfidence(recs: FieldRecommendation[]): number   // 0~1, auto+conflict 평균
export function summarizeByKind(recs: FieldRecommendation[]): {
  confirmed: string[], auto: string[], conflict: string[], missing: string[]
}
```

**핵심 규칙**:
- avg confidence 게이지: `<div className="h-2 bg-slate-200"><div className="bg-amber-500" style={width: `${avg*100}%`} /></div>`
- 4 카테고리 카운트는 작은 chip 4개 가로 배치 (✓확정 / ⚡자동 / ⚠충돌 / ❌미입력)
- 추천 사유 요약: auto 추천 필드 각각 1줄 (`reasonSummary(rec)` 재사용)
- bulk action: `[✨ 자동 N건 모두 채택]` (auto 만, applied 제외), `[↻ AI 재생성]`, `[X 추천 무시]`

**verify**: `bash .claude/verify.sh recommend-step1.5`
- typecheck 통과
- 페이지에서 AISummaryBottom mount + 4 카테고리 카운트 동적 갱신 확인

---

## **1.6** — secondary-accordion
**Scope**: 보조 정보 collapsible (출연진/외부소스/AI이력). 기본 닫힘.

**파일**:
- `apps/web/components/contents/recommend/SecondaryInfoAccordion.tsx`

**시그니처**:
```tsx
type Props = {
  contentId: number
  cast: ContentCredit[]
  externalSources: ExternalMetaSource[]
  aiHistory: ContentAIResult[] | null
  onLoadAIHistory: () => Promise<void>     // 펼침 시 lazy load
}
```

**핵심 규칙**:
- Radix UI `Accordion` (이미 `packages/ui` 에 있을 가능성 — 없으면 `useState` 기반)
- 각 섹션 헤더: `▶ <라벨> (<count>)`
- AI 이력만 lazy load (펼침 시 호출)
- 출연진/외부소스 컴포넌트는 기존 `[id]/page.tsx` 의 JSX 추출 가능 (라인 502~545 출연진, 별도 영역 외부소스)

**verify**: `bash .claude/verify.sh recommend-step1.6`
- typecheck 통과
- 3 섹션 펼침/접힘 동작 확인

---

## **1.7** — wiring-states-responsive
**Scope**: Review Queue 행 클릭 → 신규 라우트 + 반응형 breakpoint + empty/loading states.

**파일**:
- `apps/web/app/(main)/programming/contents/review/page.tsx` (1줄 변경)
- `apps/web/app/(main)/programming/contents/[id]/recommend/page.tsx` (반응형 클래스 추가, empty/loading 처리)

**변경 사항**:
- review/page.tsx 의 `router.push(`/programming/contents/${row.content_id}`)` → `router.push(`/programming/contents/${row.content_id}/recommend`)`
- ShortMetaGrid 반응형:
  - `≥1280px`: `grid-cols-[200px_1fr_1fr]`
  - `1024~1280px`: `grid-cols-[160px_1fr_1fr]`
  - `<1024px`: 필드별 카드 (Meta·Diff·AI추천 세로 stack)
- empty/loading 상태:
  - content fetch 중: 페이지 전체 spinner
  - recommendations === null: ShortMetaGrid·SynopsisRow·AISummaryBottom 모두 "추천 데이터 없음" + `AI 재생성` 강조
  - posterCandidates === []: PosterRow 빈 상태

**verify**: `bash .claude/verify.sh recommend-step1.7`
- Review Queue 행 클릭 시 `/recommend` 경로로 이동 확인
- 1024px 폭에서 ShortMetaGrid 압축 확인
- 768px 폭에서 카드 stacking 확인

---

## **1.8** — wrap (doc only)
**Scope**: 문서 갱신, 코드 변경 없음.

**파일**:
- `plans/dev-recommend-detail-page/index.json` — 모든 step `completed` + summary + completed_at
- `mediaX-CMS/apps/web/app/CLAUDE.md` — `/programming/contents/[id]/recommend` 라우트 추가
- `TODO.md` — Done 으로 이동
- `apps/web/components/contents/CLAUDE.md` 신규 또는 갱신 (recommend/ 디렉토리 안내)

**verify**: `/verify --skip "doc only"`

---

## 주의사항 (금지 + 이유)
- ❌ **기존 `[id]/page.tsx` 수정 금지** — 신규 라우트만 작업. 기존은 A/B 비교용으로 보존. 라우터 wiring (1.7) 만 review/page.tsx 1줄 변경.
- ❌ **기존 3패널 컴포넌트 (`MetadataDiffPanel` / `MetadataEnrichPanel` / `VisualAssetCandidatePanel`) 직접 수정 금지** — 다른 화면 (`/[id]` 일반 상세) 에서도 사용 중. 필요한 로직은 helper (`recommendDerive.ts`) 로 추출하거나 신규 cell 컴포넌트로 분리.
- ❌ **컬럼 헤더(현재 메타·Diff·AI 추천)를 sticky 로 만들지 마라** — 짧은 메타가 7행이라 sticky 헤더는 noise. 스크롤은 페이지 단위로만.
- ❌ **줄거리에 `<textarea>` 또는 inline edit 금지** — Apply 후 편집 필요시 기존 `/[id]/edit` 라우트로 이동. 이 화면은 검수·선택 전용.
- ❌ **AI 종합 섹션을 sticky bottom 으로 만들지 마라** — sticky 액션바와 영역 중복. AI 종합은 페이지 흐름의 끝에서 자연스럽게 보이도록.
- ❌ **conftest.py `db` fixture 패턴 잊지 마라** — 백엔드 변경은 이 task 없음. 프론트엔드 전용.
- ❌ **verify.sh `recommend-step1.X` 케이스 누락 금지** — 각 sub-step 구현 시 `.claude/verify.sh` 에 케이스 동시 추가. `$BACKEND` 가 아닌 새 변수 필요시 `MEDIAX_CMS="$SCRIPT_DIR/../mediaX-CMS"` 정의.
- ❌ **TypeScript `any` 남용 금지** — `RecommendationsOut` / `FieldRecommendation` / `SourceFieldRec` 타입 사용. 타입 없으면 `apps/web/lib/api.ts` 에 추가.

## 후속 (이번 plan 범위 외)
- review queue → 추천 상세 워크플로우 사용자 테스팅 (5 명 × 3 콘텐츠)
- 추천 사유 요약을 LLM 호출로 동적 생성 (현재는 source_type + confidence 기반 자동 생성)
- 같은 화면에서 multi-content batch 검수 (체크박스 + 다음 콘텐츠)
