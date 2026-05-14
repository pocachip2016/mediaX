# Step 3: add-modal

> GitHub: 미생성 | Milestone: dev-ui-api-wiring

## 읽어야 할 파일
- `mediaX-CMS/apps/web/components/contents/AddContentModal.tsx`
- `mediaX-CMS/apps/web/app/(main)/programming/contents/pipeline/page.tsx`
- `lib/api.ts` (Step 0 추가 함수: `sourcesSearch`, `createFromSources`, `batchPreviewCsv`, `retryFailedJob`)

## 작업

### AddContentModal.tsx
- External 탭 검색창: 하드코딩 배열 → `sourcesSearch(query, sources)` 호출 (debounce 300ms)
- "이 소스로 등록" 버튼: `createFromSources(sourceId, fields, cpName)` 호출 → 성공 시 모달 close + 토스트
- CSV 탭 미리보기: 하드코딩 카운트 → `batchPreviewCsv(csvData)` 호출

### pipeline/page.tsx
- `handleRetry()`: 기존 `triggerEnrich(item.id)` → `retryFailedJob(jobId)` 로 교체
- job_id 가 row 에 없으면 retry 버튼 비활성화

## Acceptance Criteria

```bash
bash .claude/verify.sh ui-wiring-step3
```

- `AddContentModal.tsx` 에 `sourcesSearch`, `createFromSources`, `batchPreviewCsv` 모두 호출 확인
- `pipeline/page.tsx` 에 `retryFailedJob` 호출 + `triggerEnrich` 호출 제거 확인

## 최종 통합 검증

브라우저에서:
1. 콘텐츠 목록 → Bulk 모달 → 실제 bulk 요청 전송 확인 (Network 탭)
2. 콘텐츠 상세 → "변경 이력" 탭 → API 응답 렌더링
3. Add 모달 External 탭 → 검색어 입력 → 백엔드 결과 표시
4. pipeline 페이지 → 실패 row retry → job 재시작 확인

## 금지사항
- pipeline/page.tsx KPI 카드 구조 변경 금지 (ui-impl-4 에서 확정됨).
- sources/search 결과를 캐싱 없이 매 키 입력마다 호출 금지 (debounce 필수).
