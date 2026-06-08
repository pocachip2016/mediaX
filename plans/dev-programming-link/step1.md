# Step 1.1: scheduling-models

> GitHub: 미생성 | Milestone: dev-programming-link
> Status: pending

## 읽어야 할 파일
- docs/dev/dev-programming-link/adr-011-01-domain-model.md (테이블 정의 SSOT)
- backend/api/programming/catalog/models.py (구 모델 — 컬럼 계승 참고)
- backend/api/distribution/models.py (ServiceCategory — copy/theme 계승 참고)
- backend/shared/database.py (Base)

## 작업
신규 모듈 `backend/api/programming/scheduling/models.py` 에 3모델 + 4 enum 정의.

- enum: `NodeKind(container|rule|rank|manual)`, `ChildType(node|content)`,
  `LinkSource(manual|ai|rule)`, `LinkStatus(active|suggested|rejected)`
- `ProgrammingNodeSet`: id, name, description, status(draft|published), published_at, ts
- `ProgrammingNode`: id, set_id(FK,null), kind, name, slug, headline_copy, sub_copy,
  theme_features(JSON), rule_query(JSON), rank_source, rank_limit,
  window_start/end(Date), is_active, is_draft, ts
- `ProgrammingLink`: id, parent_node_id(FK), child_type, child_node_id(FK,null),
  child_content_id(FK contents,null), sort_order, is_pinned,
  window_start/end(Date,null), copy_override(JSON,null),
  source, confidence(Float,null), status, created_at

제약(모델 `__table_args__`):
- `UNIQUE(parent_node_id, child_node_id)`, `UNIQUE(parent_node_id, child_content_id)`
- `CHECK`: child_node_id IS NULL ≠ child_content_id IS NULL (정확히 하나)
- 인덱스: parent_node_id, child_content_id, (parent_node_id, sort_order)

`alembic/env.py` 에 신규 모델 import 추가(테이블 자동 인식용).
**이 step 은 모델 정의만** — 마이그레이션(1.2)·서비스(2.x)는 다음 step.

## 금지사항
- module/package 섀도잉 금지: `scheduling/models.py` 파일과 `scheduling/models/` 패키지 공존 금지.
- 구 모델 파일을 수정·삭제하지 마라(레거시 제거는 5.3). 여기선 신규 추가만.

## Acceptance Criteria
```bash
bash .claude/verify.sh scheduling-models
# (모델 import 성공 + Base.metadata 에 3테이블 등록 + enum 4종 존재 검증)
```
