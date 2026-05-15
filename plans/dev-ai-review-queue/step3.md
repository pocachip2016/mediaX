# Step 3: MetadataDiffPanel 분리 + 추천 패널 위치 정리

## 목적
상세 페이지 내 인라인 `RecommendationPanel`(1041행짜리 page.tsx의 60행~)을 별 파일로 분리하고, 행 표시를 통일된 컬럼 구조(`Field|Current|Suggestion|Source|Confidence|Action`)로 정리.

## 미커밋 변경 합류
현재 unstaged 변경(`[id]/page.tsx` 추천 패널을 헤더 2열 grid에서 빼서 하단 풀폭 배치)을 본 Step에 합쳐서 한 커밋으로 처리.

## 신규 컴포넌트
`mediaX-CMS/apps/web/components/contents/MetadataDiffPanel.tsx`

### Props
```ts
type Props = {
  recommendations: RecommendationsOut
  currentValues: Record<string, string | null>   // 현재 콘텐츠 값 (Current 컬럼 표시용)
  onDismiss(): void
  onApply(rec: FieldRecommendation, source: SourceFieldRec): void
  onApplyAll(): void                              // auto_fill만
  onEditManually(field: string): void
}
```

### 표시 구조
```
┌ Metadata Diff — 3개 미입력 · 2개 충돌 ──────────── [모두 채택] [닫기] ┐
│                                                                          │
│ Field      Current        Suggestion           Source     Conf   Action  │
│ ───────────────────────────────────────────────────────────────────────  │
│ runtime    —              132분                 TMDB      0.94   [Apply] │
│ country    —              대한민국              TMDB      0.94   [Apply] │
│ cast       —              김설현 · 오정세 외   Watcha    1.00   [Apply] │
│                                                                          │
│ ▼ Conflicts                                                              │
│ synopsis   "AAA…"         "BBB…"                Watcha    1.00   [Apply] │
│                           "CCC…"                TMDB      0.94   [Apply] │
│                           [AI 종합: "DDD…"]                       [Apply]│
│                                                                          │
│ [현재 유지]  [수동 편집]                                                 │
└──────────────────────────────────────────────────────────────────────────┘
```

### 규칙
- **Apply All**: `auto_fill`에만 — conflict 일괄 적용 금지
- **AI synthesis 행**: `rec.ai_synthesis`가 있을 때만, conflict 그룹 안에서 강조 배경
- **빈 상태(clean)**: 부모가 패널 자체를 렌더하지 않음 (현재 page.tsx 조건 그대로 유지)

## 부모 페이지 수정
`mediaX-CMS/apps/web/app/(main)/programming/contents/[id]/page.tsx`:
1. 인라인 `function RecommendationPanel(...)` 제거 (대략 60~190행)
2. `import { MetadataDiffPanel } from "@/components/contents/MetadataDiffPanel"` 추가
3. 호출부 교체 — props 매핑 (`currentValues`는 `content_detail`에서 추출)
4. 미커밋 변경(헤더 2열 grid → 풀폭 + 추천 패널 하단) 그대로 유지

## 변경 파일
- `mediaX-CMS/apps/web/components/contents/MetadataDiffPanel.tsx` (신규)
- `mediaX-CMS/apps/web/app/(main)/programming/contents/[id]/page.tsx` — 인라인 제거 + import + 위치 변경

## 검증
- `cd mediaX-CMS && npm run typecheck && npm run lint`
- 3 시나리오 수동 확인:
  - **Missing만**: auto_fill 행만 표시, [모두 채택] 활성
  - **Conflict 포함**: conflict 그룹 표시, [모두 채택] 클릭해도 conflict는 영향 없음
  - **Clean**: 패널 자체 렌더 안 됨
- Apply 후 해당 행이 패널에서 사라지는지 (재조회 동작) 확인

## 주의
- 인라인 함수에서 사용하던 mock 추천 데이터(page.tsx 250행대)는 그대로 두기 — 백엔드 폴백 용도
- `handleApplyRec`/`handleApplyAllAuto` 시그니처 변경 없음
- 컴포넌트 자체에는 fetch 로직 넣지 않음 (부모가 주입)
