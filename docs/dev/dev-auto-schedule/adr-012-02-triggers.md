# ADR-012-02: 자동편성 트리거 3종

> 부모: [adr-012-auto-schedule_index.md](adr-012-auto-schedule_index.md)

자동편성 파이프라인은 **세 가지 경로**로 발동된다. 모두 동일한 `auto_service.advance_one` /
`run_to_stable` 멱등 코어를 호출하므로 중복 실행해도 안전하다.

## ① 시간 Beat (정기)

- `workers/tasks/scheduling_auto.py:auto_schedule_tick()` — `policy.auto_tick_enabled` 일 때만 동작.
- 각 버킷을 `claim_bucket(batch_size, visibility_timeout)` → 클레임된 노드마다 `advance_one`.
- `celery_app.py` beat 등록: off-peak·비0분(예: `crontab(minute="*/2")` 또는 정시 비0분).
- 콘텐츠 `pipeline_auto_tick`(15초)보다 느린 주기 — 편성은 실시간성 낮음.

## ② 콘텐츠 이벤트 (드리븐)

신규 콘텐츠가 매칭 풀에 들어오면, 그 콘텐츠를 담을 수 있는 auto 노드를 재매칭한다.

- 훅 지점: semantic profile 빌드 완료(`build_semantic_profiles` 태스크 말미) 또는 콘텐츠 `approved/published`.
- 동작: 대상 = **`auto_enabled=True` + 소속 set `published`** 노드만 → P3 재매칭(`suggest_links`) 큐잉.
- **과호출 방지(불변)**: 위 조건으로 한정. 전체 노드 재매칭 금지 — 부하·중복 suggested 폭증 위험.
- 재매칭은 `suggested` upsert(멱등) — 이미 active/rejected 링크는 건드리지 않음(`suggest_service` 보장).

## ③ 온디맨드 (콘솔)

- `POST /auto/nodes/{id}/run` → `run_to_stable(node, policy)` — 더 진행 불가/검수 잔류까지 동기 반복 advance.
- 콘솔 "자동 실행(run-to-stable)" 버튼이 선택 노드에 대해 호출.
- 운영자가 즉시 결과 확인하며 편성 — Beat 미대기.

## 공통 보장

- **멱등**: 세 경로가 동시/중복 호출돼도 `advance_one` 의 txn 선조건 재확인으로 이중 전이 없음.
- **hold**: `auto_hold=True` 노드는 Beat/이벤트 claim 에서 제외(운영자 수동 run 은 hold 해제하고 진행).
- **잔류 존중**: `auto_skipped_at` 마킹 노드는 임계값 변경 전까지 자동 재진입 안 함.
