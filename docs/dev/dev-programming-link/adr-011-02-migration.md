# ADR-011-02: 마이그레이션 전략 — 통합 이관 + 레거시 제거

> 부모: [adr-011-programming-link_index.md](adr-011-programming-link_index.md)

## 원칙

위험을 단계로 나눈다: **신규 테이블 생성 → 데이터 복사(idempotent) → 검증 → FE/API 전환 → 레거시 제거.**
복사 단계에서 구 테이블은 read-only로 살려두고, 전환 완료(Phase 5) 후 drop.

## 매핑 표

| 구(SOURCE) | 신(TARGET) | 변환 규칙 |
|-----------|-----------|----------|
| `category_sets` | `programming_node_sets` | name/description 복사, status=draft |
| `categories` | `programming_nodes` (kind=`container`) | name/slug/sort_order/is_active 복사. `parent_id` → **링크로 분리**(아래) |
| `categories.parent_id` | `programming_links` (child_type=node) | parent=상위 카테고리 노드, child=하위 카테고리 노드, sort_order 보존, source=manual |
| `content_categories` | `programming_links` (child_type=content) | parent=카테고리 노드, child=content. `is_primary`→`is_pinned`, sort_order 보존, source=manual |
| `service_categories` | `programming_nodes` | category_type 이 top/rank류면 kind=`rank`, 아니면 kind=`manual`. headline_copy/sub_copy/theme_features/is_draft 복사 |
| `service_category_items` | `programming_links` (child_type=content) | parent=service 노드, child=content, `rank`→sort_order, `score`→confidence(없으면 null), source=manual |
| `external_curations` / `_items` | **이관 안 함** | 외부 OTT 미러(참조). Tier 5 RAG 후보 소스로 그대로 유지 |
| `contents.parent_id` | **변경 없음** | 작품 계층 유지 |

ID 매핑: 변환 스크립트는 `legacy_kind:legacy_id → new_node_id` 매핑 테이블을 메모리에 두고
2-pass(노드 생성 → 링크 생성)로 처리. 멱등성 위해 `slug`/원본 id 기반 upsert.

## 충돌·엣지 케이스

- **카테고리가 콘텐츠+하위카테고리 동시 보유**: 신모델은 자연 지원(같은 부모에 child_type 혼합 링크).
- **다중 부모 부재(구 데이터)**: 구 카테고리는 단일부모였으므로 1:1 링크. 다중소속은 신규 운영에서 추가.
- **service_categories.platform**: 노드 속성으로 직접 컬럼 안 둠 — 필요 시 `theme_features.platform` 또는 별도 노출 채널 매핑(후속). 1차는 theme_features에 보존.
- **사이클**: 구 데이터는 트리라 사이클 없음. 변환 후 가드 활성.

## 검증 (마이그레이션 게이트)

```text
- node_sets 행수 == category_sets 행수
- nodes(container) 행수 == categories 행수
- links(node) 행수 == categories WHERE parent_id NOT NULL 행수
- links(content, from content_categories) 행수 == content_categories 행수
- nodes(rank|manual) 행수 == service_categories 행수
- links(content, from items) 행수 == service_category_items 행수
- 사이클 0건, CHECK 위반 0건
```

## 레거시 제거 (Phase 5 종료 시)

FE/API가 신규 모델만 사용함을 확인 후:
- `categories`, `content_categories`, `category_sets`, `service_categories`, `service_category_items` drop.
- 관련 service/router/schemas 코드 제거. 회귀 테스트로 잔존 참조 0 확인.
- `external_curations`/`_items` 는 존치(참조 소스).
