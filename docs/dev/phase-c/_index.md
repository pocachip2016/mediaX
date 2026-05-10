# Meta Intelligence — Phase C (SEED 신규 콘텐츠 발굴)

> 상태: **draft** | 작성: 2026-05-10 | 관련 task: `plans/dev-meta-intelligence-phase-c/`
> 선행 ADR: `docs/dev/meta-intelligence.md` (Phase A/B — 5단계 데이터 흐름·필드 5분류)
> 본 디렉토리는 Phase C 의 모든 step (C.0 ~ C.10) 이 참조하는 단일 진실원이다.
> 임계·정책의 변경은 해당 섹션 파일을 먼저 수정한 뒤 step 진행한다.
> Phase D (WebSearch 보강) 는 별도 task — 본 디렉토리에 포함하지 않는다.

---

## §0. Phase C 의 위치

Phase A/B 는 "**이미 mediaX DB 에 있는 Content** 의 메타 품질을 끌어올리는" 파이프라인이다.
candidate → suggestion → resolution 의 3단계가 모두 `content_id` 를 전제로 동작한다.

Phase C 는 한 단계 앞 — "**아직 mediaX DB 에 없는 콘텐츠 자체** 를 외부에서 발굴해
내부 Content 로 끌어올리는" 단계다. 입력은 외부 발견(Trending, 개봉예정, 신규 등록),
출력은 검수를 거쳐 승격된 `Content` 행 한 줄.

이 두 phase 의 경계가 흐려지면 "발굴 후 자동 등록 vs 검수 후 등록" 같은 정책이
코드 위치에 따라 다르게 구현된다. 본 ADR 이 그 경계를 박아둔다.

---

## 섹션 인덱스

| § | 파일 | 다루는 결정 |
|---|---|---|
| §1 | [lifecycle.md](lifecycle.md) | SEED 5상태 (discovered → candidate → under_review → accepted/rejected) + 전이 규칙 |
| §2 | [sources.md](sources.md) | 소스 우선순위 (TMDB/KOBIS/KMDB/OMDb) + 발굴 영역 매트릭스 |
| §3 | [promotion-guard.md](promotion-guard.md) | 자동 승격 금지·검토 잠금·bulk-promote·ExternalMetaSource 자동 작성 |
| §4 | [dedup.md](dedup.md) | 적재 전·SEED 간 dedup 정책 (compute_match_score 재사용) |
| §5 | [beat-schedule.md](beat-schedule.md) | Celery Beat 시간표 (기존 schedule 충돌 회피 04:30~05:30) |
| §6 | [ops-cost.md](ops-cost.md) | rate limit·Redis counter·모니터링·비용 추정 |

후속 step 은 필요한 섹션 파일만 Read 하면 된다 — 본 인덱스는 ~50줄로 유지.

---

## §7. Phase D 와의 경계

Phase D (별도 task `dev-meta-intelligence-phase-d`) 는 WebSearch 기반 보강 —
"기존 Content 의 결측 필드를 자유 웹 검색으로 채우는" 작업이다.

Phase C (본 디렉토리) 와의 차이:
- Phase C: **신규 Content 발굴** (외부 정형 API → SEED → Content)
- Phase D: **기존 Content 보강** (WebSearch → field_suggestion)

두 phase 는 입력·출력·테이블 모두 다르므로 본 ADR 에 D 의 정책을 끼워넣지 않는다.
