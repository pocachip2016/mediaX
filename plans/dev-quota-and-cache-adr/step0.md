# Step 0: adr-doc-and-plan-init

> GitHub: 미생성 | Milestone: quota-and-cache-adr

## 읽어야 할 파일
- `mediaX/docs/dev/phase-c/ops-cost.md` (기존 quota 설계)
- `mediaX/backend/workers/tasks/metadata.py` (L31–48 `_kobis_rate_allowed`)
- `mediaX/backend/api/meta_core/clients/kmdb_client.py` (전체)
- `mediaX/plans/dev-tmdb-cache/index.json` (캐시 결정 컨텍스트)

## 작업

1. **플랜 파일 초기화** — `mediaX/plans/dev-quota-and-cache-adr/`
   - `index.json` — 4 steps (0–3), 전부 `status: "pending"`
   - `step0.md` ~ `step3.md` — 각 step 자기완결 형식

2. **ADR 문서 작성** — `mediaX/docs/dev/quota-cache-adr.md`
   - Status (Accepted, 2026-05-11)
   - Context (분산 현황 표 + 4가지 문제점)
   - Decision (QuotaManager 유틸 · KST anchor · fail-open · 모듈 싱글톤)
   - API별 정책 표 (TMDB/KOBIS/KMDB/OMDb 확정값)
   - Alternatives Considered (in-process / DB / 외부 서비스 — 각 기각 사유)
   - Cache 전략 (TMDB SQL · WebSearchCache 패턴 · KOBIS/KMDB 미적용 이유)
   - Consequences (Positive/Negative)
   - Follow-up (OMDb 후속)

## Acceptance Criteria

```bash
# 문서/플랜 init 전용 — verify.sh 케이스 없음
# /verify --skip "ADR 문서 + plan 디렉토리 초기화만, 코드 변경 없음"
```

## 금지사항
- ADR 문서에 미확정 값(TBD/예정) 남기지 마라. 이유: 후속 step 의 의사결정 의존, 명확히 채우거나 Out-of-scope 표기
- 코드 파일 일체 손대지 마라. 이유: 본 step 은 문서 전용 — 구현은 Step 1 이후
