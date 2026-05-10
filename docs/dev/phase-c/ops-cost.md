# §6. 비용·운영

> 소속: Phase C ADR — `_index.md` | 인접: §2 [sources.md](sources.md), §5 [beat-schedule.md](beat-schedule.md)

## 6.1 외부 API rate limit

| 소스 | 공식 한도 | 운영 한도 (안전 마진) | 일 예상 호출 |
|---|---|---|---|
| TMDB | 50 req/sec | 30 req/sec | ~500/day (Trending+Upcoming+Discover) |
| KOBIS | 무제한 (정부 공개) | 1 req/sec (정중함) | ~100/day |
| KMDB | 무제한 | 1 req/sec | ~50/day |
| OMDb free | 1000/day | **800/day** (Redis daily counter) | 검수 화면 호출량 |

## 6.2 Redis daily counter (OMDb)

`fix(kobis): add Redis daily rate limiter` (커밋 238000c) 와 동일 패턴 재사용:

- 키: `omdb:daily:{YYYYMMDD}` (TTL 26h, 자정 KST 기준)
- 호출 전 `INCR` → 한도 초과 시 클라이언트가 503 + `Retry-After: <자정까지 남은 초>` 반환
- 운영자 검수 화면은 503 받으면 "오늘 OMDb 한도 소진 — 내일 재시도" 토스트

## 6.3 모니터링

- `GET /seeds/stats` — 일/소스별 발굴 건수·dedup 비율·승격률·잔여 검수 큐
- `GET /seeds/discovery-log?source=tmdb&date=2026-05-10` — raw 발굴 이력 (디버깅)
- Slack 알림 (`notify-router`):
  - discover task 3회 실패 → `urgent` 채널
  - 일 발굴량이 평균의 50% 미만 → `warn` 채널 (소스 장애 추정)

## 6.4 데이터 보존

| 테이블 | 보존 기간 | 정책 |
|---|---|---|
| `seed_discovery_log` | 30일 | partition drop (디버깅용 raw) |
| `content_seeds` (status=`rejected`) | 무기한 | 학습 데이터 |
| `content_seeds` (status=`accepted`) | 무기한 | promoted_content_id 추적 |

## 6.5 비용 추정 (월간)

- TMDB: 무료 (rate limit 만 준수)
- KOBIS: 무료
- KMDB: 무료
- OMDb: free tier 1000/day = $0 (운영 한도 800/day 로 안전), 초과 시 patreon $1/월

총 외부 API 비용: **$0~$1/월**. 인프라 비용 (Redis counter·DB 추가 테이블) 은
기존 인프라에 흡수 가능 — 별도 증설 불필요.
