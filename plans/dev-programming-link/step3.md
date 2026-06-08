# Step 1.3: data-migration

> GitHub: 미생성 | Milestone: dev-programming-link
> Status: pending

## 읽어야 할 파일
- docs/dev/dev-programming-link/adr-011-02-migration.md (매핑 표·검증 게이트 SSOT)
- backend/api/programming/catalog/models.py, backend/api/distribution/models.py

## 작업
구→신 데이터 이관 스크립트 `backend/scripts/migrate_programming_links.py` (멱등, 2-pass).

- pass 1: `category_sets→node_sets`, `categories→nodes(container)`,
  `service_categories→nodes(rank|manual)`. 메모리 매핑 `legacy_kind:id → new_node_id`.
- pass 2 (링크): `categories.parent_id→links(node)`, `content_categories→links(content)`,
  `service_category_items→links(content, rank→sort_order, score→confidence)`.
- `external_curations`/`_items`: 이관 안 함(참조 소스로 존치).
- 멱등성: slug/원본 id 기반 upsert, 재실행 시 중복 생성 0.

검증 게이트(스크립트 종료 시 출력 + 테스트):
```
node_sets==category_sets / nodes(container)==categories /
links(node)==categories(parent_id≠null) / links(content,cat)==content_categories /
nodes(rank|manual)==service_categories / links(content,item)==service_category_items /
사이클 0 / CHECK 위반 0
```

## 금지사항
- 구 테이블 삭제 금지(5.3 에서). 여기선 읽기만 + 신규 insert.
- 작품 계층(contents.parent_id) 이관 금지 — 변경 없음.

## Acceptance Criteria
```bash
bash .claude/verify.sh data-migration
# (이관 스크립트 실행 + 검증 게이트 8항목 통과 + 재실행 멱등)
```
