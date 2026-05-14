# Step 0: 사이드바 + 콘텐츠 목록 (`/programming/contents`)

> GitHub: 미생성 | Milestone: dev-ui-implementation

## 읽어야 할 파일
- `mediaX-CMS/apps/web/config/docs.ts` (line 29-51 programming 섹션)
- `mediaX-CMS/apps/web/app/(main)/programming/contents/page.tsx` (현재 150줄+)
- `mediaX-CMS/apps/web/app/(prototypes)/list/page.tsx` (406줄, 이식 원본)
- `docs/dev/ui-consolidation/02_menu_lifecycle.md` §1 (메뉴 구조) + §3 (status 필터)

## 작업

### 1. 사이드바 메뉴 재구성 (`config/docs.ts`)

programming 섹션에 다음 그룹 추가 (기존 항목 위에 배치):

```
콘텐츠 관리 (신규)
├── 콘텐츠 목록      /programming/contents
└── (Step 3 에서 처리 현황 추가)
```

기존 항목 라벨 변경:
- `메타데이터` → `메타데이터 (레거시)` (그룹 라벨, 하위 11개 항목은 그대로)

기존 `편성표`, `외부 소스` 는 변경 없음.

### 2. 콘텐츠 목록 화면 이식 (`(main)/programming/contents/page.tsx`)

`(prototypes)/list/page.tsx` 의 UI 구조를 production 경로로 옮긴다. 핵심 요소:

- **상태 필터 칩**: `[전체]` `[처리중 ●]` `[검수필요 ◉]` `[승인됨]` `[반려됨]` — UI 4 그룹 모델 (백엔드 enum 6개와는 분리)
- **검색·필터**: 제목 검색 + CP 드롭다운 + 타입 드롭다운
- **다중 선택 체크박스 (3-state)**: 행별 + 헤더 전체선택 (mixed/all/none)
- **sticky 액션 바**: 선택된 항목이 1개 이상일 때 화면 하단 고정 — `[승인]` `[반려]` `[AI 재처리]` `[외부소스 매칭]`
- **품질점수·enrichment 배지**: 행 우측에 점수/배지 표시
- 행 클릭 → `/programming/contents/[id]` 이동 유지 (기존 동작)

mock 우선:
- 프로토타입의 MOCK_DATA 그대로 또는 기존 `metadataApi.listContents()` 응답을 UI 그룹으로 매핑. Step 1 시점은 어느 쪽이든 OK — 단 호출 패턴은 유지 (API 활성화는 dev-api-consolidation).

## Acceptance Criteria

```bash
bash .claude/verify.sh ui-impl-1
```

- 사이드바에 "콘텐츠 관리 → 콘텐츠 목록" 노출 + 기존 "메타데이터 (레거시)" 그룹 노출
- `http://localhost:3002/programming/contents` 접근 시 status 칩 5개·검색·필터 표시
- 다중 선택 시 sticky 액션 바 표시
- 행 클릭 시 상세로 이동

## 금지사항

- API 실제 호출 패턴 변경 X — mock 우선, 시그니처 유지 (dev-api-consolidation 의 영역)
- 기존 `(main)/programming/metadata/*` 페이지 수정·삭제 X — Step 3 에서 일괄 처리
- `(main)/layout.tsx` 변경 X
- 신규 shadcn 컴포넌트 설치 X — 이번 step 은 기존 Badge/Button/Collapsible 만 사용
