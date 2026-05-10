# Step C.9: seed-beat-monitoring

> GitHub: 미생성 | Milestone: dev-meta-intelligence-phase-c

## 읽어야 할 파일
- C.2~C.4 산출물 — TmdbDiscoverySource, KobisDiscoverySource, KmdbDiscoverySource
- `backend/workers/__init__.py` — Beat 등록 패턴
- `backend/workers/CLAUDE.md` (있으면)

## 작업

### 1. Celery tasks
`workers/discovery_tasks.py` 신설:
```python
@shared_task
def discover_tmdb(mode='trending_day', limit=100): ...

@shared_task
def discover_kobis(mode='box_office_daily'): ...

@shared_task
def discover_kmdb(mode='new_release', days=7): ...

@shared_task
def discover_all_daily(): ...   # 위 3개 chord 로 묶음
```

### 2. Beat 스케줄
`workers/celery_app.py` (또는 기존 beat 설정 위치) 에 추가:
```python
beat_schedule = {
    "discover_tmdb_daily":  crontab(hour=3, minute=0,  ...),
    "discover_kobis_daily": crontab(hour=3, minute=30, ...),
    "discover_kmdb_daily":  crontab(hour=4, minute=0,  ...),
    "discover_tmdb_weekly_trending": crontab(day_of_week=0, hour=5, minute=0, ...),
}
```

### 3. 모니터링 API
`api/meta_core/intelligence/router.py` 확장:
- `GET /seeds/discovery-log?source=&mode=&limit=` — seed_discovery_log 페이징
- `GET /seeds/discovery-stats` — 최근 7일 / 30일 / 소스별 누적 통계
- `GET /seeds/funnel` — discovered → candidate → under_review → accepted 변환률

### 4. 알림 (선택)
discovery_tasks 실패 시 ntfy 또는 Slack 호출 — `notify_router` 활용 (있으면).
구체적 트리거: 24시간 내 new_seeds=0 (소스 장애 의심) 또는 errors > 0.5 * total.

### 5. 단위 테스트
- `tests/workers/test_discovery_tasks.py` ≥ 5개:
  - discover_tmdb 정상 task 실행 (mock TMDB)
  - discover_all_daily chord 묶음 검증
  - 실패 시 retry 메커니즘 검증
- `tests/meta_core/test_discovery_monitoring.py` ≥ 4개:
  - discovery-log 필터/페이징
  - discovery-stats 7일/30일 카운트
  - funnel 변환률 계산

## Acceptance Criteria
```bash
bash .claude/verify.sh phase-c-step9
```

- Celery beat 설정에 4개 schedule 추가됨
- workers/discovery_tasks.py 4개 task 정의
- 모니터링 API 3개 엔드포인트 200 응답
- pytest 9+ pass

## 금지사항
- Beat 시간 변경 금지 — ADR §5 따라 03:00/03:30/04:00 고정
- 자동 알림 항상 발송 금지 — 임계값(0건/50% errors) 초과 시만
- discovery 동기 실행 금지 — 항상 Celery 비동기 (모니터링 API 도 stat 조회만)
