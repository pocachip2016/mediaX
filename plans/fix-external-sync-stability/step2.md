# Step 2: fess-beat-stability (Phase B)

> Milestone: fix-external-sync-stability

## 읽어야 할 파일
- `backend/workers/celery_app.py`
- `docker-compose.yml` (beat 서비스 정의)

## 작업
redbeat LockNotOwnedError 발생 빈도를 낮춰 Beat 재시작을 방지.

산출:
- `backend/workers/celery_app.py`
  - `redbeat_lock_timeout`: 600 (10분) → 1800 (30분) — WSL2 sleep tolerance
  - `beat_max_loop_interval`: 60 → 30 (락 갱신 빈도 ↑)
- `docker-compose.yml` (선택)
  - `beat` 서비스 `restart: unless-stopped` 확인
  - healthcheck 추가는 follow-up (이번 step 범위 외)

## 검증
- 컨테이너 재기동 → 30분 이상 관찰 → `docker logs mediax-beat-1 --since 30m | grep -i lock` 결과 없음
- `docker inspect mediax-beat-1 --format '{{.RestartCount}}'` 값 freeze 확인

## Acceptance Criteria
```bash
/verify fess-beat-stability
```

## 금지사항
- 단순 lock_timeout 만 늘려 무한 대기 만들지 마라. 이유: stale lock 으로 다른 인스턴스가 절대 차지하지 못함. loop_interval 도 함께 줄여 갱신 빈도 확보.
- redbeat 외 다른 scheduler 로 교체 마라. 별도 ADR 필요.
