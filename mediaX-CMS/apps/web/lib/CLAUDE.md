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
metadataApi.getDashboard()
metadataApi.listContents({ status, cp_name, page, size })
metadataApi.createContent({ title, content_type, cp_name, production_year })
metadataApi.triggerProcess(id)
metadataApi.getQueue({ page, size })
metadataApi.reviewAction(id, { action, reviewer, ... })
metadataApi.generate({ title, production_year, cp_name, cp_synopsis })
```
API 오류 시 페이지별 Mock 데이터로 자동 폴백.
