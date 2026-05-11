# ADR: External API Quota Management & Caching Strategy

**Status**: Accepted
**Date**: 2026-05-11
**Phase**: meta_core / external integrations

---

## Context

mediaX 백엔드는 4개 외부 API 를 사용한다: TMDB, KOBIS, KMDB, OMDb. 각 API 별 rate limit · daily quota · 캐시 결정이 일관성 없이 분산돼 있어 다음 문제가 누적되고 있다.

### 현황 (2026-05-11 기준)

| 클라이언트 | Req/sec | Daily quota | 캐시 | 코드 위치 |
|---|---|---|---|---|
| TMDB | `asyncio.Semaphore(25)` | 없음 (공식 daily limit 없음) | SQL 3 테이블 (`tmdb_movie/tv/person_cache`) | `programming/metadata/tmdb_client.py` |
| KOBIS | `time.sleep(1.0)` (클라이언트) | 2900/day Redis INCR (`_kobis_rate_allowed`) | 없음 | `meta_core/clients/kobis_client.py` + `workers/tasks/metadata.py` L31–48 |
| KMDB | 없음 | 없음 | 없음 | `meta_core/clients/kmdb_client.py` |
| OMDb | 없음 | 설계만 (`phase-c/ops-cost.md` §6.2), 미구현 | 없음 | `meta_core/clients/omdb_client.py` |

### 문제점

1. **KOBIS Redis 카운터 재연결** — `_kobis_rate_allowed()` 가 호출마다 `redis.from_url()` 로 새 연결 생성 → 커넥션 풀 낭비.
2. **KOBIS UTC anchor 버그** — 키 생성에 `datetime.utcnow()` 사용 → KST 자정과 9시간 어긋남 (한국 운영 기준 부적합).
3. **재사용 불가** — KOBIS quota 로직이 `workers/tasks/metadata.py` 의 module-private 함수 → KMDB/OMDb 에서 재사용 불가.
4. **KMDB/OMDb rate limit · quota 부재** — KMDB 는 무제한 호출 가능, OMDb 는 설계 문서만 존재.

---

## Decision

### 1. 신규 `QuotaManager` 유틸리티 도입

`backend/shared/quota_manager.py` 에 단일 진실 원천 구현.

```python
class QuotaManager:
    def is_allowed(self, api: str, daily_limit: int) -> bool: ...
    def current_count(self, api: str) -> int: ...
```

### 2. 구현 원칙

- **Redis INCR + EXPIRE 원자성** — Lua script 또는 매 호출 EXPIRE 재설정으로 race condition 방지
- **TTL anchor** — KST 자정 + 1h 여유 (한국 운영 시각대 기준)
- **Redis 연결 재사용** — 모듈 레벨 싱글톤, `from_url()` 매 호출 금지
- **Fail-open** — Redis 장애 시 `True` 반환 + `logger.warning` (외부 의존성 장애가 워크로드 중단을 유발하지 않음)

### 3. API별 정책 (확정값)

| API | Req/sec 제한 | Daily limit | Redis key | 비고 |
|---|---|---|---|---|
| TMDB | 25 (Semaphore) | — | — | 공식 daily limit 없음. 현행 유지 |
| KOBIS | 1 (time.sleep) | **2900** | `kobis:daily:{YYYYMMDD_KST}` | 공식 3000 한도, 100 여유 |
| KMDB | 1 (time.sleep) | **500** | `kmdb:daily:{YYYYMMDD_KST}` | 공식 "무제한", 운영 캡 보수적 — 모니터링 후 상향 |
| OMDb | — | 800 | `omdb:daily:{YYYYMMDD_KST}` | 본 ADR 후속 작업 (OUT-OF-SCOPE) |

---

## Alternatives Considered

| 대안 | 기각 사유 |
|---|---|
| In-process counter (`threading.Lock` + dict) | Celery 워커 multi-process 환경에서 공유 불가 — fork 후 카운터 재시작 |
| DB 카운터 (Postgres row + `SELECT FOR UPDATE`) | 라운드트립 비용 (~5ms vs Redis ~0.5ms) + 락 경합으로 워커 쓰루풋 저하 |
| 외부 rate limiter 서비스 (Envoy / Istio / Kong) | 인프라 복잡도 증가 — 4개 API 단순 daily counter 에는 과잉 |

---

## Cache 전략 (현황 기록)

본 ADR 은 quota 통합이 주 범위이며, 캐시는 **현황 기록만** 한다.

- **TMDB SQL 캐시 (`tmdb_movie/tv/person_cache`)** — 데이터 안정성 (변경 빈도 낮음) + 재조회 빈도 높음. `alembic/versions/0005_tmdb_cache.py` 마이그레이션, `workers/tasks/tmdb_cache.py` 백필 비콘.
- **KOBIS / KMDB** — 일자별 박스오피스 · 신작 쿼리는 일회성 (재사용성 낮음) → 캐시 불필요.
- **WebSearchCache (`web_search_cache`, `alembic/versions/0008_add_web_search_cache.py`)** — SHA-256 hash key + `expires_at` 컬럼 (DB 레벨 TTL). 향후 신규 외부 API 캐시가 필요할 때 재사용 가능한 패턴.

---

## Consequences

### Positive
- 모든 daily quota 결정이 한 곳 (`QuotaManager` + 본 ADR) — 추적성 향상.
- KST anchor 통일 — 운영 시각 기준 일관성.
- 단위 테스트 가능 (`fakeredis` 또는 mock) — 회귀 방지.
- Redis MONITOR 로 quota 사용량 실시간 관측.

### Negative
- Redis 의존성 추가 — 단, 이미 Celery broker · KOBIS quota 에 사용 중이므로 신규 부담 없음.
- 마이그레이션 당일 KOBIS key 변경 (`kobis:daily_calls` → `kobis:daily`) — 카운터 일시 초기화 (다음 KST 자정 정상화).

---

## Follow-up

- **OMDb 구현** — 본 ADR 채택 직후 별도 task. `omdb:daily:{YYYYMMDD_KST}` (800/day) 패턴 적용.
- **TMDB daily monitoring** — 공식 daily limit 은 없지만 비용 관측 목적의 `tmdb:daily:{YYYYMMDD_KST}` 추가 검토 (별도 task).
- **KMDB 500/day 상향** — 운영 모니터링 결과에 따라 800/day 또는 1000/day 조정 (Follow-up amendment).

---

## 참고

- 기존 분산 결정 문서: `docs/dev/phase-c/ops-cost.md` (§6.2 OMDb quota)
- KOBIS Redis counter 원본: `commit 238000c` (`fix(kobis): add Redis daily rate limiter`)
- TMDB 캐시 결정 컨텍스트: `plans/dev-tmdb-cache/findings.md`
- 구현 plan: `plans/dev-quota-and-cache-adr/index.json`
