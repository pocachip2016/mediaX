# Step 3: esc-startup-hook — Worker 시작 시 Stale running 자동 cleanup

> GitHub: 미생성 | Milestone: fix-external-sync-cleanup

## 읽어야 할 파일
- backend/workers/celery_app.py
- backend/workers/tasks/metadata.py (signal import 패턴 참고)

## 작업
celery_app.py 끝에 `worker_ready` signal handler 추가:

```python
from celery.signals import worker_ready

@worker_ready.connect
def cleanup_stale_sync_logs(sender=None, **kwargs):
    """
    Worker 시작 시 1시간 이상 running 상태로 남아있는 external_sync_log를 failed로 마킹.
    Worker 크래시/Redis flip 후 잔류한 레코드 자동 정리.
    """
    import logging
    from datetime import datetime, timedelta, timezone
    from shared.database import SessionLocal
    from api.programming.metadata.models import TmdbSyncLog, TmdbSyncStatus

    logger = logging.getLogger(__name__)
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        stale = db.query(TmdbSyncLog).filter(
            TmdbSyncLog.status == TmdbSyncStatus.running,
            TmdbSyncLog.started_at < cutoff,
        ).all()
        for row in stale:
            row.status = TmdbSyncStatus.failed
            row.finished_at = datetime.now(timezone.utc)
            row.error_sample = ["auto-cleanup on worker_ready: stale > 1h"]
        if stale:
            db.commit()
            logger.warning(f"[startup_cleanup] {len(stale)} stale sync_log → failed")
        else:
            logger.info("[startup_cleanup] no stale sync_log")
    except Exception as exc:
        logger.error(f"[startup_cleanup] failed: {exc}")
        db.rollback()
    finally:
        db.close()
```

핵심 불변 규칙:
- **1시간 cutoff** — 실제 long-running backfill (TMDB year 백필 90s+) 보호. 너무 짧으면 정상 task를 죽임.
- **except 광범위 catch** — 시작 hook 실패가 worker startup을 막으면 안 됨.
- **import 함수 내부에서** — circular import 회피.
- error_sample은 `jsonb` 컬럼이므로 list/dict 형태로 저장.

## Acceptance Criteria
```bash
# 1. stale 레코드 1개를 인위적으로 만든다
docker exec mediax-postgres-1 psql -U media_ax -d media_ax -c \
  "INSERT INTO external_sync_log (run_id, source, status, started_at) \
   VALUES ('test-cleanup', 'changes_movie', 'running', NOW() - INTERVAL '2 hours') RETURNING id;"

# 2. worker 재시작 → hook 동작
docker compose restart worker
sleep 15

# 3. cleanup 로그 확인 + DB 상태 확인
docker logs mediax-worker-1 --since 30s 2>&1 | grep startup_cleanup
# "1 stale sync_log → failed" 포함

docker exec mediax-postgres-1 psql -U media_ax -d media_ax -c \
  "SELECT status, finished_at IS NOT NULL AS has_finished FROM external_sync_log WHERE run_id='test-cleanup';"
# status=failed, has_finished=t

# 4. 테스트 레코드 정리
docker exec mediax-postgres-1 psql -U media_ax -d media_ax -c \
  "DELETE FROM external_sync_log WHERE run_id='test-cleanup';"
```

## 금지사항
- `kombu`/`celery` 내부 잠금 메커니즘 건드리지 말 것
- DELETE 사용 금지 — 감사 기록 보존
- cutoff 1h를 줄이지 말 것 — long-running backfill 보호
- beat에는 hook 추가 금지 — worker만 (beat은 task 실행 안 함)
