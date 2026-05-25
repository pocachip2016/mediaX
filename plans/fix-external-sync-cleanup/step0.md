# Step 0: esc-plan — 진단 결과 + 3-step skeleton

> GitHub: 미생성 | Milestone: fix-external-sync-cleanup

## 진단 결과 요약 (2026-05-25 22:30 KST 기준)

### ✅ 정상 동작
- Beat 스케줄 14개 모두 등록됨, 매일 실행 중
- 캐시 테이블 어제까지 정상 갱신: TMDB movie 480K · TV 166K · KOBIS 6.6K · KMDB 2.7K
- TMDB 역사 백필 진행 중 (1999→1996, 매일 1년)
- backfill_movie_year/tv_year/kobis_daily/kmdb_daily/kmdb_backfill/kobis_backfill 모두 어제까지 completed

### ⚠️ 운영 위생 문제
1. **Stale `running` 2건** (id=74, 77): `changes_movie` 2026-05-15 데이터, 9일째 `finished_at=NULL`
2. **Stale `failed` 3건** (id=99, 102, 103): 2026-05-18 worker hang 사고 잔재, 정리 안 됨
3. **Stale `failed` 1건** (id=135): `kobis_backfill` 2023, error_sample 비어있음
4. **Worker Redis 재연결 취약**: 오늘 16:41 master→replica flip 감지 후 `Unrecoverable error` → 강제 재시작
5. **Beat lock 만료**: 오늘 22:21 `LockNotOwnedError` → 재시작 (WSL2 sleep 패턴)

## Step 분할

| Step | 이름 | Phase | 영향 |
|------|------|-------|------|
| 1 | esc-db-cleanup | A | DB 6건 cleanup (running 2 → failed, finished_at=now, error_sample="stale cleanup 2026-05-25") |
| 2 | esc-celery-config | B | celery_app.py: `broker_connection_retry_on_startup=True`, `broker_transport_options.visibility_timeout`, `broker_pool_limit` |
| 3 | esc-startup-hook | C | worker_ready signal: 시작 시 1h+ running sync_log 자동 failed 마킹 + 로그 |

## 금지사항
- Redis master/replica flip **근본 원인 추적은 follow-up** (이 plan 범위 아님)
- 코드 리팩토링 금지 — 최소 변경
- Beat 스케줄 변경 금지
