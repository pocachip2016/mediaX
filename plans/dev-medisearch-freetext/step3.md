# Step 3 — API 클라이언트 (lib/api.ts)

**목표**: `medisearchApi`에 free-text 함수 추가. 기존 content-bound 2함수 유지.

## 변경 파일
- `mediaX-CMS/apps/web/lib/api.ts`

## 추가 내용
```ts
export interface MediSearchFreeResult {
  query: string
  metadata: Record<string, unknown>
  provenance: Record<string, string[]>
  sources_detail: MediSearchSourceDetail[]
  resolved_tmdb_id?: number
  resolved_imdb_id?: string
  facet: MediSearchFacetInfo
}

// medisearchApi에 추가:
searchByTitle: (body: { title: string; production_year?: number; content_type?: string; original_title?: string }) =>
  request<MediSearchFreeResult>(`${BASE}/api/programming/metadata/medisearch/search`, { method:"POST", body: JSON.stringify(body) })

evaluateByTitle: (body: { title: string; production_year?: number; tmdb_id?: number; imdb_id?: string }) =>
  request<MediSearchFacetInfo>(`${BASE}/api/programming/metadata/medisearch/evaluate`, { method:"POST", body: JSON.stringify(body) })
```

## 검증
```bash
cd mediaX-CMS && npm run typecheck 2>&1 | grep -E "error|Error" | head -20
```
