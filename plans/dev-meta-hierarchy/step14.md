# Step 14: mh-fe-3tab (Phase E)

> Milestone: dev-meta-hierarchy

## 읽어야 할 파일

- `docs/dev/meta-hierarchy/fe-design.md` § 4 (Detail page Leaf/Container 설계, Wireframe, 컴포넌트 트리)
- `apps/web/app/(main)/programming/contents/[id]/page.tsx` (현재 954줄 — 전체 확인)
- `backend/api/programming/metadata/schemas.py` (ContentOut, line 41~57)
- `apps/web/lib/api.ts` (ContentDetail, ContentOut 타입)
- `.claude/verify.sh` (mh-fe-3tab case 추가 위치)

## 작업

`fe-design.md §4` 설계를 구현한다.

### 14.A — Backend 스키마 mini-change

- `backend/api/programming/metadata/schemas.py`
  - `ContentOut` 에 `parent_id: Optional[int] = None`, `season_number: Optional[int] = None`, `episode_number: Optional[int] = None` 추가
  - (DB 모델 `Content` 에 이미 존재 → validate 자동 매핑)

### 14.B — FE 타입 + API 추가

- `apps/web/lib/api.ts`
  - `ContentOut` 인터페이스에 `parent_id: number | null`, `season_number: number | null`, `episode_number: number | null` 추가
  - `metadataApi` 에 `getContentHierarchy(id: number)` 추가 (`GET /contents/{id}/hierarchy` → `StagingItem`)
  - `StagingItem` 타입이 없으면 필요한 최소 인터페이스 추가

### 14.C — 공통 컴포넌트

`apps/web/components/contents/detail/` 디렉토리(신규):

- `BreadcrumbNav.tsx` — `parents: {id: number, title: string, content_type: string}[]` props, 클릭 시 `/contents/{id}` 이동
- `ChildrenTable.tsx` — `children: ContentOut[]`, `parentType: "series"|"season"` props
  - series: 번호(season_number) · 제목 · 상태 · 품질 → 행 클릭 `/contents/{id}`
  - season: 번호(episode_number) · 제목 · 상태 · 품질 · 런타임 → 행 클릭 `/contents/{id}`

### 14.D — LeafMetaHeader + DetailLeafLayout

- `apps/web/components/contents/detail/LeafMetaHeader.tsx` — 포스터 + content_type 배지 + 제목 + 메타(CP/연도/장르/런타임) + 시놉시스 + 액션 버튼
- `apps/web/components/contents/detail/DetailLeafLayout.tsx`
  - props: `content`, `onEdit`, `onEnrich` 등 기존 page.tsx 로부터 전달
  - 3탭(글자/이미지/영상) wrapper — 탭 내용은 기존 page.tsx JSX 이동
  - episode 이면 `BreadcrumbNav` 표시 (parentChain 로딩)

### 14.E — DetailContainerLayout + page.tsx 통합

- `apps/web/components/contents/detail/DetailContainerLayout.tsx`
  - 메타 헤더(포스터 없는 경우 fallback) + `ChildrenTable`
  - season 이면 `BreadcrumbNav` 표시
  - children 로딩 시 spinner
- `apps/web/app/(main)/programming/contents/[id]/page.tsx`
  - `content_type` 기반 dispatcher: `isLeaf = ["movie","episode"]` → `<DetailLeafLayout>`, 나머지 → `<DetailContainerLayout>`
  - parentChain fetch (episode: 2번, season: 1번 추가 호출)
  - Container 타입이면 hierarchy fetch → children 추출

### 14.F — verify.sh

- `.claude/verify.sh` — `mh-fe-3tab` case 추가

## Acceptance Criteria

```bash
bash .claude/verify.sh mh-fe-3tab
```

- BE 스키마: `ContentOut.parent_id` 필드 존재 (`schemas.py` grep)
- FE 타입: `api.ts ContentOut` 에 `parent_id` 존재
- `DetailLeafLayout.tsx`, `DetailContainerLayout.tsx`, `BreadcrumbNav.tsx`, `ChildrenTable.tsx` 파일 존재
- `[id]/page.tsx` 에 Leaf/Container dispatcher 로직 존재
- typecheck pass · lint 에러 없음

## 금지사항

- 새 URL 라우트 생성 금지 (`/series/{id}` 등)
- Container 에 3탭 추가 금지
- 고아 노드(D6) 처리 금지 — 별도 follow-up
- page.tsx 전면 재작성 금지 — 기존 state·fetch 로직 최대한 재사용
