# Step 7: MetadataEnrichPanel — 2패널 AI 추천 적용 화면

## 목적
insert / bulk insert / modify / 검수 상세 공통으로 사용하는 "빈 필드를 채우는" 인터랙션을 단일 컴포넌트로 제공.
- 왼쪽: 비어있거나 편집 가능한 필드 목록 (클릭으로 선택)
- 오른쪽: 선택된 필드의 AI 추천 — 확정 후보 / AI Mix / 대체 후보 계층
- 하단 액션: Apply confirmed only / Apply selected / Regenerate

## 사전 조건
- Step 3 완료 (`MetadataDiffPanel` 존재)
- 기존 `getRecommendations` 응답 스키마 그대로 사용 (신규 백엔드 없음)

## 핵심 설계 결정
| 항목 | 결정 |
|---|---|
| "확정 후보" 조건 | `auto_fill[i].recommendations.length ≥ 2` AND 최소 confidence ≥ 0.90 |
| "Apply confirmed only" | 위 조건을 만족하는 auto_fill 전체 일괄 적용 |
| "AI Mix" | `rec.ai_synthesis` 존재 시 conflict 그룹에서 별도 강조 표시 |
| "대체 후보" | auto_fill 중 확정 조건 미달이거나 conflict 그룹의 개별 후보 |
| Regenerate | `POST /contents/{id}/enrich` (기존 `metadataApi.triggerEnrich`) |
| 진입 경로 | [id]/page.tsx → 기존 MetadataDiffPanel 교체 OR 상단 "AI Enrich" 버튼 클릭 시 오버레이 |

## 신규 컴포넌트
`mediaX-CMS/apps/web/components/contents/MetadataEnrichPanel.tsx`

### Props
```ts
type Props = {
  recommendations: RecommendationsOut
  currentValues: Record<string, string | null>
  onApply(rec: FieldRecommendation, source: SourceFieldRec): Promise<void>
  onApplyAll(targets: Array<{ rec: FieldRecommendation; source: SourceFieldRec }>): Promise<void>
  onRegenerate(): Promise<void>
  onDismiss(): void
}
```

### UI 구조 (2패널)
```
┌ MetadataEnrichPanel ────────────────────────────────────────────────┐
│                                                              [닫기] │
├─────────────────────┬───────────────────────────────────────────────┤
│ Missing / Editable  │ Selected field: {fieldName}                   │
│                     │                                               │
│ ● Title      [빈값] │ ┌─ 확정 후보 ─────────────────────────────┐   │
│ ● Synopsis   [빈값] │ │ "추천 제목"                              │   │
│ ● Runtime    [빈값] │ │ Confidence 98% · TMDB + Watcha + Kobis   │   │
│ ● Country    [빈값] │ │ 3개 External DB 일치              [Apply]│   │
│                     │ └─────────────────────────────────────────┘   │
│ △ Synopsis  [충돌] │                                               │
│                     │ ┌─ AI Mix 추천 ───────────────────────────┐   │
│                     │ │ "AI가 생성한 줄거리..."                  │   │
│                     │ │ Confidence 86% · TMDB + Watcha + AI     │   │
│                     │ │ Mixed AI recommendation           [Apply]│   │
│                     │ └─────────────────────────────────────────┘   │
│                     │                                               │
│                     │ ┌─ 대체 후보 ─────────────────────────────┐   │
│                     │ │ ○ "2024-01-12"  92%  TMDB+Kobis [Apply] │   │
│                     │ │ ○ "2024-01-11"  61%  Watcha     [Apply] │   │
│                     │ └─────────────────────────────────────────┘   │
│                     │                                               │
│                     │ [Apply confirmed only] [Regenerate]           │
└─────────────────────┴───────────────────────────────────────────────┘
```

### 왼쪽 패널 필드 항목
- `missing_fields` → "빈값" 아이콘 (●, amber)
- `conflicts` 필드 → "충돌" 아이콘 (△, red)
- `auto_fill` 필드 → "추천 있음" 아이콘 (✦, blue)
- 클릭 시 오른쪽 패널 갱신, 첫 렌더 시 첫 번째 항목 자동 선택

### 오른쪽 패널 계층
1. **확정 후보**: `auto_fill` 중 `recommendations.length ≥ 2 AND min(confidence) ≥ 0.90`
   - 헤더: `"{n}개 External DB 일치"`, confidence + source 나열
   - `[Apply]` 버튼
2. **AI Mix 추천**: `rec.ai_synthesis !== null` (주로 conflict 그룹)
   - 보라색 배경 강조
   - `[Apply]` 버튼
3. **대체 후보**: 나머지 recommendations (확정 미달 auto_fill + conflict 개별 후보)
   - 라디오 스타일 리스트, 각 행에 `[Apply]`

### Apply confirmed only 동작
```ts
// 확정 조건
function isConfirmed(rec: FieldRecommendation): boolean {
  return (
    rec.status === "auto" &&
    rec.recommendations.length >= 2 &&
    Math.min(...rec.recommendations.map(r => r.confidence)) >= 0.90
  )
}
// 적용 대상: isConfirmed인 auto_fill들의 top recommendation
```

## 부모 페이지 통합
`[id]/page.tsx`:
- 기존 `MetadataDiffPanel` 를 유지하면서 상단에 "AI Enrich →" 버튼 추가
- 버튼 클릭 시 `showEnrich` 상태 토글 → `MetadataEnrichPanel` 렌더 (MetadataDiffPanel 대체)
- Review Queue 상세 진입 시 기본적으로 `showEnrich=true`

## 변경 파일
- `mediaX-CMS/apps/web/components/contents/MetadataEnrichPanel.tsx` (신규)
- `mediaX-CMS/apps/web/app/(main)/programming/contents/[id]/page.tsx` — "AI Enrich" 버튼 + showEnrich 토글

## 검증
```bash
cd mediaX-CMS && npm run typecheck && npm run lint
```
시나리오:
- **확정 후보 있음**: 왼쪽 첫 필드 자동 선택 → 오른쪽에 "확정 후보" 카드 표시
- **AI Mix 있음**: synopsis 선택 → AI Mix 카드 보라색 강조
- **대체 후보만**: confidence 낮은 필드 → 대체 후보 리스트만 표시
- **Apply confirmed only**: 확정 조건 필드만 일괄 적용 후 목록에서 사라짐
- **Regenerate**: triggerEnrich 호출 → 완료 후 recommendations 재조회

## 주의
- 왼쪽 패널 너비 고정 min-w-48, 오른쪽 flex-1 — min-width 900px 미만 시 수직 스택으로 전환 (`flex-col`)
- Apply 중 스피너: 개별 버튼 disabled + applying 상태 string key (`${rec.field}-${source.source_id}`)
- "Apply confirmed only" 버튼: 확정 후보가 0개면 비활성 (disabled + 회색)
- Regenerate 후 바로 `getRecommendations` 재조회는 하지 않음 — Celery 비동기이므로 "재처리 요청됨" 알림만
- MetadataDiffPanel은 삭제하지 않음 — 향후 compact view로 활용 가능
