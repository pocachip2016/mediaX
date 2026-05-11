# Step 1: quota-manager

> GitHub: 미생성 | Milestone: quota-and-cache-adr

## 읽어야 할 파일
- `mediaX/docs/dev/quota-cache-adr.md` (Step 0 산출물 — KST TTL · fail-open · key 형식 확정)
- `mediaX/backend/shared/` 디렉토리 리스트 (기존 Redis 연결 패턴 확인)
- `mediaX/backend/workers/tasks/metadata.py` L31–48 (기존 `_kobis_rate_allowed` 패턴 참고)
- `mediaX/backend/requirements.txt` (fakeredis 가용 여부 확인)

## 작업

1. **`mediaX/backend/shared/quota_manager.py` 신규**

   인터페이스:
   ```python
   class QuotaManager:
       def is_allowed(self, api: str, daily_limit: int) -> bool: ...
       def current_count(self, api: str) -> int: ...
   ```

   구현 요건 (디테일은 에이전트 재량):
   - Redis 연결 재사용 (모듈 레벨 또는 인스턴스 보관)
   - `INCR` + `EXPIRE` 원자성 (Lua script 또는 매 호출 EXPIRE 재설정)
   - TTL anchor: 다음 KST 자정 + 1h 여유 (KST = UTC+9)
   - Key 형식: `{api}:daily:{YYYYMMDD_KST}`
   - Redis 실패 시 `True` 반환 + `logger.warning` (fail-open)

2. **`mediaX/backend/tests/shared/test_quota_manager.py` 신규**

   `fakeredis` 또는 `unittest.mock`. 최소 3 케이스:
   - limit 미만 → True
   - limit 초과 → False
   - Redis 장애 → True (fail-open)

3. **`mediaX/.claude/verify.sh` 케이스 `quota-adr-step1` 추가**:
   ```bash
   python3 -c "from shared.quota_manager import QuotaManager; QuotaManager().is_allowed; print('  ✓ import OK')"
   python3 -m pytest tests/shared/test_quota_manager.py -q
   ```

## Acceptance Criteria

```bash
bash .claude/verify.sh quota-adr-step1
```

## 금지사항
- `from_url()` 을 매 호출마다 만들지 마라. 이유: 커넥션 풀 낭비 — KOBIS 기존 버그 재현 시 Step 2 무의미
- 비동기로 만들지 마라. 이유: KOBIS/KMDB sync 호출 스택 — async 전환은 scope 외
- TTL 을 `90000` 같은 magic number 로 박지 마라. 이유: UTC anchor 버그 재현 — `datetime` 으로 KST 자정 계산
