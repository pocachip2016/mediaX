# FE Design — Meta Hierarchy (Phase D)

**Status**: In progress (Step 11)
**Date**: 2026-05-19
**Scope**: `mediaX-CMS/apps/web/` — 검색 / Bulk 업로드 / 상세 / 추천
**관련 ADR**: [adr-001-content-kind-routing.md](./adr-001-content-kind-routing.md) (Decision D10)

본 문서는 ADR-001 D10 의 FE 적용 설계 사양. 백엔드 Phase A~C(content_kind SSOT,
read-time 상속, bulk movie/series 디스패치) 가 완료된 상태에서 FE 가 어떻게
content_type 분기·계층 표시·상속 표시·재사용 패턴을 구현할지 규정한다.

> **재사용 패턴 핵심**: 상세 페이지는 **Leaf** (movie · episode) 와
> **Container** (series · season) 두 패턴으로 분리, 공통 부품(포스터·메타·시놉시스·
> 브레드크럼·상속 배지) 은 양쪽이 공유한다. 재사용 매트릭스는 § 4.3 참조.

---

## § 1. Audit — 현재 FE content_type 핸들링 매핑

### 1.1 진입점 4종 현황

```
┌──────────────────────────────────────────────────────────────────┐
│ 검색 (page.tsx · 618줄)                                            │
│   필터 select [movie│series│season│episode] ✅                     │
│   행 표시 TYPE_CLASS · TypeIcon · TYPE_LABEL ✅                    │
│   계층 트리 / 그룹 ✗      행 클릭 분기 ✗ (모두 /contents/{id})    │
├──────────────────────────────────────────────────────────────────┤
│ Bulk Upload (upload/page.tsx · 284줄)                              │
│   FIELD_DESCRIPTIONS 평면 1세트 (content_type 컬럼 1개로 4타입)   │
│   movie/series 템플릿 분리 ✗     계층 컬럼 가이드 ✗               │
├──────────────────────────────────────────────────────────────────┤
│ 상세 ([id]/page.tsx · 954줄)                                       │
│   contentTypeLabel 라벨 분기만 ✅                                  │
│   leaf/container 레이아웃 분기 ✗   자식 목록 ✗   브레드크럼 ✗    │
│   상속 배지 ✗   parent_chain 사용 ✗                                │
│   → 영화·시리즈·시즌·에피소드 모두 동일 단일 레이아웃              │
├──────────────────────────────────────────────────────────────────┤
│ 추천 ([id]/recommend/page.tsx · 190줄)                             │
│   cells: PosterRow · ShortMetaGrid · SynopsisRow · AISummaryBottom │
│         · SecondaryAccordion · StickyActionBar                     │
│   content_type 분기 ✗   상속 read-only ✗   브레드크럼 ✗           │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 컴포넌트 재사용 컴포넌트 현황

| 컴포넌트 | 위치 | content_type 분기 |
|---|---|---|
| `ContentForm` | `components/contents/ContentForm.tsx` | select dropdown 4타입 ✅ |
| `AddContentModal` | `components/contents/AddContentModal.tsx` | select dropdown 4타입 ✅ |
| `MetadataDiffPanel` | `components/contents/MetadataDiffPanel.tsx` | 무관 |
| `MetadataEnrichPanel` | `components/contents/MetadataEnrichPanel.tsx` | 무관 |
| `VisualAssetCandidatePanel` | `components/contents/VisualAssetCandidatePanel.tsx` | 무관 |
| `recommend/PosterRow` | `components/contents/recommend/PosterRow.tsx` | 무관 |
| `recommend/ShortMetaGrid` | `components/contents/recommend/ShortMetaGrid.tsx` | 무관 |
| `recommend/SynopsisRow` | `components/contents/recommend/SynopsisRow.tsx` | 무관 |
| `recommend/AISummaryBottom` | `components/contents/recommend/AISummaryBottom.tsx` | 무관 |
| `recommend/SecondaryAccordion` | `components/contents/recommend/SecondaryAccordion.tsx` | 무관 |
| `recommend/StickyActionBar` | `components/contents/recommend/StickyActionBar.tsx` | `CONTENT_TYPE_KO` 라벨만 |
| `recommend/cells/{DiffCell,MetaCell,RecomCell}` | `components/contents/recommend/cells/` | 무관 (상속 prop 없음) |

### 1.3 백엔드(Phase A~C) 와 FE 갭

| 백엔드 Decision | FE 반영 상태 | 갭 |
|---|---|---|
| D1 `content_kind` SSOT | ✗ FE 는 리터럴 분기만 | FE 헬퍼/상수 정리 필요 (Step 12) |
| D3 read-time 상속 (`inheritance.resolve_inherited_metadata`) | ✗ `inherited_meta` / `parent_chain` 응답 미사용 | API 응답 스키마 확인 + UI 노출 (Steps 14·15) |
| D4 `parent_id` 계층 SSOT | ✗ FE 는 평면 표시 | 검색 트리 빌더 + 자식 목록 (Steps 12·14) |
| D6 soft-delete cascade | ✗ "고아 노드" 메시지 없음 | 상세에서 부모 삭제 시 경고 (Step 14) |
| D9 bulk movie/series 분리 | ✗ 단일 템플릿 | 템플릿 토글 + 2 CSV (Step 13) |
| D10 검색 / 3탭 / 추천 / bulk 4개 화면 | 부분 ✅ (라벨만) | 본 fe-design 의 § 2~5 가 사양 |

### 1.4 갭 우선순위 요약

1. **검색 (Step 12)** — D1·D4 적용. 행 클릭은 도착 화면이 leaf/container 어디로 가는지를 백엔드 응답이 정하므로 라우팅 자체는 단순 (`/contents/{id}` 고정).
2. **Bulk (Step 13)** — D9 와 1:1, 백엔드 변경 0.
3. **상세 (Step 14)** — D3·D4·D6 통합. **leaf/container 분리** 가 본 phase 의 가장 큰 작업. `[id]/page.tsx` 954줄을 디스패처 + 5개 신규 컴포넌트로 재편 (§ 4).
4. **추천 (Step 15)** — Step 14 의 공통 컴포넌트(브레드크럼·상속 배지) 재사용. cells 에 `inheritedFrom` prop 추가.

### 1.5 즉시 확인 필요 follow-up

- `GET /contents/{id}` 응답에 `inherited_meta` / `parent_chain` 가 포함되는지
  실제 응답 스키마로 확인. 미포함 시 BE 작은 변경 step 을 Phase E 앞에 끼워 넣음 (Step 14 가
  의존). 본 fe-design 의 § 4.5 에 다시 언급.

---

## § 2. Search & Navigation — 평면 검색 + 드릴다운 진입

### 2.1 화면 목적 & 핵심 UX 결정

운영자가 movie / series / season / episode 를 **단일 평면 목록** 에서 검색하고,
행 클릭 시 **드릴다운 (한 화면씩 진입)** 으로 자식 계층을 탐색한다.

> **트리 인덴트 모드 채택하지 않음.**
> - 이유 1: 검색 목록 화면이 작은 행 안에서 시즌/에피소드까지 동시에 노출되면
>   포스터/메타 컬럼이 좁아져 가독성 저하.
> - 이유 2: 검색은 "찾는" 단계, 계층 탐색은 "보는" 단계 — 두 책임을 한 화면에
>   섞지 않는 게 더 자연스러움.
> - 이유 3: 시리즈/시즌의 **자식 목록은 콘텐츠 상세 (Container) 화면에서 이미
>   책임짐** → 두 곳에 동일 로직 중복 회피.
> - 이유 4: 시리즈 행을 클릭했을 때 "시즌 목록을 보고싶다" 가 자연스러운 의도 —
>   인덴트 펼치기는 추가 클릭이 한 번 더 필요 (▶ 누르고 → 행 누르고).

### 2.2 4 화면 드릴다운 흐름

```
┌─────────────────┐    series 클릭     ┌────────────────────┐
│  [A] 검색 목록  │ ─────────────────▶│ [B] 시리즈 상세    │
│  (평면 결과)    │                    │     (Container)    │
│                 │                    │  + 시즌 목록 테이블 │
│  ☐ movie ───┐   │                    │                    │
│  ☐ series ──┼──▶│   movie 클릭       │  season 클릭 ────┐ │
│  ☐ episode ─┘   │   (직행)           │                  │ │
│                 │                    └──────────────────┼─┘
│                 │                                       │
│                 │   episode 클릭                        ▼
│                 │   (직행, 부모 chain 브레드크럼)  ┌────────────────────┐
│                 │   ─────────────────────────────▶│ [C] 시즌 상세      │
│                 │                                 │     (Container)    │
└─────────────────┘                                 │  + 에피소드 목록   │
        │                                           │                    │
        │  movie 클릭                               │   episode 클릭 ───┐│
        ▼                                           └───────────────────┼┘
┌────────────────────┐                                                  │
│  [D-1] 영화 상세   │                                                  ▼
│       (Leaf)       │                                       ┌────────────────────┐
│  포스터 + 메타      │                                       │  [D-2] 에피소드   │
│  + 3탭 (글자/이미지 │                                       │       상세 (Leaf)  │
│   /영상)           │                                       │  포스터 + 메타     │
└────────────────────┘                                       │  + 3탭             │
                                                             │  + 상속 배지       │
                                                             │  + 3단 브레드크럼  │
                                                             └────────────────────┘
```

### 2.3 행 클릭 라우팅 매트릭스

| 클릭한 행 content_type | URL | 도착 화면 | 화면 패턴 | 화면 핵심 |
|---|---|---|---|---|
| `movie` | `/contents/{id}` | [D-1] 영화 상세 | **Leaf** | 포스터 · 메타 · 3탭 |
| `series` | `/contents/{id}` | [B] 시리즈 상세 | **Container** | 메타 + **시즌 목록 테이블** |
| `season` | `/contents/{id}` | [C] 시즌 상세 | **Container** | 메타 + **에피소드 목록 테이블** |
| `episode` | `/contents/{id}` | [D-2] 에피소드 상세 | **Leaf** | 포스터 · 메타 · 3탭 + 상속 배지 + 부모 브레드크럼 |

> **URL 은 단일 `/contents/{id}` 라우트** — 백엔드 `Content` 단일 테이블 + `GET /contents/{id}`
> SSOT 와 1:1. 화면 디스패치는 `[id]/page.tsx` 가 응답 `content_type` 으로
> `DetailLeafLayout` / `DetailContainerLayout` 분기 (§ 4).

### 2.4 [A] Wireframe — 검색 목록 (평면)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 콘텐츠 검색                                              [+ 콘텐츠 추가] [↑ 업로드]│
├─────────────────────────────────────────────────────────────────────────────────┤
│ 검색  [제목       ] [유형 ▼ 전체  ] [CP사    ] [연도 ▼]    [🔍 검색] [초기화]   │
├─────────────────────────────────────────────────────────────────────────────────┤
│ Tabs:  [전체 142]   [처리중 12]   [검수 23]   [승인 88]   [반려 19]              │
├─────────────────────────────────────────────────────────────────────────────────┤
│ ☐  포스터  제목                  유형        CP사      연도  상태   품질  Enrich │
├─────────────────────────────────────────────────────────────────────────────────┤
│ ☐  [img]   기생충                🎬 영화     CJ ENM    2019  승인   96    ✓     │
│ ☐  [img]   오징어 게임 시즌2     📺 시리즈   넷플릭스  2024  스테이징 88   ⏳    │
│ ☐  [img]   서울의 봄             🎬 영화     플러스엠  2023  승인   91    ✓     │
│ ☐  [img]   범죄도시4             🎬 영화     AB ENT    2024  검수   74    ⚠     │
│ ☐  [img]   무빙                  📺 시리즈   Disney+   2023  승인   93    ✓     │
│ ☐  [img]   외계+인 2부           🎬 영화     CJ ENM    2024  대기   —    —     │
│ ☐  [img]   시즌 1 (오징어게임)   📂 시즌     넷플릭스  2021  승인   88    ✓     │
│ ☐  [img]   에피소드 3 (시즌1)    🎞 에피소드 넷플릭스  2021  승인   85    ✓     │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ← 이전  [1] 2  3  4  ...  다음 →                            총 142건 / 20씩    │
└─────────────────────────────────────────────────────────────────────────────────┘
   ▲ 행 클릭 시:
       🎬 영화     → [D-1] 영화 상세 (Leaf)
       📺 시리즈   → [B] 시리즈 상세 (Container — 시즌 목록)
       📂 시즌     → [C] 시즌 상세 (Container — 에피소드 목록)
       🎞 에피소드 → [D-2] 에피소드 상세 (Leaf, 상속 배지 + 브레드크럼)
```

검색 결과는 4 타입이 한 표에 평면 혼재. 사용자는 유형 아이콘으로 "클릭 시
어디로 가는지" 를 미리 인지. **계층 인덴트·expand 토글은 사용하지 않는다.**

### 2.5 [B] Wireframe — 시리즈 상세 (Container, 미리보기)

> **본 wireframe 은 § 4 (상세) 의 미리보기**. § 4 에서 컴포넌트 분리 및 재사용
> 매트릭스를 자세히 다룬다. 여기서는 검색 → 시리즈 진입 시 화면 윤곽만 확인.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ ←  콘텐츠 목록                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│ ┌────────┐  📺 시리즈                       [✨ 추천 검수] [편집] [⋯]       │
│ │        │  오징어 게임 시즌2                                                │
│ │ poster │  Squid Game S2                                                  │
│ │ 2:3    │  🏢 넷플릭스  📅 2024  ⏱ —  🎭 스릴러·드라마                   │
│ │        │                                                                 │
│ └────────┘  시놉시스: 새로운 게임이 시작된다 ...                           │
├─────────────────────────────────────────────────────────────────────────────┤
│ ▼ 시즌 목록 (3건)                                       [+ 시즌 추가]       │
│ ┌─────────────────────────────────────────────────────────────────────┐    │
│ │ 포스터  시즌      제작년도   상태       에피소드 수   품질          │    │
│ ├─────────────────────────────────────────────────────────────────────┤    │
│ │ [img]   시즌 1    2021       승인        9             88 ─┐         │    │
│ │ [img]   시즌 2    2024       처리중      8 (예정)     —     │         │    │
│ │ [img]   시즌 0    2023       승인        3 (특별편)    82    │         │    │
│ └────────────────────────────────────────────────────────────┼─────────┘    │
└────────────────────────────────────────────────────────────────────────┘    │
                                                                              │
                                                       season 행 클릭 ────────┘
                                                       → /contents/{seasonId}
                                                       → [C] 시즌 상세
```

### 2.6 [C] Wireframe — 시즌 상세 (Container, 미리보기)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ ← 시리즈로 │ 오징어 게임 시즌2  ›  시즌 1                                   │  ← 2단 브레드크럼
├─────────────────────────────────────────────────────────────────────────────┤
│ ┌────────┐  📂 시즌                          [✨ 추천 검수] [편집] [⋯]      │
│ │        │  시즌 1                                                           │
│ │ poster │  📅 2021  📺 9 에피소드                                          │
│ │ 2:3    │  🏢 넷플릭스 (시리즈에서 상속)                                  │
│ │        │  시놉시스: (시리즈에서 상속)                                     │
│ └────────┘                                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ ▼ 에피소드 목록 (9건)                                  [+ 에피소드 추가]    │
│ ┌─────────────────────────────────────────────────────────────────────┐    │
│ │ 포스터  EP  제목              방영일       상태    품질   재생시간   │    │
│ ├─────────────────────────────────────────────────────────────────────┤    │
│ │ [img]   01  무궁화 꽃이 폈습니다  2021-09-17  승인   92    62분   ─┐ │    │
│ │ [img]   02  지옥             2021-09-17  검수   74    63분     │ │    │
│ │ [img]   03  우산을 든 남자    2021-09-17  승인   86    55분     │ │    │
│ │ [img]   04  쫄려도 편먹기     2021-09-17  승인   88    32분     │ │    │
│ │ [img]   05  평등한 세상       2021-09-17  승인   90    52분     │ │    │
│ │ ...                                                              │ │    │
│ └──────────────────────────────────────────────────────────────────┼─┘    │
└──────────────────────────────────────────────────────────────────────┼─────┘
                                                                       │
                                                      episode 행 클릭 ─┘
                                                      → /contents/{episodeId}
                                                      → [D-2] 에피소드 상세
```

### 2.7 [D-1/D-2] Wireframe — Leaf 상세 (미리보기)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ [D-2 만] ← 시즌으로 │ 오징어 게임 시즌2 › 시즌 1 › 무궁화 꽃이 폈습니다     │ ← 3단 브레드크럼
│ [D-1 영화는 브레드크럼 없음, 단순 ← 목록으로]                                │
├─────────────────────────────────────────────────────────────────────────────┤
│ ┌────────┐  🎬 영화 (D-1) | 🎞 에피소드 (D-2)   [✨ 추천 검수] [편집] [⋯]   │
│ │        │  기생충 (D-1) | 무궁화 꽃이 폈습니다 (D-2)                       │
│ │ poster │  🏢 CP   📅 연도 [D-2: 상속 배지]   🎭 장르 [D-2: 상속 배지]    │
│ │ 2:3    │  ⏱ 132분 (D-1) | 62분 (D-2)                                     │
│ │        │  시놉시스: ...                                                    │
│ └────────┘                                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ ┃ [글자] ┃  이미지   영상                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ │ 시놉시스 / 출연진 / 감독 / 외부소스 (TMDB·KMDB·KOBIS) / AI 이력           │
│ │ ...                                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

→ Leaf 패턴 (movie & episode 공유). 차이는: episode 에만 (a) 부모 브레드크럼,
(b) 상속 배지. § 4 에서 컴포넌트 재사용 디테일.

### 2.8 컴포넌트 트리 & 재사용 매트릭스 (검색 페이지)

```
ContentsPage  (apps/web/app/(main)/programming/contents/page.tsx)
├─ SearchFormPanel       (기존 유지)
├─ UiGroupTabs           (기존 유지)
├─ BulkActionToolbar     (기존 유지)
├─ ContentsTable         (평면 단일 모드 — 트리 모드 없음)
│   └─ ContentRow        (신규 — 기존 <tr> 추출, content_type 분기는 아이콘/배지만)
└─ Pagination            (기존 유지)

신규/공유:
- ContentRow            — 4 타입 모두 동일 행 컴포넌트 (포스터·제목·유형 배지·CP·연도·상태·품질·편집)
- ContentTypeBadge      — TYPE_CLASS · TypeIcon · TYPE_LABEL 통합 추출 (검색 + 상세 공유)
```

**검색 페이지는 단순화** — 트리/expand/lazy fetch 모두 제거. 자식 계층 탐색은 § 4
Container 상세에서 책임진다.

### 2.9 상태 & API

```ts
// 검색 폼 (기존 유지)
interface SearchForm {
  title: string
  content_type: ContentType | ""
  cp_name: string
  production_year: string
}

// API: 기존 listContents 그대로 — parent_id / include_descendants 옵션 불필요
metadataApi.listContents({
  title, content_type, cp_name, production_year, page, size
})
```

→ Step 12 에서 **백엔드/API 추가 불필요**. 검색 페이지는 기존 API 만으로 동작.
자식 목록 fetch (`parent_id` 옵션) 는 § 4 Container 상세의 책임 → 그곳에서
follow-up 으로 다룸.

### 2.10 빈 / 로딩 / 에러 상태

| 시나리오 | 표시 |
|---|---|
| 검색 로딩 | 기존 spinner + "불러오는 중..." 유지 |
| 검색 결과 0 | "표시할 콘텐츠가 없습니다" 유지 |
| 검색 API 실패 | Mock 데이터 폴백 (현재 동작 유지) |
| 행 클릭 후 상세 로딩 | 별도 — § 4 의 Container/Leaf skeleton 으로 위임 |

### 2.11 변경 예상 파일

| 파일 | 작업 |
|---|---|
| `apps/web/app/(main)/programming/contents/page.tsx` | 변경 거의 없음 — `ContentRow` 추출 정도. 트리/expand 로직 없음 |
| `apps/web/components/contents/search/ContentRow.tsx` | 신규 — 기존 `<tr>` 본문을 컴포넌트로 추출 |
| `apps/web/components/contents/search/ContentTypeBadge.tsx` | 신규 — TYPE_CLASS/TypeIcon/TYPE_LABEL 통합 |

→ **Step 12 는 가벼운 step**. content_type 분기 강화·드릴다운 라우팅은 자연스럽게
이미 됨 (기존 `router.push(\`/contents/\${id}\`)` 이 그대로 유효). 무거운 작업은
§ 4 의 Step 14 (상세 leaf/container 분리) 로 이전.

### 2.12 금지사항

- **새 라우트 만들지 마라** (`/series/{id}`, `/season/{id}` 등). 이유: 백엔드가 단일
  `Content` SSOT — FE 도 단일 `/contents/{id}` 라우트 유지하고 컴포넌트 디스패치만
  분리해야 데이터/URL 모델 일관.
- **검색 페이지에 트리 인덴트·expand 토글 추가하지 마라**. 이유: 자식 계층 탐색은
  Container 상세 (§ 4) 의 책임. 두 곳에 동일 로직 중복 시 유지보수 비용 2배 +
  사용자 경로 분기 혼란.
- **검색 페이지에서 자식 lazy fetch 하지 마라**. 이유: 동일 — 자식 목록 fetch 는
  Container 상세에서 단일 진입점.

### 2.13 Acceptance (Step 12 — 향후)

```bash
bash .claude/verify.sh mh-fe-search
```
- 기존 검색·필터·페이지네이션·다중 선택 회귀 없음
- 행 클릭 → `/contents/{id}` 단일 라우팅 (4 타입 모두 동일)
- 도착 화면이 Leaf / Container 로 올바르게 디스패치 됨 (Step 14 의존)
- `ContentRow` / `ContentTypeBadge` 컴포넌트 추출 후 시각적 회귀 없음

---

## § 3. Bulk Upload — movie / series 템플릿 분리

### 3.1 화면 목적

운영자가 **분리된 템플릿** 으로 콘텐츠를 일괄 업로드:
- **Movie 템플릿**: 평면 영화 행 (1 row = 1 movie)
- **Series 템플릿**: `series_title` 그룹핑 → series / season / episode 노드 자동 upsert

백엔드 Decision D9 (bulk movie/series 디스패치) 와 **1:1 대응** — 백엔드 `_process_movie_row`
는 평면 movie 행만, `_process_series_rows` 는 `series_title` 그룹핑된 행만 받는다.
FE 의 mode 토글이 사용자에게 "어떤 형태로 업로드 중인지" 를 명확히 인지시킨다.

### 3.2 두 템플릿 컬럼 매핑

**Movie 템플릿** (`/templates/movie.csv` — 한 행 = 한 영화)

| 컬럼 | 필수 | 설명 |
|---|---|---|
| `title` | ✅ | 영화 제목 |
| `content_type` | ✅ | 고정값 `movie` |
| `cp_name` | ✅ | CP사명 |
| `production_year` | — | 제작년도 (숫자) |
| `runtime` | — | 런타임 (분, 양수) |
| `synopsis` | — | 줄거리 |
| `cast` | — | 출연진 (쉼표 구분) |
| `directors` | — | 감독 (쉼표 구분) |
| `genres` | — | 장르 (쉼표 구분) |
| `country` | — | 제작국가 |
| `rating_age` | — | 시청등급 |
| `poster_url` | — | 포스터 이미지 URL |

**Series 템플릿** (`/templates/series.csv` — 그룹핑 형태)

| 컬럼 | 필수 | 설명 |
|---|---|---|
| `series_title` | ✅ | 그룹 키 — 같은 시리즈는 같은 값 |
| `content_type` | ✅ | `series` / `season` / `episode` 중 하나 |
| `cp_name` | ✅ | CP사명 |
| `season_number` | 조건부 | `content_type ∈ {season, episode}` 일 때 필수 |
| `episode_number` | 조건부 | `content_type = episode` 일 때 필수 |
| `title` | — | 해당 노드 제목 (생략 시 `series_title S01E01` 자동) |
| `production_year` | — | 제작년도 — **비워두면 series 에서 상속 (D3)** |
| `synopsis` | — | 줄거리 — **비워두면 series 에서 상속** |
| `genres` | — | 장르 — **비워두면 series 에서 상속** |
| `poster_url` | — | 포스터 — **비워두면 series 에서 상속** |
| `country` / `cast` / `directors` / `rating_age` | — | 일반 메타 |
| `runtime` | — | 런타임 — episode 에만 의미있음 |

> **상속 가이드**: FE 는 series 행에 메타를 모두 채우고, season/episode 행은 비워두는
> 패턴을 권장. 백엔드 read-time resolver (`inheritance.resolve_inherited_metadata`)
> 가 조회 시점에 series → season → episode 로 빈 필드를 자동 채움.

**Series 템플릿 행 패턴 예시**:

```csv
series_title,content_type,season_number,episode_number,title,production_year,synopsis,cp_name
오징어 게임 시즌2,series,,,,2024,새로운 게임이 시작된다,넷플릭스
오징어 게임 시즌2,season,1,,시즌 1,,,넷플릭스
오징어 게임 시즌2,episode,1,1,재회,,,넷플릭스
오징어 게임 시즌2,episode,1,2,456번,,,넷플릭스
오징어 게임 시즌2,season,2,,시즌 2,,,넷플릭스
오징어 게임 시즌2,episode,2,1,귀환,,,넷플릭스
```

### 3.3 사용자 플로우

```
1. 페이지 진입 → 템플릿 모드 선택 (movie 또는 series, 미선택 시 업로드 버튼 disabled)
2. 우측 컬럼 안내 패널 + 템플릿 다운로드 버튼이 mode 별로 변경됨
3. 사용자가 템플릿 다운로드 → 로컬에서 편집 → 드랍존에 업로드
4. CSV/Excel 파싱 후 미리보기 (3행) + mode 와 헤더 미스매치 시 경고
5. [업로드] 버튼 → POST /upload/batch → 백엔드가 자동 디스패치
6. 결과 패널: 성공/실패 카운트 + Job ID + 콘텐츠 목록 이동 링크
```

### 3.4 Wireframe A — Movie 모드 선택

```
┌──────────────────────────────────────────────────────────────────────┐
│ ←  일괄 업로드                                                       │
│    CSV 또는 Excel 파일로 여러 콘텐츠를 한 번에 등록합니다             │
├──────────────────────────────────────────────────────────────────────┤
│ ① 템플릿 선택                                                        │
│ ┌────────────────────┐  ┌────────────────────┐                       │
│ │ ●  🎬 영화 (Movie)  │  │ ○  📺 시리즈 (Series)│                      │
│ │ 평면 영화 일괄 업로드│  │ series→season→episode│                     │
│ │ 1 행 = 1 영화       │  │ 계층 일괄 업로드     │                     │
│ └────────────────────┘  └────────────────────┘                       │
├──────────────────────────────────────────────────────────────────────┤
│ ② 컬럼 안내 (Movie)                                                  │
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │ 필드               필수    설명                                  │ │
│ │ title              필수    영화 제목                             │ │
│ │ content_type       필수    고정값 movie                          │ │
│ │ cp_name            필수    CP사명                                │ │
│ │ production_year    선택    제작년도 (숫자)                       │ │
│ │ runtime            선택    런타임 (분)                           │ │
│ │ synopsis           선택    줄거리                                │ │
│ │ ... (8개 더 보기 ▼)                                              │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│ [📥 movie.csv 템플릿 다운로드]                                       │
├──────────────────────────────────────────────────────────────────────┤
│ ③ 파일 업로드                                                        │
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │                                                                  │ │
│ │              ↑ CSV 또는 Excel 파일을 선택하세요                  │ │
│ │              또는 이 영역에 드래그하세요                          │ │
│ │                                                                  │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│ [업로드] [초기화]                                                    │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.5 Wireframe B — Series 모드 선택

```
┌──────────────────────────────────────────────────────────────────────┐
│ ←  일괄 업로드                                                       │
├──────────────────────────────────────────────────────────────────────┤
│ ① 템플릿 선택                                                        │
│ ┌────────────────────┐  ┌────────────────────┐                       │
│ │ ○  🎬 영화 (Movie)  │  │ ●  📺 시리즈 (Series)│                      │
│ └────────────────────┘  └────────────────────┘                       │
├──────────────────────────────────────────────────────────────────────┤
│ ② 컬럼 안내 (Series)                                                 │
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │ 💡 series_title 으로 그룹핑됨 — 같은 시리즈는 같은 값            │ │
│ │ 💡 행 패턴:                                                      │ │
│ │   ▸ season_number / episode_number 모두 비움 → series 노드       │ │
│ │   ▸ season_number 만 채움 → season 노드                          │ │
│ │   ▸ season + episode 채움 → episode 노드                         │ │
│ │ 💡 메타 (synopsis · genres · poster_url 등) 를 비워두면          │ │
│ │    series → season → episode 로 자동 상속됨                      │ │
│ ├──────────────────────────────────────────────────────────────────┤ │
│ │ 필드               필수            설명                          │ │
│ │ series_title       필수            그룹 키                        │ │
│ │ content_type       필수            series/season/episode          │ │
│ │ cp_name            필수            CP사명                         │ │
│ │ season_number      조건부          season/episode 일 때 필수      │ │
│ │ episode_number     조건부          episode 일 때 필수             │ │
│ │ title              선택            노드 제목 (생략 시 자동)        │ │
│ │ ... (8개 더 보기 ▼)                                              │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│ [📥 series.csv 템플릿 다운로드]                                      │
├──────────────────────────────────────────────────────────────────────┤
│ ③ 파일 업로드                                                        │
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │ 📄 squid-game-s2.csv  (12.4 KB)                                  │ │
│ └──────────────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────────┤
│ ④ 미리보기 (첫 3행) — 검증 결과 인라인                               │
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │ series_title    | type    | season | episode | title    | 검증   │ │
│ ├──────────────────────────────────────────────────────────────────┤ │
│ │ 오징어 게임 S2  | series  |   --   |   --    | --       | ✓ OK   │ │
│ │ 오징어 게임 S2  | season  |   1    |   --    | 시즌 1   | ✓ OK   │ │
│ │ 오징어 게임 S2  | episode |   1    |   1     | 재회     | ✓ OK   │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│ [업로드 (6건)] [초기화]                                              │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.6 Wireframe C — Mode 미스매치 경고

```
┌──────────────────────────────────────────────────────────────────────┐
│ ④ 미리보기 — 모드 미스매치 경고                                       │
│ ⚠ 선택한 모드: series                                                │
│   업로드 파일에 series_title 컬럼이 없습니다. 모드를 확인하세요.     │
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │ title       | content_type | cp_name      | year   | 검증         │ │
│ ├──────────────────────────────────────────────────────────────────┤ │
│ │ 기생충      | movie        | CJ ENM       | 2019   | ⚠ movie 행이│ │
│ │ 서울의 봄   | movie        | 플러스엠     | 2023   |   series 모드│ │
│ │                                                    |   템플릿과   │ │
│ │                                                    |   다릅니다  │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│ [모드를 movie 로 전환] [그래도 업로드] [초기화]                      │
└──────────────────────────────────────────────────────────────────────┘
```

→ **소프트 경고**: 사용자가 [그래도 업로드] 를 선택하면 백엔드가 처리. 백엔드의
디스패치 (D9) 가 행마다 content_type 으로 자동 라우팅하므로 클라이언트 강제 차단은
불필요. 단, 무조건 alert 로 한 번 더 확인.

### 3.7 컴포넌트 트리 & 재사용 매트릭스

```
UploadPage  (apps/web/app/(main)/programming/contents/upload/page.tsx)
├─ TemplateModeToggle              (신규)  — radio 2 cards (movie | series)
├─ FieldDescriptionPanel           (분리)
│   ├─ MovieFieldsTable            (신규)  — FIELD_DESCRIPTIONS_MOVIE
│   ├─ SeriesFieldsTable           (신규)  — FIELD_DESCRIPTIONS_SERIES + 안내 박스
│   └─ TemplateDownloadButton      (신규)  — mode 별 static path
├─ DropZone                        (기존 유지)
├─ PreviewTable                    (수정)  — mode 별 validation 표시
│   └─ ModeValidationBadge         (신규)  — ✓ / ⚠ 표시
├─ ModeMismatchWarning             (신규)  — Wireframe C 패널
└─ ResultPanel                     (기존 유지)
```

**재사용**: `parseCSVLine`, 드랍존 UX, 결과 패널, 에러 박스 등 기존 자산 그대로.

### 3.8 상태 & API

```ts
type TemplateMode = "movie" | "series" | null  // null = 미선택

const [templateMode, setTemplateMode] = useState<TemplateMode>(null)
const [validation, setValidation] = useState<{
  rowOk: boolean[]
  modeMismatch: boolean
  reasons: string[]
} | null>(null)

// 파일 변경 시 검증
function validateAgainstMode(headers: string[], rows: PreviewRow[], mode: TemplateMode) {
  if (mode === "series" && !headers.includes("series_title")) {
    return { modeMismatch: true, reasons: ["series_title 컬럼 없음"], rowOk: [] }
  }
  if (mode === "movie" && headers.includes("series_title")) {
    return { modeMismatch: true, reasons: ["series 템플릿이 movie 모드로 선택됨"], rowOk: [] }
  }
  // row-level: series_number / episode_number 일관성 검증
  const rowOk = rows.map((r) => {
    if (mode === "series") {
      if (!r.series_title) return false
      if (r.content_type === "episode" && (!r.season_number || !r.episode_number)) return false
      if (r.content_type === "season" && !r.season_number) return false
    }
    return true
  })
  return { modeMismatch: false, reasons: [], rowOk }
}
```

**API**: `POST /api/programming/metadata/upload/batch` (FormData) **변경 없음** —
백엔드가 행마다 content_type 으로 자동 디스패치. 응답 형식 (`success_count` /
`failed_count` / `id`) 도 유지.

**정적 템플릿**: `apps/web/public/templates/movie.csv` + `apps/web/public/templates/series.csv`
. 다운로드 버튼은 `<a href="/templates/movie.csv" download>` 단순 링크.

### 3.9 빈 / 로딩 / 에러 상태

| 시나리오 | 표시 |
|---|---|
| 페이지 진입 (mode 미선택) | 드랍존 disabled + "먼저 템플릿 모드를 선택하세요" |
| Mode 선택 후 파일 미선택 | 드랍존 활성 + 컬럼 안내 표시 |
| 파싱 실패 (인코딩) | 기존 에러 유지 |
| 모드 미스매치 | Wireframe C 경고 패널 + [모드 전환] / [그래도 업로드] |
| 업로드 중 | 버튼 spinner + disabled |
| 업로드 완료 | 결과 패널 (기존 유지) — 백엔드 응답 그대로 |
| 업로드 부분 실패 | "성공 N건 / 실패 M건" — 실패 사유는 결과 페이지 / 콘텐츠 목록에서 확인 |

### 3.10 변경 예상 파일

| 파일 | 작업 |
|---|---|
| `apps/web/app/(main)/programming/contents/upload/page.tsx` | mode state + 분기 로직 + validation 호출 + ModeMismatchWarning |
| `apps/web/components/contents/upload/TemplateModeToggle.tsx` | 신규 — radio 2 cards |
| `apps/web/components/contents/upload/MovieFieldsTable.tsx` | 신규 — FIELD_DESCRIPTIONS_MOVIE 상수 + 표 |
| `apps/web/components/contents/upload/SeriesFieldsTable.tsx` | 신규 — FIELD_DESCRIPTIONS_SERIES 상수 + 안내 박스 + 표 |
| `apps/web/components/contents/upload/ModeMismatchWarning.tsx` | 신규 — Wireframe C 패널 |
| `apps/web/components/contents/upload/validateAgainstMode.ts` | 신규 — 검증 유틸 (헤더·row 수준) |
| `apps/web/public/templates/movie.csv` | 신규 — Movie 샘플 헤더 + 1행 예시 |
| `apps/web/public/templates/series.csv` | 신규 — Series 샘플 헤더 + 6행 예시 (series·season·episode 혼합) |

### 3.11 금지사항

- **백엔드 라우터를 분리하지 마라** (`/upload/batch/movie`, `/upload/batch/series`).
  이유: 백엔드 D9 가 이미 행마다 디스패치. URL 분리 시 동일 로직 두 진입점 = 유지보수
  2배.
- **모드 미스매치 시 강제 차단 (block) 하지 마라** — 소프트 경고 + [그래도 업로드]
  옵션 유지. 이유: 백엔드가 디스패치 가능. 강제 차단 시 사용자가 우회 경로를 못 찾고
  좌절.
- **CSV preview 에서 백엔드 검증을 흉내내지 마라** (예: dedup 충돌 여부 미리보기).
  이유: 백엔드 책임. FE 는 컬럼 존재·조건부 필수 (season_number, episode_number) 만
  검증.
- **메타 자동 prefill 하지 마라** (예: episode 행에 series 의 synopsis 복사 후
  업로드). 이유: D3 read-time 상속의 정신 — 복사본 stale 발생. 빈 채로 두는 것이 정답.

### 3.12 Acceptance (Step 13 — 향후)

```bash
bash .claude/verify.sh mh-fe-bulk-ui
```
- Mode 토글 동작: movie / series 선택에 따라 컬럼 안내·템플릿 다운로드 분기
- `movie.csv` / `series.csv` 정적 파일 다운로드 동작
- 파일 업로드 후 mode 별 validation: 헤더 누락 / 조건부 필수 누락 시 경고
- 모드 미스매치: 경고 + [그래도 업로드] 정상 동작
- 업로드 성공 시 결과 패널 표시 (기존 회귀 없음)
- 빈/실패/부분 실패 케이스 메시지 정확

---

---

## § 4. Detail Page — Leaf vs Container 분리 (Step 14)

### 4.1 화면 목적

`/contents/{id}` 단일 라우트를 유지하면서, `content_type` 에 따라 두 레이아웃으로 자동 디스패치:

- **Leaf** (`movie` / `episode`) — 포스터 + 메타 헤더 + **3탭** (글자/이미지/영상)
- **Container** (`series` / `season`) — 메타 헤더 + **자식 목록 테이블** (시즌 목록 or 에피소드 목록)

현재 `[id]/page.tsx` 954줄은 4가지 타입 모두 동일 레이아웃 — 이를 두 패턴으로 분리한다.

### 4.2 Backend 선행 변경 (Step 14.pre)

`ContentOut` 스키마에 누락된 3개 필드 추가:

| 필드 | 타입 | 설명 |
|---|---|---|
| `parent_id` | `int \| null` | 부모 content_id (season→series, episode→season) |
| `season_number` | `int \| null` | 시즌 번호 |
| `episode_number` | `int \| null` | 에피소드 번호 |

- DB `Content` 모델에는 이미 존재. `schemas.py ContentOut` 에만 노출 추가.
- `ContentDetail extends ContentOut` 이므로 ContentDetail 도 자동 포함.
- FE `ContentOut` interface (`lib/api.ts`) 에도 동일 필드 추가.

컨테이너 자식 목록: 기존 `GET /contents/{id}/hierarchy` (StagingItem) 를 재사용.
`StagingItem.children` → 직계 자식 목록.

### 4.3 Leaf 레이아웃 (movie / episode)

현재 page.tsx 의 핵심 부분을 `DetailLeafLayout` 컴포넌트로 추출. 변경은 최소화.

**movie 와 episode 의 차이:**
- movie: 브레드크럼 없음, 단순 `← 목록으로` 뒤로가기
- episode: 브레드크럼 표시 (`시리즈제목 › 시즌 N`)  + 부모 링크

```
┌──────────────────────────────────────────────────────────────────┐
│ [episode만] ← 시즌으로  │  오징어 게임 S2 › 시즌 1            │  ← 브레드크럼
│ [movie는] ← 목록으로                                             │
├──────────────────────────────────────────────────────────────────┤
│ ┌────────┐  🎬 영화 | 🎞 에피소드          [✨ 추천 검수] [편집]│
│ │ poster │  기생충 | 무궁화 꽃이 폈습니다  (E01 · S01)         │
│ │ 2:3    │  🏢 CP   📅 연도   🎭 장르   ⏱ 런타임              │
│ │        │  시놉시스 ...                                         │
│ └────────┘                                                       │
├──────────────────────────────────────────────────────────────────┤
│ ┃ [글자] ┃  이미지   영상                                       │
├──────────────────────────────────────────────────────────────────┤
│ 글자탭 내용 (시놉시스, 출연진, 감독, 외부소스, AI 이력)          │
└──────────────────────────────────────────────────────────────────┘
```

**3탭 정의:**
| 탭 | 내용 | 현재 상태 |
|---|---|---|
| 글자 | 시놉시스 · 출연진 · 감독 · 외부소스 · AI 이력 | ✅ 기존 유지 |
| 이미지 | 포스터 후보 · primary 선택 | ✅ 기존 유지 |
| 영상 | 스텁 ("준비 중") | 스텁 유지 |

### 4.4 Container 레이아웃 (series / season)

```
┌──────────────────────────────────────────────────────────────────┐
│ [season] ← 시리즈로   │  오징어 게임 S2 › 시즌 1             │  ← 브레드크럼
│ [series] ← 목록으로                                              │
├──────────────────────────────────────────────────────────────────┤
│ ┌────────┐  📺 시리즈 | 📂 시즌           [✨ 추천 검수] [편집]│
│ │ poster │  오징어 게임 S2 | 시즌 1                            │
│ │ 2:3    │  🏢 CP   📅 연도   🎭 장르                          │
│ │        │  시놉시스 ...                                         │
│ └────────┘                                                       │
├──────────────────────────────────────────────────────────────────┤
│ ▼ 시즌 목록 (series) / 에피소드 목록 (season)      [+ 추가]    │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │ 포스터  번호  제목           상태    품질   하위              │ │
│ ├──────────────────────────────────────────────────────────────┤ │
│ │ [img]   S01   시즌 1         승인    88     9 에피소드      ─┤ │  → 클릭 /contents/{id}
│ │ [img]   S02   시즌 2         처리중  —      8 (예정)          │ │
│ └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

**자식 목록 컬럼:**
- series → 시즌 목록: 번호(season_number), 제목, 상태, 품질, 에피소드 수
- season → 에피소드 목록: 번호(episode_number), 제목, 방영일(production_year), 상태, 품질, 런타임

### 4.5 컴포넌트 트리 & 재사용 매트릭스

```
ContentDetailPage   (apps/web/app/(main)/programming/contents/[id]/page.tsx)
├─ if (isLeaf)  → DetailLeafLayout      (신규 — 기존 page.tsx 핵심 추출)
│   ├─ BreadcrumbNav                    (신규 — episode 에만 표시)
│   ├─ LeafMetaHeader                   (신규 — 포스터 + 메타 헤더)
│   └─ DetailTabs                       (신규 — 글자/이미지/영상 3탭 wrapper)
│       ├─ TextTab                      (기존 page.tsx 글자탭 추출)
│       ├─ ImageTab                     (기존 page.tsx 이미지탭 추출)
│       └─ VideoTab                     (스텁)
└─ if (isContainer) → DetailContainerLayout (신규)
    ├─ BreadcrumbNav                    (신규 — season 에만 표시)
    ├─ ContainerMetaHeader              (신규 — 포스터 + 메타 헤더, leaf와 다른 구성)
    └─ ChildrenTable                    (신규 — series: 시즌 목록 / season: 에피소드 목록)
```

**공유 컴포넌트:**
- `BreadcrumbNav` — episode 와 season 모두 사용. props: `parents: {id, title, content_type}[]`
- `ChildrenTable` — series/season 이 각각 다른 컬럼으로 재사용

### 4.6 API & 상태

```ts
// 기존 (유지)
const [content, setContent] = useState<ContentDetail | null>(null)

// 신규 — Container 타입일 때만
const [children, setChildren] = useState<ContentOut[] | null>(null)

// parent_chain (브레드크럼용) — ContentOut.parent_id 로 1~2회 추가 fetch
const [parentChain, setParentChain] = useState<ContentOut[]>([])
```

**API 호출 전략:**
- `GET /contents/{id}` → 기존 (ContentDetail, parent_id/season/episode 필드 추가됨)
- Container 타입: `GET /contents/{id}/hierarchy` → `StagingItem.children` 에서 직계 자식 추출
- episode 브레드크럼: `content.parent_id` 로 season fetch → season.parent_id 로 series fetch (최대 2번 추가 호출)
- season 브레드크럼: `content.parent_id` 로 series fetch (1번 추가 호출)

### 4.7 빈 / 로딩 / 에러 상태

| 시나리오 | 처리 |
|---|---|
| content_type = null 또는 알 수 없음 | Leaf로 폴백 |
| children fetch 로딩 | ChildrenTable spinner |
| children 없음 | "등록된 시즌/에피소드가 없습니다 [+ 추가]" |
| parent fetch 실패 | 브레드크럼 숨김, 본문 표시 유지 |

### 4.8 변경 예상 파일

| 파일 | 작업 |
|---|---|
| `backend/api/programming/metadata/schemas.py` | `ContentOut` 에 `parent_id`, `season_number`, `episode_number` 추가 |
| `apps/web/lib/api.ts` | `ContentOut` 인터페이스에 동일 필드 추가 + `getContentHierarchy` 함수 추가 |
| `apps/web/app/(main)/programming/contents/[id]/page.tsx` | dispatcher 로직 추가 + Leaf/Container 분기 |
| `apps/web/components/contents/detail/BreadcrumbNav.tsx` | 신규 |
| `apps/web/components/contents/detail/LeafMetaHeader.tsx` | 신규 — 포스터 + 타입 배지 + 메타 |
| `apps/web/components/contents/detail/DetailLeafLayout.tsx` | 신규 — 기존 page.tsx 주요 부분 추출 |
| `apps/web/components/contents/detail/DetailContainerLayout.tsx` | 신규 |
| `apps/web/components/contents/detail/ChildrenTable.tsx` | 신규 |

### 4.9 금지사항

- **새 URL 라우트 만들지 마라** (`/series/{id}`, `/season/{id}` 등)
- **page.tsx 를 완전히 버리지 마라** — 기존 state·API 호출·결과 패널은 재사용
- **고아 처리(D6)를 Step 14 에서 구현하지 마라** — soft-delete cascade 경고는 Step 15 follow-up
- **Container 에 3탭 추가하지 마라** — Container 는 자식 목록이 핵심

### 4.10 Acceptance (Step 14)

```bash
bash .claude/verify.sh mh-fe-3tab
```
- `content_type = movie` → Leaf 레이아웃 (3탭, 포스터 헤더)
- `content_type = series` → Container 레이아웃 (시즌 목록 테이블)
- `content_type = season` → Container 레이아웃 (에피소드 목록 테이블) + 브레드크럼(series)
- `content_type = episode` → Leaf 레이아웃 + 브레드크럼 (시리즈 › 시즌)
- TypeScript typecheck pass · lint 에러 없음
- 기존 추천/이미지/편집 흐름 회귀 없음

---

## § 5. 추천 검수 — 외부소스 획득 + 3단 레이어 (Step 15)

### 5.1 화면 목적

운영자가 외부 소스를 획득하고, **3단 레이어**(현재값 │ 외부소스 raw │ AI 추천·채택)로
메타를 검수·채택한다. movie(Leaf 평면) 와 series/season/episode(계층·상속) 를 분기 처리.

> **3단 레이어 = 기존 `ShortMetaGrid`** — 이미 `MetaCell(현재값) │ DiffCell(외부소스 raw) │
> RecomCell(AI 추천·채택)` 3열 구조 보유. 새 레이아웃 발명 금지, movie/series 분기 prop 만 추가.

### 5.2 3단 레이어 정의

```
┌─ ① 현재값 ────┬─ ② 외부소스 raw ──────┬─ ③ AI 추천·채택 ──┐
│ DB 저장값      │ TMDB/KMDB/KOBIS/Watcha│ AI 종합 + 신뢰도   │
│ (= MetaCell)   │ 소스별 원본+신뢰도     │ + [채택] (=RecomCell)│
└────────────────┴───────────────────────┴─────────────────────┘
```

### 5.3 외부소스 획득 UI — 영화 (Leaf)

```
┌─ 외부 소스 획득 ──────────────────────────────────────────────┐
│ 기생충 (2019) · 🎬 영화                                       │
│ 조회 대상:  ☑ TMDB  ☑ KMDB  ☑ KOBIS  ☑ Watcha  ☐ WebSearch  │
│ [🔍 획득 시작]                                                │
├───────────────────────────────────────────────────────────────┤
│ 진행 ████████░░ 80%                                           │
│  ✓ TMDB 0.94·11필드  ✓ KMDB 0.88·7필드  ✓ KOBIS 0.91·5필드   │
│  ⏳ Watcha 조회 중...                       [완료 → 추천 검수]│
└───────────────────────────────────────────────────────────────┘
```

### 5.4 외부소스 획득 UI — 시리즈/시즌/에피소드 (ADR D2 라우팅)

```
┌─ 외부 소스 획득 ──────────────────────────────────────────────┐
│ 무궁화 꽃이 폈습니다 · 🎞 에피소드 (S01E01)                    │
│ ↳ 외부 조회 단위:  오징어 게임 시즌2 (시리즈 조상) ⓘ           │
│ 조회 대상:  ☑ TMDB(tv)  ⊘ KMDB  ⊘ KOBIS  ☑ Watcha           │
│  ℹ KMDB·KOBIS = 영화 전용 → tv 타입 자동 제외 (ADR D2)        │
│ [🔍 획득 시작]                                                │
├───────────────────────────────────────────────────────────────┤
│  ✓ TMDB(tv) "오징어 게임" 시리즈 매칭 0.92                     │
│    → 시리즈 메타 획득 → 시즌·에피소드 read-time 상속 (D3)      │
└───────────────────────────────────────────────────────────────┘
```

> **tv-type 분기**: (1) 외부조회를 **시리즈 조상 타이틀**로 수행, (2) KMDB/KOBIS
> 체크박스 비활성(⊘), (3) 결과는 시리즈 노드 저장 → 하위 상속.

### 5.5 3단 레이어 검수 — 영화 (단일, Leaf)

```
┌ Sticky ─────────────────────────────────────────────────────────────────┐
│ ← 목록  기생충 (2019) 🎬 영화           [👁 미리보기] [✕ 반려] [✓ 승인]  │
├──────────────────────────────────────────────────────────────────────────┤
│ 포스터 후보:  [●1] [2] [3] [4]                                          │
├──────────┬──────────────┬───────────────────────┬───────────────────────┤
│ 필드      │ ① 현재값     │ ② 외부소스 raw 비교   │ ③ AI 추천·채택        │
├──────────┼──────────────┼───────────────────────┼───────────────────────┤
│ 🎭 장르   │ 드라마       │ TMDB 드라마/스릴러    │ 드라마·스릴러         │
│          │              │ KMDB 드라마           │ 0.93 TMDB+AI [채택]   │
│ 📅 연도   │ 2019 ✓일치   │ TMDB 2019 KMDB 2019   │ — (일치·채택됨)       │
│ ⏱ 런타임 │ — Missing    │ TMDB 132분            │ 132분 [채택]          │
│ 👤 주연   │ 송강호       │ TMDB 송강호/이선균..  │ ⚠ 충돌 → ②에서 선택   │
├──────────┴──────────────┴───────────────────────┴───────────────────────┤
│ 시놉시스 [현재]....  [TMDB]....  [AI 종합]....            [채택]         │
│ 🤖 AI 종합 — auto 5필드   [전체 자동 채택] [재생성] [무시]               │
│ ▸ 부가정보 (출연진 · 외부소스 원본 · AI 이력)                    접힘 ▼  │
└──────────────────────────────────────────────────────────────────────────┘
```

### 5.6 3단 레이어 검수 — 시리즈 (Container, 상속 원천)

```
┌ Sticky ─────────────────────────────────────────────────────────────────┐
│ ← 목록  오징어 게임 시즌2 📺 시리즈                  [✕ 반려] [✓ 승인]   │
├──────────────────────────────────────────────────────────────────────────┤
│ ⚠ 시리즈 메타 검수 — 승인 시 하위 3 시즌 · 17 에피소드에 상속 갱신       │
├──────────┬──────────────┬───────────────────────┬───────────────────────┤
│ 🎭 장르   │ 드라마       │ TMDB(tv) 드라마/스릴러│ 드라마·스릴러 0.91[채택]│
│ 📅 연도   │ 2024 ✓       │ TMDB(tv) 2024         │ 2024 ✓                │
│ 📝 시놉시스│ ...          │ TMDB(tv) ...          │ AI 종합 [채택]        │
│ 🖼 포스터 │ [현재]       │ TMDB(tv) 후보 4건     │ [후보에서 선택]       │
├──────────┴──────────────┴───────────────────────┴───────────────────────┤
│ 🤖 [전체 자동 채택]   ⚠ 승인 시 하위 20개 노드 상속 필드 자동 갱신      │
└──────────────────────────────────────────────────────────────────────────┘
```

### 5.7 3단 레이어 검수 — 에피소드 (Leaf, 상속 수신)

```
┌ Sticky ─────────────────────────────────────────────────────────────────┐
│ ← 시즌  오징어게임S2 › 시즌1 › EP01  🎞 에피소드      [✕] [✓]           │
├──────────────────────────────────────────────────────────────────────────┤
│ ℹ 시리즈 "오징어 게임 시즌2" 메타 상속 중      [→ 시리즈 검수로 이동]   │
├──────────┬──────────────┬───────────────────────┬───────────────────────┤
│ 🎭 장르   │ 스릴러 🔒상속│ 🔒 시리즈에서 상속    │ (상속 — 검수 불가)    │
│ 📅 연도   │ 2021 🔒상속  │ 🔒 시리즈에서 상속    │ (상속)                │
│ 📝 제목   │ 무궁화 꽃..  │ TMDB(tv) S01E01       │ 무궁화 꽃이.. 0.90[채택]│
│  〔고유〕 │              │                       │                       │
│ ⏱ 런타임 │ — Missing    │ TMDB(tv) 62분         │ 62분 [채택]           │
│  〔고유〕 │              │                       │                       │
├──────────┴──────────────┴───────────────────────┴───────────────────────┤
│ 🔒 상속 (read-time D3, 검수 잠금) · 〔고유〕 = 에피소드 단위 검수 대상   │
└──────────────────────────────────────────────────────────────────────────┘
```

> **상속 분기**: 상속 필드는 ②③열 **🔒 잠금**, 빈 값도 "Missing" ≠ "상속" 명확
> 구분 (D3 정신: 복사 prefill 금지). 〔고유〕필드(제목·런타임·EP 시놉시스)만 활성.

### 5.8 Bulk Upload → 계층 추천 검수 큐

```
┌─ Bulk 추천 검수 큐 ───────────────────────────────────────────────────┐
│ Job #142 · series.csv · 6행 → 1 시리즈 / 2 시즌 / 3 에피소드           │
│ 필터 [전체6][검수대기4][상속2][충돌1]   정렬: 계층순 ▼                 │
├──┬───────────────────────────────┬────────┬──────────┬───────────────┤
│☐ │ 오징어 게임 시즌2             │📺시리즈│TMDB 0.92 │ 검수대기 ⚑    │
│☐ │  └ 시즌 1                     │📂시즌  │ 🔒상속   │ 상속 (자동)   │
│☐ │     └ EP01 재회               │🎞EP    │TMDB 0.88 │ 검수대기      │
│☐ │     └ EP02 456번              │🎞EP    │TMDB 0.85 │ 검수대기      │
│☐ │  └ 시즌 2                     │📂시즌  │ 🔒상속   │ 상속 (자동)   │
│☐ │     └ EP01 귀환               │🎞EP    │ — 미매칭 │ ⚠ 충돌        │
├──┴───────────────────────────────┴────────┴──────────┴───────────────┤
│ 권장: ① 시리즈 검수 → ② 에피소드 고유필드 → ③ 일괄 승인              │
│ [시리즈만 먼저 검수 →] [선택 일괄 승인] [전체 자동채택 후 검수]       │
└───────────────────────────────────────────────────────────────────────┘
   행 클릭 → §5.5(영화) / §5.6(시리즈) / §5.7(에피소드) 검수 화면 진입
```

> **Bulk 분기**: movie bulk = 평면 큐(인덴트 없음). series bulk = 계층 인덴트,
> 시즌 행 "상속(자동)" 검수 스킵 가능, 시리즈 우선 검수 동선 유도.

### 5.9 컴포넌트 재사용 매트릭스

| 컴포넌트 | 재사용/신규 | movie | series | season | episode |
|---|---|---|---|---|---|
| `ShortMetaGrid`(3열) | 재사용 | ✅전체 | ✅전체 | 🔒상속잠금 | 🔒+〔고유〕 |
| `DiffCell`/`RecomCell` | 재사용 | ✅ | ✅ | lock variant | lock variant |
| `StickyActionBar` | 재사용 | 그대로 | +영향경고 | +브레드크럼 | +브레드크럼 |
| `ExternalSourcePanel` | **신규** | 4소스 | tv 라우팅 | tv 라우팅 | tv 라우팅 |
| `InheritedLockCell` | **신규** | — | — | ✅ | ✅ |
| `SeriesImpactBanner` | **신규** | — | ✅ | — | — |
| `BulkReviewQueue` | **신규** | 평면 | 계층인덴트 | — | — |

### 5.10 API & 상태

```ts
// 외부소스 획득 — 기존 enrich 재사용
metadataApi.triggerEnrich(contentId)       // POST /contents/{id}/enrich
metadataApi.getRecommendations(contentId)  // RecommendationsOut (auto_fill/conflicts)

// 상속 표시 — Step 14 의 ContentDetail.inherited_meta / parent_id 활용
// tv-type 외부조회 라우팅: 백엔드가 이미 시리즈 조상 처리 (ADR D2, Phase A 완료)
// FE 는 external_lookup_target 결과를 "조회 단위" 라벨로 노출만
```

### 5.11 빈 / 로딩 / 에러 상태

| 시나리오 | 처리 |
|---|---|
| 외부소스 획득 진행 | 소스별 진행 배지 (✓/⏳/✗) |
| 획득 0건 매칭 | "외부 매칭 없음 — 수동 입력 권장" |
| 상속 필드 | 🔒 잠금 표시, "Missing" 표기 금지 |
| 시리즈 children 0 | 영향 경고 배너 숨김 |
| 추천 재생성 중 | RecomCell spinner |

### 5.12 금지사항

- **새 3단 레이아웃 발명 금지** — `ShortMetaGrid` 3열 재사용
- **상속 필드 복사 prefill 금지** (D3) — 🔒 잠금만, 값 복사 금지
- **tv-type 에 KMDB/KOBIS 조회 노출 금지** — ⊘ 비활성 (ADR D2)
- **새 URL 라우트 금지** — 기존 `/contents/{id}/recommend` 유지
- **시즌 노드 강제 검수 금지** — 상속 시즌은 "자동" 스킵 허용

### 5.13 Acceptance (Step 15)

```bash
bash .claude/verify.sh mh-fe-recommend
```
- movie → 4소스 외부획득 패널 + 3단 전체활성
- series/season/episode → tv 라우팅(KMDB/KOBIS ⊘) + 시리즈 조상 조회 라벨
- season/episode 상속필드 🔒 잠금 (Missing 표기 안 됨)
- 시리즈 검수 화면에 하위 영향 경고 배너
- Bulk series → 계층 인덴트 큐 / Bulk movie → 평면 큐
- typecheck pass · lint 에러 없음 · 기존 recommend 흐름 회귀 없음
