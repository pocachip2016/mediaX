# Step 3: kmdb-rate-limit

> GitHub: 미생성 | Milestone: quota-and-cache-adr

## 읽어야 할 파일
- `mediaX/backend/api/meta_core/clients/kmdb_client.py` (전체, 104줄)
- `mediaX/backend/api/meta_core/clients/kobis_client.py` (sleep 패턴 참고)
- `mediaX/backend/shared/quota_manager.py` (Step 1 산출물)
- `mediaX/docs/dev/quota-cache-adr.md` (KMDB daily limit = 500, req/sec = 1 확인)

## 작업

1. `KmdbClient` 에 1 req/sec 스로틀 (KOBIS 동일 패턴):
   - 클래스 변수 `_MIN_INTERVAL = 1.0`, 인스턴스 변수 `_last_call: float = 0.0`
   - `fetch()` 진입 시 `time.monotonic()` 기준 sleep 보정

2. `QuotaManager.is_allowed("kmdb", 500)` 호출 추가:
   - 위치: `fetch()` 진입부, sleep 보정 직전
   - quota 초과 시 신규 예외 `KmdbDailyLimitExceeded` raise (`KmdbApiKeyMissing` 옆 정의)
   - `iter_collection()` 은 `fetch()` 를 통해 자동 보호됨

3. **`mediaX/.claude/verify.sh` 케이스 `quota-adr-step3` 추가**:
   - `KmdbClient` 소스에 `_MIN_INTERVAL` 존재
   - `KmdbClient` 소스에 `QuotaManager`/`is_allowed` 존재
   - `KmdbDailyLimitExceeded` import 가능

## Acceptance Criteria

```bash
bash .claude/verify.sh quota-adr-step3
```

## 금지사항
- async 로 전환하지 마라. 이유: Celery task 전체 sync — 전환 범위 scope 외
- `iter_collection` 의 페이지네이션 로직을 변경하지 마라. 이유: 퇴행 위험 · surgical changes
- `KmdbDailyLimitExceeded` 호출부 처리를 이 step 에서 추가하지 마라. 이유: 예외 정의만 — 핸들링은 caller 책임 (별도 step)
