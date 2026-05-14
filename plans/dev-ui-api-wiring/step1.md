# Step 1: bulk-modal

> GitHub: 미생성 | Milestone: dev-ui-api-wiring

## 읽어야 할 파일
- `mediaX-CMS/apps/web/components/contents/BulkActionModal.tsx` (현재 `startBulkAction()` 가 mock)
- `lib/api.ts` (Step 0 에서 추가된 5개 bulk 함수 + getJobStatus)

## 작업

`BulkActionModal.tsx` 의 `startBulkAction()` 가짜 progress 타이머를 제거하고, action type 에 따라 실제 API 호출 → `job_id` 획득 → 1초마다 `getJobStatus` 폴링 → 100% 완료 시 종료하는 로직으로 교체.

### 핵심 로직
```ts
const ACTION_MAP = {
  reprocess: metadataApi.bulkReprocess,
  rematch: metadataApi.bulkEnrich,
  process: metadataApi.bulkProcess,
  recall: metadataApi.bulkRecall,
  delete: metadataApi.bulkDelete,
};

const res = await ACTION_MAP[action](ids, reason);
const interval = setInterval(async () => {
  const job = await metadataApi.getJobStatus(res.job_id);
  setProgress(job.progress_percent);
  if (job.status === 'done' || job.status === 'failed') clearInterval(interval);
}, 1000);
```

### 불변 규칙
- mock 데이터 **삭제하지 말고** `catch` 블록에서 fallback 으로 유지 (API 미연결 환경 대비).
- 폴링 interval cleanup 누락 시 메모리 leak — `useEffect` cleanup 또는 모달 close 시 `clearInterval` 보장.

## Acceptance Criteria

```bash
bash .claude/verify.sh ui-wiring-step1
```

- `BulkActionModal.tsx` 에 `metadataApi.bulkReprocess` (또는 ACTION_MAP) + `metadataApi.getJobStatus` 호출 코드 존재
- 가짜 progress 타이머 (`setProgress(prev + ...)` 형태) 제거 확인
- catch 블록의 mock fallback 보존 확인

## 금지사항
- 기존 mock 패턴 완전 제거 금지. `try { API } catch { mock }` 형태 유지.
- 폴링 주기를 1초 미만으로 단축 금지 (백엔드 부하).
