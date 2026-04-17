# apps/web/lib/ — 유틸리티 라이브러리

## 파일
| 파일 | 역할 |
|------|------|
| `nav.ts` | 네비게이션 헬퍼 (브레드크럼, 활성 메뉴, 페이저) |
| `api.ts` | FastAPI 백엔드 HTTP 클라이언트 + TypeScript 타입 |

## nav.ts
`config/docs.ts`의 `NavSection[]`을 기반으로 동작.
- `getActiveNav(pathname)` — 현재 경로의 활성 섹션/아이템
- `getBreadcrumbs(pathname)` — `[{title, href}]` 배열, 중복 제거
- `getPagerLinks(pathname)` — 같은 섹션 내 이전/다음 링크
- `getFlatNav()` — 전체 플랫 목록 (검색용)

## api.ts
`metadataApi` 객체로 백엔드 통신:
```ts
tmdbApi.list({ content_type?, search?, page?, size? })  // TMDB 매핑 콘텐츠 목록
metadataApi.getDashboard()
metadataApi.listContents({ status, cp_name, title, content_type, production_year, page, size })
metadataApi.getContent(id)
metadataApi.createContent({ title, content_type, cp_name, production_year })
metadataApi.triggerProcess(id)
metadataApi.getQueue({ page, size })
metadataApi.reviewAction(id, { action, reviewer, ... })
metadataApi.generate({ title, production_year, cp_name, cp_synopsis })
metadataApi.getStaging({ content_type, page, size })
metadataApi.bulkApprove({ content_ids, reviewer })
metadataApi.bulkReject({ content_ids, reviewer })
metadataApi.triggerEnrich(id)
metadataApi.getHierarchy(id)          // 시리즈 계층 트리 (StagingItem 재귀)
metadataApi.getPipelineStatus()
metadataApi.uploadBatch(formData)
metadataApi.getBatchJob(jobId)

imageMetaApi.list({ completed, page, size })
imageMetaApi.get(id)                  // ContentImageOut[] 포함
textMetaApi.list / get / update / bulkComplete
videoMetaApi.list / get / update / bulkComplete
serviceReadinessApi.get()             // ServiceReadinessStats
```

## 주요 타입
- `ContentStatus` — `waiting | processing | staging | review | approved | rejected`
- `ContentType` — `movie | series | season | episode`
- `ContentOut` — 기본 콘텐츠 (country?: string | null 포함)
- `ContentDetail` — ContentOut + metadata_record
- `StagingItem` — `{ content, metadata, diff, external_sources, children }` 재귀 계층
- `ImageMetaOut` — `images: ContentImageOut[]` + has_poster/thumbnail/stillcut/banner/logo
- `PipelineStatus` — 상태별 카운트 + avg_quality_score + last_email_poll
- `ServiceReadinessStats` — text/image/video/all_completed + total
- `BatchJobOut` — 배치 작업 이력
- `TmdbSyncedItem` — content_id/title/tmdb_id/poster_url/match_confidence/matched_at/quality_score
- `PaginatedTmdbItems` — items + total + page + size

API 오류 시 페이지별 Mock 데이터로 자동 폴백.
