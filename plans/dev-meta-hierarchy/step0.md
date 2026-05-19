# Step 0: mh-audit-adr (Phase A)

> GitHub: 미생성 | Milestone: dev-meta-hierarchy

## 읽어야 할 파일
- backend/api/programming/metadata/models/content.py
- backend/api/meta_core/enrich.py
- backend/api/meta_core/gap.py
- backend/api/programming/metadata/service.py
- backend/workers/tasks/metadata.py
- backend/scripts/dedup_contents.py

## 작업
현재 movie/series/season/episode meta 처리 불일치(A~F) + write 경로 무결성
위험(R1~R6)을 감사하고, 목표 모델·결정(D1~D10)을 ADR 로 정리.
산출: `docs/dev/meta-hierarchy/adr-001-content-kind-routing.md`,
`plans/dev-meta-hierarchy/index.json`, `plans/dev-meta-hierarchy/step0.md`.

## Acceptance Criteria
```bash
bash .claude/verify.sh mh-audit-adr   # 또는 /verify --skip "doc-only ADR"
```

## 금지사항
- 코드 수정하지 마라. 이유: Step 0 은 분석/문서 전용. 구현은 Step 1+.
