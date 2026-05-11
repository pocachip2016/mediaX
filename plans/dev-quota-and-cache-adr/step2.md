# Step 2: kobis-migration

> GitHub: 미생성 | Milestone: quota-and-cache-adr

## 읽어야 할 파일
- `mediaX/backend/workers/tasks/metadata.py` L1–60 (`_KOBIS_DAILY_LIMIT` · `_kobis_rate_allowed`)
- `mediaX/backend/shared/quota_manager.py` (Step 1 산출물)
- `mediaX/docs/dev/quota-cache-adr.md` (KOBIS daily limit = 2900 확인)

## 작업

1. `metadata.py` 의 `_kobis_rate_allowed()` 본체 교체:
   ```python
   _quota = QuotaManager()  # 모듈 레벨

   def _kobis_rate_allowed() -> bool:
       return _quota.is_allowed("kobis", 2900)
   ```
   - **함수 시그니처 유지** (호출부 L259/L793/L981 변경 없음)
   - `_KOBIS_DAILY_LIMIT = 2900` 상수 제거 (인라인)
   - `datetime.utcnow()` · `r.incr` · `r.expire` 직접 호출 제거

2. import 추가: `from shared.quota_manager import QuotaManager`

3. **`mediaX/.claude/verify.sh` 케이스 `quota-adr-step2` 추가** (AST 기반 검증):
   - `_kobis_rate_allowed` 함수 본체에 `QuotaManager`/`is_allowed` 호출 존재
   - 함수 본체에 `utcnow` · `r.incr` 부재

## Acceptance Criteria

```bash
bash .claude/verify.sh quota-adr-step2
```

## 금지사항
- `_kobis_rate_allowed` 함수 자체를 삭제하지 마라. 이유: 호출부 3곳(L259/L793/L981) 동시 수정은 회귀 위험 — 본 step scope 외
- `_KOBIS_DAILY_LIMIT` 외 다른 상수를 손대지 마라. 이유: surgical changes — 무관한 정리는 별도 PR
