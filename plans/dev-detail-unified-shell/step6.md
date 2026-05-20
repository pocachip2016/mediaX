# Step 6: dus-queue-integration (Phase D)

> Milestone: dev-detail-unified-shell

## 작업
Review 큐 행 클릭 시 unified shell로 진입 — `review/page.tsx` + `BulkReviewQueue.tsx` 컴포넌트의 URL 파라미터 추가.

산출:
- `review/page.tsx:382` — 행 클릭 URL에 `?mode=review&return=review` 추가
- `BulkReviewQueue.tsx:110` — 네비게이션 URL을 unified shell 형식으로 통일

## Acceptance Criteria
```bash
/verify dus-queue-integration
```

## 상태
✅ Completed (2026-05-20)
