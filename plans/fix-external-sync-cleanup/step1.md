# Step 1: esc-db-cleanup — Stale sync_log 레코드 정리

> GitHub: 미생성 | Milestone: fix-external-sync-cleanup

## 읽어야 할 파일
- plans/fix-external-sync-cleanup/step0.md
- backend/alembic/versions/0006_external_sync_log.py

## 작업
6건의 stale 레코드를 정리한다. **삭제 아님 — UPDATE로 status/finished_at/error_sample 기록 유지**.

대상:
- id=74, 77 (running 9일+) → status='failed', finished_at=NOW(), error_sample 추가
- id=99 (이미 failed지만 finished_at은 채워져 있음) → 그대로 둠
- id=102, 103 (failed, finished_at=NULL) → finished_at=NOW() 채우기
- id=135 (failed, finished_at은 채워져 있음) → 그대로 둠

방법: `docker exec mediax-postgres-1 psql -U media_ax -d media_ax -c "<SQL>"` 1회 실행.

SQL:
```sql
UPDATE external_sync_log
SET status = 'failed',
    finished_at = NOW(),
    error_sample = COALESCE(error_sample, '"stale cleanup 2026-05-25 — 9일+ running"'::jsonb)
WHERE id IN (74, 77);

UPDATE external_sync_log
SET finished_at = NOW()
WHERE id IN (102, 103) AND finished_at IS NULL;
```

## Acceptance Criteria
```bash
docker exec mediax-postgres-1 psql -U media_ax -d media_ax -c \
  "SELECT COUNT(*) FROM external_sync_log WHERE status='running';"
# 결과: 0

docker exec mediax-postgres-1 psql -U media_ax -d media_ax -c \
  "SELECT COUNT(*) FROM external_sync_log WHERE finished_at IS NULL;"
# 결과: 0
```

## 금지사항
- DELETE 사용 금지 (감사 기록 보존)
- 상태가 completed인 레코드 변경 금지
- alembic migration 작성 금지 (DML only, schema 변경 없음)
