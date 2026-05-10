# §5. Beat 스케줄

> 소속: Phase C ADR — `_index.md` | 인접: §2 [sources.md](sources.md), §6 [ops-cost.md](ops-cost.md)

기존 Beat (`backend/workers/celery_app.py:23-55`) 와 시간 충돌을 회피하기 위해
**Phase C step-C0.md 의 제안 시간 (03:00·03:30·04:00) 을 04:30 이후로 이동** 한다.
SSOT 인 본 ADR 의 시간이 우선.

## 5.1 충돌 회피 — 기존 Beat 와의 시간 매트릭스

| 시간 (KST) | 기존 (Phase A/B) | Phase C (신규) |
|---|---|---|
| 01:00 | reeval-quality-scores | – |
| 02:00 | sync-tmdb-daily (보강) | – |
| 03:00 | sync-kobis-daily | – |
| 03:30 | tmdb-daily-changes | – |
| 03:45 | tmdb-daily-new-releases | – |
| 04:00 | check-missing-episodes | – |
| **04:30** | – | **discover-tmdb-daily** |
| **05:00** | – | **discover-kobis-daily** |
| **05:30** | – | **discover-kmdb-daily** |
| **Sun 06:00** | – | **discover-tmdb-trending-week** (백필) |

discover Beat 는 모두 `metadata` 큐로 라우팅 (기존 sync 와 동일 큐) — 같은 시간대에
겹치면 워커 처리량 경합 발생하므로 30분 간격으로 분리.

## 5.2 태스크 정의

- `discover_tmdb_daily` — TMDB Trending day + Upcoming KR + Discover (지난 7일)
  → DiscoverySource 정규화 → dedup → SEED 적재
- `discover_kobis_daily` — 개봉예정작 + 박스오피스 일간 → 정규화 → dedup → SEED
- `discover_kmdb_daily` — 신규 등록 영화·시리즈 (전일 createdDate 필터) → SEED
- `discover_tmdb_trending_week` — Trending week 백필 (daily 누락 보완), 일요일 1회
- OMDb — Beat 없음, `POST /seeds/{id}/enrich-omdb` 검수 화면 on-demand 만

## 5.3 실패 정책

- 각 discover task 는 `max_retries=3`, `retry_backoff=300s` (5분)
- 3회 실패 시: `seed_discovery_log` 에 `error` row + Slack 알림 (`notify-router` 경유)
- 부분 실패 (50건 중 N건 실패) 는 성공분만 commit, 실패분은 다음 회차 재시도

## 5.4 수동 트리거

기존 `sync_tmdb` 패턴 (workers/CLAUDE.md:60-62) 과 동일:
```bash
docker exec mediax-worker-1 celery -A workers.celery_app call workers.tasks.discovery.discover_tmdb_daily
```
