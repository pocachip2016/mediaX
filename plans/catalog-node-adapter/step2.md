# Step 2: write-path-adapter — CRUD 함수 전환

## 목표
`backend/api/programming/catalog/service.py` 및 `router.py`의 **쓰기 경로** 함수를 모두 `ProgrammingNode/Link` DAG 기반으로 전환.

## 쓰기 경로 함수 목록 (9개)

### 현황
| 함수 | 상태 | 변환 내용 |
|------|------|---------|
| `create_category` | ✅ 완료 | node 생성 + 부모 링크 추가 |
| `bulk_create_categories` | 🔜 | 대량 생성 + 중복 정책 → link 생성으로 통일 |
| `rename_category` | 🔜 | node.name 변경 |
| `set_active` | 🔜 | node.is_active 토글 |
| `move_category` | 🔜 | 부모 링크 재설정(link 삭제 후 재생성) |
| `merge_category` | 🔜 | 소스 child 링크 → 타겟 부모로 재지정 + 소스 노드 삭제 |
| `delete_category` | 🔜 | 노드 + 관련 링크 모두 삭제 |
| `map_content` | 🔜 | content_categories → ProgrammingLink(child_type=content) 생성 |
| `unmap_content` | 🔜 | content 링크 삭제 |

## 구현 전략

### Phase 2a: 단순 쓰기 함수 (rename, set_active)
- `rename_category`: node.name ← 요청 name
- `set_active`: node.is_active ← 요청 bool
- 테스트: 각각 1~2개 단위 테스트

### Phase 2b: 위치 변경 함수 (move, merge)
- `move_category`: 기존 incoming_link 삭제 → 새 link 생성
- `merge_category`: 소스 children 링크 → 타겟 parent로 재설정
- 복잡도: 고아 노드 방지, sort_order 재정렬
- 테스트: 각 3~4개 케이스

### Phase 2c: 대량 쓰기 (bulk_create)
- `bulk_create_categories`: 기존 로직 재구성 (중복 정책 유지)
- content_categories 테이블 제거는 아직 (legacy-drop phase에서)
- 테스트: 5~6개 케이스 (dup_policy: overwrite/reject/skip)

### Phase 2d: content 매핑 (map/unmap)
- `map_content`: ContentCategory → ProgrammingLink(child_type=content)
- `unmap_content`: content 링크 삭제
- ContentCategory 테이블 아직 유지 (Step 5에서 제거)
- 테스트: 3~4개 케이스

## 예상 변경 파일
- `backend/api/programming/catalog/service.py` — 함수 리팩터
- `backend/tests/test_catalog_node_adapter.py` — 테스트 추가 (20~30개)
- `.claude/verify.sh` — s2 체크 추가

## 성공 기준
- 모든 쓰기 함수가 ProgrammingNode/Link만 사용 (ContentCategory 레거시 쿼리 제거)
- 회귀 없음: 기존 테스트 37개 통과 + 신규 테스트 20+ 통과
- verify.sh `catalog-node-adapter-s2` 스크립트 통과

## 참고
- read-path 헬퍼: `_get_node_depth`, `_max_sibling_sort`, `_incoming_link`  재사용
- 기존 `_cat_view`는 그대로 유지 (API 응답 호환성)
- sort_order: move/merge 시 재정렬 로직 필요 (depth 또는 부모별)
