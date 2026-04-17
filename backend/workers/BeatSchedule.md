# Beat Schedule 가동 계획

**목적**: `celery_app.py`에 설계된 6개 Beat 태스크를 실제로 주기적으로 돌아가도록 운영 체계를 구축.

---

## 1. 현재 상태 진단

| 항목 | 설계 | 현재 |
|------|------|------|
| `celery_app.py` beat_schedule | 6개 태스크 정의 | ✅ 정의 완료 |
| Redis (broker/backend) | Docker | ⚠️ 미기동 (`docker compose up -d redis` 필요) |
| Celery worker 프로세스 | `docker-compose.yml`의 `worker` 서비스 | ⚠️ 미기동 |
| Celery **beat** 프로세스 | ❌ **없음** (docker-compose에 beat 서비스 미정의) | ❌ 미정의·미기동 |
| 쿼터/레이트리밋 관리 | `BATCH_LIMIT=50`만 존재 | ⚠️ 429 재시도·일일 카운터 없음 |
| 모니터링 | 로그만 | ⚠️ Flower 등 없음 |

**핵심 Gap**: docker-compose에 Beat 서비스가 없어 "스케줄 발화 주체"가 부재.

---

## 2. 전제 조건

### 2.1 인프라
- Redis 기동: `docker compose up -d redis`
- Postgres 기동: `docker compose up -d postgres` → `alembic upgrade head`
- (선택) Ollama: AI 처리 태스크(`process_content_metadata`, `enrich_content_metadata`) 호출 시 필요 — Beat 태스크 중 `reeval_quality_scores`가 간접 사용

### 2.2 환경 변수 (`backend/.env`)
| 키 | 관련 Beat 태스크 | 필수 |
|----|-----------------|------|
| `REDIS_URL` | 전체 (broker) | ✅ |
| `DATABASE_URL` | 전체 | ✅ |
| `TMDB_API_KEY` | `sync_tmdb`, `check_missing_episodes` | 없으면 skip |
| `KOBIS_API_KEY` | `sync_kobis` | 없으면 skip |
| `IMAP_HOST`·`IMAP_USER`·`IMAP_PASS` | `poll_cp_emails` | 없으면 skip |
| `OLLAMA_URL`·`OLLAMA_MODEL` | `reeval_quality_scores`(간접) | 없으면 AI 처리 실패 |

---

## 3. 실행 플랜

### Phase 1 — docker-compose에 `beat` 서비스 추가 (권장)

`docker-compose.yml`에 다음 서비스를 추가한다:

```yaml
  beat:
    build: ./backend
    command: celery -A workers.celery_app beat --loglevel=info
    volumes:
      - ./backend:/app
    env_file:
      - ./backend/.env
    environment:
      - PYTHONPATH=/app
    depends_on:
      - redis
      - worker
```

**주의**:
- beat 인스턴스는 반드시 **1개만** 띄울 것 (중복 실행 시 태스크 이중 발화).
- worker와 분리한 이유: worker를 replica로 스케일해도 beat는 단일 유지.

### Phase 2 — 로컬 개발 환경 (Docker 없이)

터미널 3개를 열어 각각 실행:

```bash
# 1. 인프라
docker compose up -d postgres redis ollama

# 2. worker (백엔드 venv 활성화 후)
cd backend
.venv/bin/celery -A workers.celery_app worker --loglevel=info \
  -Q metadata,design.high,design.normal,design.brand_check,design.cdn,ingest,analytics

# 3. beat
cd backend
.venv/bin/celery -A workers.celery_app beat --loglevel=info
```

로컬 환경변수 주입:
```bash
export DATABASE_URL=postgresql://media_ax:media_ax@localhost:5432/media_ax
export REDIS_URL=redis://localhost:6379/0
export OLLAMA_URL=http://localhost:11434
```

### Phase 3 — 운영 품질 보강 (후속)

1. **Flower 기동** (태스크 모니터링 UI)
   ```yaml
   flower:
     build: ./backend
     command: celery -A workers.celery_app flower --port=5555
     ports: ["5555:5555"]
     depends_on: [redis]
   ```
2. **쿼터 관리 강화** (§5 참조)
3. **알림** — Beat 실패 시 Slack/이메일 webhook

---

## 4. 태스크별 상세

| # | 태스크 | 주기 | 큐 | 입력 선택 조건 | 배치 크기 | 외부 API |
|---|--------|------|----|---------------|----------|---------|
| 1 | `poll_cp_emails` | 5분 | metadata | IMAP 미읽음 | 무제한 | IMAP, Ollama |
| 2 | `reeval_quality_scores` | 매일 01:00 | metadata | `status=review` | 100건 | Ollama(간접) |
| 3 | `sync_tmdb` | 매일 02:00 | metadata | `tmdb_id IS NULL` AND type∈{movie,series} AND status≠waiting | **50건** | TMDB |
| 4 | `sync_kobis` | 매일 03:00 | metadata | 전일 신규 영화 | KOBIS 응답 전체 | KOBIS |
| 5 | `check_missing_episodes` | 매일 04:00 | metadata | 시리즈 전체 | — | TMDB |
| 6 | `retry_failed_enrichments` | 6시간 | metadata | `status=processing` AND `updated_at < now-6h` | 50건 | (enqueue만) |

**태스크 간 의존**:
- `poll_cp_emails` → Content(waiting) 생성 → 별도 flow에서 `enrich_content_metadata` 큐잉
- `sync_tmdb` → `tmdb_id` 매핑만 수행. 시리즈 에피소드 보강은 `check_missing_episodes`가 담당
- `retry_failed_enrichments` → `enrich_content_metadata`를 재큐잉

---

## 5. 쿼터/레이트리밋 계획

### 5.1 TMDB (v3 API)
- 공식 제한: **50 req/sec** (일일 총량 제한은 공식 문서상 없음, 다만 abuse 감지 시 차단)
- 현재 방어: `BATCH_LIMIT=50`로 간접 제한 → 1일 최대 50건 처리
- **권장 보강**:
  - `httpx.AsyncClient(limits=httpx.Limits(max_connections=10))` + `asyncio.Semaphore(5)`
  - 429 응답 시 `Retry-After` 헤더 기반 백오프
  - `daily_quota_used` Redis 카운터(`tmdb:quota:YYYYMMDD`)로 일일 호출 수 추적

### 5.2 KOBIS
- 공식 제한: 일일 10,000 req (무료), 키당
- 현재 방어: 전일 신규분만 조회(수백건 수준)
- 추가 조치 불필요

### 5.3 IMAP
- CP사 메일함 부하 — 5분 주기·UID 기반 증분 조회로 이미 가벼움

### 5.4 Ollama (간접)
- 로컬 모델이라 외부 쿼터 없음. 단, `reeval_quality_scores`가 100건을 한꺼번에 큐잉하면 GPU 경합 → worker concurrency 제한 권장 (`--concurrency=2`)

---

## 6. 검증 체크리스트

가동 후 다음을 순서대로 확인:

```bash
# (a) beat 로그에 schedule entry 출력 확인
docker logs -f mediax-beat-1 | grep -i 'scheduler'
# → "beat: Starting..." 후 "Scheduler: Sending due task sync-tmdb-daily (...)" 류

# (b) Redis에 broker 큐 생성 확인
docker exec mediax-redis-1 redis-cli KEYS 'celery*'

# (c) 수동 즉시 실행으로 태스크 자체 검증
docker exec mediax-worker-1 celery -A workers.celery_app call \
  workers.tasks.metadata.sync_tmdb

# (d) 결과 확인 (DB)
docker exec mediax-postgres-1 psql -U media_ax -d media_ax -c \
  "SELECT count(*) FILTER (WHERE tmdb_id IS NOT NULL) AS mapped,
          count(*) FILTER (WHERE tmdb_id IS NULL) AS unmapped
   FROM content_metadata;"
```

**정상 동작 조건**:
- [ ] `beat` 컨테이너 로그에 "Scheduler: Sending due task" 출력
- [ ] `worker` 컨테이너 로그에 "Task workers.tasks.metadata.X received" 출력
- [ ] 각 태스크 실행 후 return dict(`updated`, `skipped`, `failed`) 로그 기록
- [ ] 02:00/03:00/04:00 KST에 해당 태스크 자동 실행 (다음날 오전 확인)

---

## 7. 실행 체크리스트

| 단계 | 작업 | 상태 |
|------|------|------|
| 1 | `backend/.env`에 `TMDB_API_KEY`, `KOBIS_API_KEY` 설정 (운영 시) | ⬜ |
| 2 | `docker-compose.yml`에 `beat` 서비스 블록 추가 | ⬜ |
| 3 | `docker compose up -d postgres redis` | ⬜ |
| 4 | `alembic upgrade head` | ⬜ |
| 5 | `docker compose up -d worker beat` | ⬜ |
| 6 | 수동 `celery call` 로 각 태스크 1회 검증 | ⬜ |
| 7 | 24h 후 자동 실행 로그 확인 | ⬜ |
| 8 | (선택) Flower 기동, 쿼터 카운터 도입 | ⬜ |

---

## 8. 장애 시나리오 및 대응

| 증상 | 원인 후보 | 대응 |
|------|----------|------|
| Beat가 태스크를 발화하지 않음 | `beat` 프로세스 미기동 / Redis 연결 실패 | 로그 확인 → Redis 접속 테스트 |
| 태스크가 Pending만 쌓임 | worker 미기동 or 큐 라우팅 불일치 | worker의 `-Q` 옵션에 `metadata` 포함 여부 확인 |
| TMDB 429 폭주 | 레이트리밋 미보강 | §5.1 백오프·세마포어 적용 |
| Beat 이중 발화 (같은 태스크 2회 실행) | `beat` 컨테이너가 2개 이상 | replica=1 고정 |
| `No module named 'api'` | `PYTHONPATH=/app` 환경변수 누락 | docker-compose 환경 블록 확인 |
