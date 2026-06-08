# Step 0.1: adr-011-programming-link (설계 확정)

> GitHub: 미생성 | Milestone: dev-programming-link
> Status: completed (doc-only)

## 산출물
- `docs/dev/dev-programming-link/adr-011-programming-link_index.md`
- `docs/dev/dev-programming-link/adr-011-01-domain-model.md`
- `docs/dev/dev-programming-link/adr-011-02-migration.md`
- `docs/dev/dev-programming-link/adr-011-03-ai-autolink.md`
- `docs/dev/dev-programming-link/adr-011-04-gui.md`

## 결정 요약
- **통합(A)**: 구 catalog/큐레이션 2체계 → 단일 편성 DAG(Node+Link). 기존 화면·API 전환 포함.
- 작품 계층(`contents.parent_id`)은 유지(소유 관계).
- AI 자동링크 1차 범위 = Tier 0(규칙) + 1(LLM 의도) + 2(임베딩 kNN). 사람이 확정.

## Acceptance Criteria
문서 5종 존재 + ADR 분할 규칙(각 파일 200줄 이내) 준수. 코드 없음 → `/verify --skip "ADR 문서 작성"`.

## 금지사항
- 작품 계층을 DAG에 편입하지 마라. 이유: series/season/episode 는 소유 관계.
