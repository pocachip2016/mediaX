# ADR-011-01: 도메인 모델 — 3축 분리 + Node/Link DAG

> 부모: [adr-011-programming-link_index.md](adr-011-programming-link_index.md)

## 3개의 직교 축

편성의 복잡함은 성격이 다른 3축을 섞을 때 발생한다. 분리해서 모델링한다.

| 축 | 의미 | 저장소 | 구조 | 변경 |
|----|------|--------|------|------|
| **A. 작품 계층** | series⊃season⊃episode (소유) | `contents.parent_id` | 트리(단일부모) | **유지** |
| **B. 분류** | 장르·국가·연령·메타 (사실) | `programming_nodes(kind=rule)` 의 `rule_query` | 규칙 도출 | 신규 흡수 |
| **C. 편성·노출** | 홈 진열·특집·TOP10 (운영) | `programming_nodes` + `programming_links` | **DAG** | 신규 |

축 A는 read-time 상속(`meta-hierarchy` 패턴)으로 활용: 시즌 1개 링크 → 하위 에피소드 자동 포함.

## 테이블 1 — `programming_node_sets` (편성안 버전)

기존 `category_sets` 개념 계승. 편성안 단위 draft → published.

| 컬럼 | 타입 | 비고 |
|------|------|------|
| id | PK | |
| name | str(200) | "2026 여름 편성" |
| description | str(1000) | nullable |
| status | str(20) | `draft` \| `published` (default draft) |
| published_at | datetime | nullable |
| created_at / updated_at | datetime | |

## 테이블 2 — `programming_nodes` (편성 노드)

| 컬럼 | 타입 | 비고 |
|------|------|------|
| id | PK | |
| set_id | FK node_sets | nullable = 작업 디렉토리(draft) |
| kind | enum | `container` \| `rule` \| `rank` \| `manual` |
| name | str(200) | |
| slug | str(220) | nullable |
| headline_copy | str(200) | 큐레이션 문구 (구 ServiceCategory) |
| sub_copy | str(300) | nullable |
| theme_features | JSON | 무드/테마 시드 (Tier 2 벡터 입력) |
| rule_query | JSON | `kind=rule`: `{genre, year_gte, country, tags…}` |
| rank_source | str(50) | `kind=rank`: `popularity` \| `recency` \| 혼합 |
| rank_limit | int | `kind=rank`: 상위 N (예: 10) |
| window_start / window_end | date | 노드 기본 노출기간(시즌널), nullable |
| is_active | bool | default true |
| is_draft | bool | default false |
| created_at / updated_at | datetime | |

노드 kind 의미:
- **container**: 단순 진열대(홈 1행처럼 다른 노드/콘텐츠를 담는 묶음)
- **rule**: 자동 카테고리 — `rule_query` 로 멤버 read-time 산출(Tier 0)
- **rank**: TOP10류 — `rank_source`/`rank_limit` 로 정렬·상위 N
- **manual**: 운영자 수동 특집 — 링크를 직접 건다

## 테이블 3 — `programming_links` (배치 엣지 = DAG 간선)

노드의 자식(콘텐츠 또는 다른 노드)을 가리키는 다형성 엣지. **여기에 다중소속·중첩·배치별 기간/문구가 표현됨.**

| 컬럼 | 타입 | 비고 |
|------|------|------|
| id | PK | |
| parent_node_id | FK nodes | 이 배치가 속한 부모 노드 |
| child_type | enum | `node` \| `content` |
| child_node_id | FK nodes | nullable (child_type=node) |
| child_content_id | FK contents | nullable (child_type=content) |
| sort_order | int | 진열 순서 (구 rank/sort_order 통합) |
| is_pinned | bool | 고정(상단 유지), default false |
| window_start / window_end | date | **이 배치만의** 노출기간 override, nullable |
| copy_override | JSON | 이 위치에서만의 문구, nullable |
| source | enum | `manual` \| `ai` \| `rule` |
| confidence | float | nullable (source=ai) |
| status | enum | `active` \| `suggested` \| `rejected` (default active; ai 추천은 suggested) |
| created_at | datetime | |

제약:
- `UNIQUE(parent_node_id, child_node_id)` / `UNIQUE(parent_node_id, child_content_id)`
- `CHECK`: child_node_id / child_content_id 중 **정확히 하나**만 NOT NULL
- **사이클 가드**: child_type=node 링크 추가 시 부모 조상 체인에 자신 포함되면 거부(앱 레벨 검증; 선택적 closure table)

## 멤버 산출 (read-time)

노드의 최종 노출 멤버 = **rule 산출(Tier 0) ∪ active 링크(manual/ai-confirmed)**, status=suggested/rejected 제외.
중복은 `child_content_id` 기준 dedupe, `is_pinned` 우선 후 `sort_order`.

## 핵심 불변 규칙

1. 작품 계층(`contents.parent_id`)은 DAG에 넣지 않는다 — 소유 관계.
2. 노드 삭제 ≠ 콘텐츠/하위노드 삭제. 링크만 끊는다.
3. AI/rule 자동 멤버와 manual 멤버는 `source`로 구분 저장, read-time 병합.
4. 배치 기간 ⊆ 노드 기간 (권장 검증, 위반 시 경고).
