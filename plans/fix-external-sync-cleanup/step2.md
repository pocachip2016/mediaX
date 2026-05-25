# Step 2: esc-celery-config — Celery Worker Redis 재연결 강화

> GitHub: 미생성 | Milestone: fix-external-sync-cleanup

## 읽어야 할 파일
- backend/workers/celery_app.py

## 작업
`celery_app.conf.update(...)` 블록에 3개 옵션 추가:

```python
broker_connection_retry_on_startup=True,
broker_transport_options={
    "visibility_timeout": 7200,   # 2h — 긴 백필 작업이 재할당되지 않도록
    "socket_keepalive": True,
    "retry_on_timeout": True,
    "max_connections": 50,
},
result_backend_transport_options={
    "visibility_timeout": 7200,
    "retry_on_timeout": True,
},
```

추가 이유:
- `broker_connection_retry_on_startup=True` — Celery 6.0 deprecation 경고 해소 + 시작 시 Redis 미응답 대비
- `visibility_timeout=7200` — backfill_movies가 90s+ 걸리는데 기본 1h 후 재할당 위험 → 2h로 여유
- `retry_on_timeout=True` — master/replica flip 시 자동 재시도

**적용 후 worker + beat 재시작 필요** (`docker compose restart worker beat`).

## Acceptance Criteria
```bash
docker compose restart worker beat
sleep 10
docker logs mediax-worker-1 --since 1m 2>&1 | grep -E "ready|connected|error" | tail -5
# "ready" 로그 + error 없어야 함

docker logs mediax-beat-1 --since 1m 2>&1 | grep -E "Acquired lock|error" | tail -5
# "Acquired lock" 로그 + error 없어야 함

docker exec mediax-worker-1 python -c "from workers.celery_app import celery_app; \
  assert celery_app.conf.broker_connection_retry_on_startup is True; \
  assert celery_app.conf.broker_transport_options.get('visibility_timeout') == 7200; \
  print('OK')"
```

## 금지사항
- 기존 옵션 변경 금지 (timezone, beat_scheduler, beat_schedule 등)
- 새 task/queue 추가 금지
- Redis 호스트 변경 금지
