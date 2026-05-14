# Step 0: api-types

> GitHub: 미생성 | Milestone: dev-ui-api-wiring

## 읽어야 할 파일
- `mediaX-CMS/apps/web/lib/api.ts` (현재 651줄, 기존 `metadataApi` 객체 구조 파악)
- `backend/api/programming/metadata/schemas.py` (백엔드 Pydantic 스키마와 1:1 매칭)
- `plans/dev-api-consolidation/index.json` (백엔드 18개 함수 명세)

## 작업

`lib/api.ts` 에 dev-api-consolidation 18개 엔드포인트와 1:1 대응하는 TypeScript 인터페이스 + API 함수를 추가한다.

### 추가할 인터페이스 (백엔드 스키마와 1:1)
- `BulkActionRequest` (ids, reason, filter_query?)
- `BulkActionResponse` (job_id, ids_accepted, ids_rejected, errors?)
- `JobStatusOut` (id, status, progress_percent, completed_count, failed_count, errors?)
- `UndoActionRequest`, `UndoActionOut`
- `PromoteAIResultOut`
- `ContentChangelogOut`, `ChangeLogItem`
- `EnrichPreviewOut`, `BatchPreviewOut`
- `SourceSearchOut`, `SourceResult`
- `CreateFromSourcesRequest`, `CreateFromSourcesOut`

### 추가할 API 함수 18개 (`metadataApi` 객체에 추가)

| 카테고리 | 함수 |
|---|---|
| Bulk (5) | `bulkReprocess`, `bulkEnrich`, `bulkProcess`, `bulkRecall`, `bulkDelete` |
| Job (3) | `getJobStatus`, `bulkUndo`, `retryFailedJob` |
| Detail (6) | `promoteAIResult`, `partialReprocess`, `applyExternalFields`, `getChangelog`, `lockFields`, `requestPreviewClip` |
| Add (4) | `enrichPreview`, `batchPreviewCsv`, `sourcesSearch`, `createFromSources` |

### 기존 패턴 유지
```ts
export async function bulkReprocess(ids: number[], reason?: string): Promise<BulkActionResponse> {
  return request('/metadata/bulk/reprocess', { method: 'POST', body: JSON.stringify({ ids, reason }) });
}
```

**주의**: `DELETE /bulk` 는 body 포함이라 `method: 'DELETE', body: JSON.stringify(...)` 필요.

## Acceptance Criteria

```bash
bash .claude/verify.sh ui-wiring-step0
```

- `lib/api.ts` 에 18개 함수명 모두 존재
- 핵심 인터페이스(JobStatusOut, BulkActionResponse 등) 정의 확인
- TypeScript 컴파일 통과 (`npm run typecheck` 또는 `tsc --noEmit`)

## 금지사항
- 기존 함수 시그니처 변경 금지 — 추가만.
- 18개 외 endpoint 함수를 함께 추가하지 말 것 (scope creep 방지).
