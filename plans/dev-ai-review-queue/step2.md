# Step 2: 프론트 Review Queue 리스트 화면

## 목적
운영자가 "무엇부터 검수할지" 단일 화면에서 결정.

## 경로 & 메뉴
- 페이지: `mediaX-CMS/apps/web/app/(main)/programming/contents/review/page.tsx`
- 메뉴: `config/docs.ts`의 Programming › Contents 섹션에 추가
  ```ts
  { title: "AI Review Queue", href: "/programming/contents/review" }
  ```
  기존 `/new`, `/upload`, `/external` 항목과 같은 레벨.

## API 타입 (lib/api.ts append)
```ts
export type AiReviewQueueRow = {
  content_id: number
  title: string
  content_type: string
  input_type: "bulk" | "manual" | "existing"
  content_status: string
  metadata_status: "missing" | "conflict" | "enhancement" | "clean"
  poster_status: "poster_ok" | "needs_selection" | "dam_match_found" | "external_only" | "no_candidate"
  dam_match_count: number
  risk_level: "low" | "medium" | "high"
  confidence: number
  updated_at: string
}
export type AiReviewQueueSummary = {
  total: number; missing: number; conflict: number;
  needs_poster: number; dam_match: number; high_risk: number;
}
export type PaginatedAiReviewQueue = {
  items: AiReviewQueueRow[]
  summary: AiReviewQueueSummary
  total: number; page: number; size: number
}

// metadataApi에 추가
getAiReviewQueue(params: {
  status?: string
  input_type?: string
  metadata_status?: string
  poster_status?: string
  risk_level?: string
  include_dam?: boolean
  page?: number
  size?: number
}) => Promise<PaginatedAiReviewQueue>
```

Review Queue 페이지는 `include_dam=true` 호출.

## UI 구조 (dense, 운영툴)
```
[AI Review Queue]

┌ Summary ─────────────────────────────────────────────────────────┐
│ Total 237  Missing 41  Conflict 18  Needs Poster 12  Dam 4  High 9│
└──────────────────────────────────────────────────────────────────┘

[Filter chips] All  Missing  Conflict  Dam Match  External Only  High Risk

┌ Table ─────────────────────────────────────────────────────────────┐
│ Title         Input   Metadata    Poster        Dam  Risk  Conf  Updated  │
│ 어쩌고 시즌1  bulk    conflict    needs_select  ●1   high  0.42  …          │
│ ...                                                                       │
└──────────────────────────────────────────────────────────────────────────┘
```

- row 클릭 → `/programming/contents/[content_id]`
- 카드 dashboard 남발 금지 — 상단 summary 1줄만
- 첫 MVP는 detail drawer 없음
- 빈/로딩/에러 상태 3종 분기 (lib/api.ts 기존 mock fallback 패턴 사용)

## 변경 파일
- `mediaX-CMS/apps/web/lib/api.ts` — 타입 + getAiReviewQueue 추가
- `mediaX-CMS/apps/web/app/(main)/programming/contents/review/page.tsx` (신규)
- `mediaX-CMS/apps/web/config/docs.ts` — Programming › Contents 섹션에 항목 추가

## 검증
```bash
cd mediaX-CMS && npm run typecheck
cd mediaX-CMS && npm run lint
# 브라우저:
# - http://localhost:3000/programming/contents/review (정상 로드)
# - 백엔드 끈 상태 → mock 또는 error UI 표시
# - 필터 chip 토글 → 행 수 변경
# - row 클릭 → 상세 페이지 이동
```

## 주의
- summary 카드는 1행으로 압축 (대시보드 화려하게 만들지 않기)
- 운영툴 dense table — Tailwind v4의 `text-sm`/`py-1` 위주
- row action 컬럼은 MVP에서 "Review" 링크 하나만
