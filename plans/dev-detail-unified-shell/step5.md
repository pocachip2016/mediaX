# Step 5: dus-mode-routing (Phase D)

> Milestone: dev-detail-unified-shell

## 작업
URL `?mode=view|edit|review` SSOT 전환 + ViewPane/EditPane/ReviewPane 3분기 dispatch + `/edit`, `/recommend` redirect 구현.

산출:
- `useSearchParams()` → `mode` 파라미터 파싱
- ModePane 컴포넌트로 3패널 dispatch
- `/edit`, `/recommend` → `?mode=edit`, `?mode=review` redirect

## Acceptance Criteria
```bash
/verify dus-mode-routing
```

## 상태
✅ Completed (2026-05-20)
