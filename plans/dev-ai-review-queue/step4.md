# Step 4: VisualAssetCandidatePanel MVP

## 목적
포스터 후보를 "이미지 메타 데이터" 관점이 아니라 "검수 후보" 관점으로 노출.

## 사용 API (신규 없음)
- `POST /api/programming/metadata/contents/{id}/recommend-posters`
- `GET  /api/programming/metadata/contents/{id}/poster-candidates`
- `POST /api/programming/metadata/contents/{id}/poster/select`

`PosterCandidateOut`은 이미 `id, url, source, is_primary, width, height` 보유 — 추가 백엔드 변경 없음.

## 신규 컴포넌트
`mediaX-CMS/apps/web/components/contents/VisualAssetCandidatePanel.tsx`

### Props
```ts
type Props = {
  contentId: number
  candidates: PosterCandidateOut[]
  primaryId: number | null
  onRecommend(): void                      // POST recommend-posters
  onSelectPrimary(imageId: number): void   // POST poster/select
}
```

### UI
```
[Visual Assets]
┌ Current Primary ──────────────────────┐
│ [thumbnail 2:3]  TMDB · 600×900 · External│
└────────────────────────────────────────┘

[+ TMDB 후보 추천]                          (Recommend 버튼)

Candidates
┌──────────┐ ┌──────────┐ ┌──────────┐
│ thumb    │ │ thumb    │ │ thumb    │
│ TMDB     │ │ CP       │ │ DAM      │
│ 500×750  │ │ 600×900  │ │ 800×1200 │
│ External │ │ CP Prov. │ │ Internal │
│ [Primary]│ │ [Set]    │ │ [Set]    │
└──────────┘ └──────────┘ └──────────┘
```

### Rights badge (계산형 — 컴포넌트 내부)
```ts
function rightsBadge(source: string) {
  switch (source) {
    case "cp":   return { label: "CP Provided", tone: "green" }
    case "tmdb": return { label: "External", tone: "amber" }
    case "dam":  return { label: "Internal OK", tone: "blue" }
    default:     return { label: "Review", tone: "slate" }
  }
}
```

### 동작
- "TMDB 후보 추천" 클릭 → `recommend-posters` POST → 결과 후보 목록으로 갱신
- "Set Primary" 클릭 → `poster/select` POST → primary 갱신
- 이미지 깨짐(`onError`) → 회색 placeholder + `data-broken` 마커

## 부모 페이지 통합
`[id]/page.tsx`의 기존 포스터 영역을 본 컴포넌트로 교체. 이미지 탭 또는 좌측 카드 하단에 배치.

## 변경 파일
- `mediaX-CMS/apps/web/components/contents/VisualAssetCandidatePanel.tsx` (신규)
- `mediaX-CMS/apps/web/app/(main)/programming/contents/[id]/page.tsx` — 기존 포스터 영역 교체

## 검증
- `cd mediaX-CMS && npm run typecheck && npm run lint`
- 시나리오:
  - 후보 0개 콘텐츠 → "TMDB 후보 추천" 버튼만 표시
  - 후보 추천 실행 → 후보들 카드 표시
  - "Set Primary" → 목록 페이지로 돌아가서 썸네일 갱신 확인
  - 깨진 url 행 → placeholder 표시

## 주의
- Dam 후보는 source='dam'으로 받지만 **MVP에서는 표시만**, "Link to Dam" 액션은 Step 5에서 자리만 마련
- Web Search 후보 / rights workflow는 Later
- aspect ratio 표시는 width/height로 직접 계산 (예: 2:3, 16:9). 없으면 표시 안 함
