# Step 2: content-detail

> GitHub: 미생성 | Milestone: dev-ui-api-wiring

## 읽어야 할 파일
- `mediaX-CMS/apps/web/app/(main)/programming/contents/[id]/page.tsx` (5탭 상세 페이지)
- `lib/api.ts` (Step 0 에서 추가된 detail 6개 함수)

## 작업

콘텐츠 상세 페이지의 6개 버튼·탭을 실제 API 에 wiring.

| 버튼 / 탭 | 현재 | 목표 |
|---|---|---|
| AI 결과 "채택" | 미연결 | `promoteAIResult(contentId, resultId)` |
| "AI 재처리" | 미연결 | `partialReprocess(contentId, fields)` |
| "필드별 가져오기" | `alert("Step 2에서")` | `applyExternalFields(contentId, sourceId, fields)` |
| "변경 이력" 탭 | mock 하드코딩 | `getChangelog(contentId)` |
| "잠금" 버튼 | 미연결 | `lockFields(contentId, fields, reason)` |
| "Preview clip" | 미연결 | `requestPreviewClip(contentId)` |

### 패턴
- 변경 이력 탭은 `useEffect` 에서 contentId 변경 시 `getChangelog` 호출 → 로컬 state.
- 잠금 버튼은 토글 → 낙관적 업데이트 + 실패 시 롤백.
- preview-clip 은 비동기 job (백엔드 stub) 이므로 "요청됨" 토스트만.

## Acceptance Criteria

```bash
bash .claude/verify.sh ui-wiring-step2
```

- `[id]/page.tsx` 에 6개 함수명(`promoteAIResult`, `partialReprocess`, `applyExternalFields`, `getChangelog`, `lockFields`, `requestPreviewClip`) 모두 호출 코드 존재
- `alert("Step 2에서")` 같은 placeholder 제거 확인

## 금지사항
- 5탭 구조 변경 금지 (dev-ui-implementation 에서 확정됨).
- 변경 이력 mock 을 완전히 지우지 말 것 — catch 시 fallback 유지.
