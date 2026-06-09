# Step 1.2: scheduling-migration

> GitHub: 미생성 | Milestone: dev-programming-link
> Status: pending

## 읽어야 할 파일
- plans/dev-programming-link/step1.md (모델 정의)
- backend/alembic/versions/0040_*.py, 0041_category_sets.py (최근 마이그레이션 패턴·ENUM 생성 참고)
- docs/dev/dev-programming-link/adr-011-02-migration.md

## 작업
신규 alembic revision (다음 번호) — **스키마만** 생성(데이터 이관은 1.3).

- PostgreSQL ENUM 4종 생성: node_kind / child_type / link_source / link_status
- 테이블 3종: `programming_node_sets`, `programming_nodes`, `programming_links`
- 제약: unique 2종 + check(child 정확히 하나) + 인덱스(step1.md 명세)
- downgrade: 테이블 drop + ENUM drop (역순)
- Docker PostgreSQL 에 `alembic upgrade head` 적용 확인

## 금지사항
- 구 테이블을 건드리지 마라(drop/alter 금지) — 공존 단계.
- ENUM 이름 충돌 주의: 기존 quality_enum/purchase_type_enum 과 겹치지 않게.

## Acceptance Criteria
```bash
bash .claude/verify.sh scheduling-migration
# (upgrade/downgrade 왕복 + 3테이블·4ENUM·제약 존재 확인)
```
