# ADR-010 — 파이프라인 진행 엔진 백엔드 이관: 단계 병행 워커 + 동시성 안전 + AI 단계 백프레셔

## 맥락
현재 파이프라인 콘솔(`/programming/contents/pipeline`)의 AUTO 진행 엔진은 **프론트엔드 브라우저 안의 React 루프**(`runAutoPipeline`, `page.tsx`)다. 다음 한계가 있다.

1. **백그라운드 진행 불가** — 콘솔 탭이 열려 살아있어야만 진행. 탭을 닫으면 멈춘다.
2. **단계 비병행** — `stageDefs.find(d => d.enabled && d.items.length > 0)`로 AUTO-ON인 **가장 낮은 단계 하나**의 배치를 전부 처리 후 재조회·반복. 긴 단계가 다른 단계를 막는다(기아).
3. **AI 단계 병목** — bucket 3(AI: RAG + AI번역 + AI축약)은 LLM 호출이라 단건도 느리고, 위 단계에서 계속 밀려와 적체. 현 구조는 그 단계 내부도 직렬이라 처리량 부족.
4. **Race condition** — 동시성 가드 `autoPipelineRef`는 한 브라우저 안에서만 유효. 다중 운영자/탭이 같은 콘텐츠를 중복 처리. 백엔드 `advance`/`approve`는 row-lock·status 선조건 없이 read-modify-write → lost update + StageEvent 중복.
5. **역방향 상태가 FE-로컬** — revert/재검수 회피용 `s4ReviewedRef`·revert-OFF가 reload 시 소실, 운영자 간 미공유.

Beat 스케줄(`celery_app.py`) 27개는 전부 외부 일일 동기화(TMDB/KMDB/discovery)일 뿐, 파이프라인 단계 진행을 도는 워커는 **없다**.

## 결정

### D1. 진행 엔진을 Celery 워커로 이관
- `pipeline_auto_tick` Beat 태스크(기본 **15초** 간격)가 진행을 구동. 콘솔은 **모니터**로 전환(진행 엔진 제거, 수동 단건 버튼은 유지).
- AUTO 토글은 `stage_auto_policy` PATCH = **백엔드 워커 제어**. 전체 AUTO off = tick dispatch 중단(kill switch).

### D2. 단계 병행 — bucket별 독립 태스크 + 큐 분리
- tick이 AUTO-ON bucket마다 처리 태스크를 **개별 dispatch** → 워커 동시성으로 단계 병행. 긴 단계가 다른 단계를 막지 않음.
- **큐 분리**: 빠른 단계(bucket 1/2/4)는 `pipeline_fast` 큐, 느린 AI 단계(bucket 3)는 `pipeline_ai` 전용 큐. AI backlog가 커도 빠른 단계는 계속 흐름(기아 방지).
- **공정성**: 태스크당 batch cap(기본 20). 남은 건 다음 tick.

### D3. AI 단계(bucket 3) 수평 확장 + 백프레셔
- AI 단계는 batch 직렬이 아니라 **per-item fan-out** — `process_ai_item.delay(id)`를 건별 dispatch. `pipeline_ai` 워커 concurrency=N으로 **동시 N건** 처리.
- concurrency 상한은 정책값(`ai_concurrency`, 기본 **2**). 로컬 Ollama 3b 스래싱·외부 API 한도 보호. 기존 QuotaManager/graceful-degrade 재사용.
- backlog 가시화: auto-status에 bucket별 pending(대기) + in-flight(처리중) + 평균 latency 노출.

### D4. 동시성 안전
- **claim**: 후보 콘텐츠를 `SELECT … FOR UPDATE SKIP LOCKED LIMIT n`(Postgres)으로 확보. 동시 claimer는 잠긴 행을 건너뜀.
- **claim 마킹**: claim 시 `auto_claimed_at` set → 다음 tick에서 제외(이미 큐에 들어간 건 재dispatch 방지). **visibility timeout**(`ai_visibility_timeout`, 기본 10분) 초과 시 stuck으로 보고 재claim(워커 죽어도 복구). 완료/실패 시 clear.
- **멱등 전이**: `advance_one`/`approve_one`은 txn 내에서 stage/status 선조건을 재확인하고 **이미 이동했으면 no-op**. StageEvent는 실제 전이 때만 기록.
- 기존 "bucket별 single-flight 락"은 AI를 직렬화하므로 **채택하지 않음**. claim 마킹 + 큐 concurrency 상한으로 안전성과 병렬성을 동시에 확보.

### D5. 역방향(revert/재검수) = `auto_hold`
- FE의 "이전단계 AUTO OFF" 휴리스틱 폐기. revert/re-review 시 콘텐츠별 `auto_hold=true` set → claim에서 제외(자동 재진행 차단).
- `POST /resume-auto {ids}`로 hold 해제. S4 잔류는 `auto_review_skipped_at`(영속)으로 마킹, 임계값 변경 시 초기화(정책 PATCH가 일괄 clear).

### D6. 두 축 모델 유지
- `current_stage`(위치) + `status`(완료) 두 축, bucket 매핑(1=S1, 2=S2~S5, 3=S6~S7, 4=S8, 5=S9, 6=rejected)은 ADR-006/009 그대로. 본 ADR은 "누가 advance를 호출하느냐"(FE→워커)와 동시성/병행만 바꾼다.

### D7. async 서비스의 워커 호출
- 기존 `enrich_autofill`/`ai_autofill`은 `async`(`apply_external_fields` 등). Celery 태스크는 동기 → 추출한 서비스 함수를 워커에서 `asyncio.run(...)`으로 호출(태스크별 이벤트루프). 엔드포인트는 기존대로 await.

## 스키마 변경
- `Content.auto_hold` (bool, default false) — 자동 진행 제외 플래그.
- `Content.auto_review_skipped_at` (timestamp, nullable) — S4 잔류(임계값 미달) 영속 마킹.
- `Content.auto_claimed_at` (timestamp, nullable) — claim/in-flight 마킹(visibility timeout 기준).
- `stage_auto_policy.auto_tick_enabled` (bool, default true) — tick 마스터 스위치.
- `stage_auto_policy.batch_size` (int, default 20) — 태스크당 처리 상한.
- `stage_auto_policy.ai_concurrency` (int, default 2) — AI 동시 처리 상한.
- `stage_auto_policy.ai_visibility_timeout` (int 초, default 600) — claim 재확보 임계.

## 엔드포인트
- `GET /test/pipeline/auto-status` — last tick, bucket별 pending/in-flight/processed/failed, 평균 latency, running.
- `POST /test/pipeline/resume-auto {ids}` — auto_hold 해제.
- 기존 `advance`/`approve`/`enrich-autofill`/`ai-autofill`은 추출 서비스 호출로 리팩터(동작 패리티 유지).

## 동시성 시나리오 검증(목표)
- 두 워커가 동시에 같은 bucket claim → SKIP LOCKED로 분할, 중복 처리 0.
- AI 단건 처리 중 tick 재발 → `auto_claimed_at`로 재dispatch 안 됨.
- 운영자 수동 advance와 워커 advance 충돌 → 선조건 재확인으로 1건만 전이.
- revert 후 워커 tick → `auto_hold`로 미재진행. resume 시 재개.
- 워커 크래시로 claim 고착 → visibility timeout 후 재claim.

## 비결정 / 후속
- 즉시 dispatch(신규 유입 시 tick 안 기다리고 바로 dispatch)는 후속 옵션. MVP는 15초 tick.
- 멀티 큐 워커는 docker-compose에 `pipeline_ai` 워커 서비스 추가 또는 기존 워커 `-Q` 멀티큐(Step 4b에서 확정).
- 게시(S9 이후) 자동화는 범위 외.
