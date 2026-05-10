# Step C.0: adr-phase-c-seed

> GitHub: 미생성 | Milestone: dev-meta-intelligence-phase-c

## 읽어야 할 파일
- `docs/dev/meta-intelligence.md` (Phase A/B ADR — §1 용어 5단계 / §2 필드 5분류 / §5 자동 확정 가드)
- `backend/api/meta_core/scoring.py` (compute_match_score 가중치)
- `backend/api/meta_core/aggregator.py` (Phase B 집계 흐름)
- `backend/api/programming/metadata/models/external.py` (ExternalSourceType ENUM)

## 목적
Phase C 의 모든 코드 변경은 ADR 문서에 정의된 SEED 라이프사이클·소스 우선순위·승격 가드를
따른다. ADR 없이 마이그레이션부터 들어가면 다음 step 에서 의미 다툼이 일어나므로,
**먼저 한 곳에 박아두는 것** 이 이 step 의 유일한 목적.

## 작업

### `docs/dev/phase-c/` 디렉토리 신설 (섹션별 파일 분할)

토큰 효율을 위해 단일 파일이 아닌 섹션별 분할로 작성한다.
구조:
```
docs/dev/phase-c/
├── _index.md          # §0 위치 + §7 Phase D 경계 + 섹션 링크
├── lifecycle.md       # §1
├── sources.md         # §2
├── promotion-guard.md # §3
├── dedup.md           # §4
├── beat-schedule.md   # §5
└── ops-cost.md        # §6
```

기존 `docs/dev/meta-intelligence-phase-c.md` 는 위 디렉토리로의 redirect 한 줄만 남긴다.

다음 섹션 모두 포함:

#### §1 SEED 라이프사이클 (5단계)
1. `discovered` — DiscoverySource 가 raw 발굴 (seed_discovery_log)
2. `candidate` — content_seeds 행 생성 (정규화 완료, 미매칭 확인됨)
3. `under_review` — 인간 검토 진행 중 (locked_by, locked_at)
4. `accepted` → 즉시 `Content` 승격 (이 시점에 ExternalMetaSource 도 작성됨)
5. `rejected` — 거부, content_seeds 유지 (재검토 가능)

각 상태마다 "이게 아닌 것" 한 줄.
예: "accepted ≠ confidence 100%. 인간 판단을 신뢰하기로 한 결정."

#### §2 소스 우선순위 (한국 VOD 특성)
| 우선 | 소스 | 역할 | 신뢰도 | 빈도 |
|---|---|---|---|---|
| 1 | TMDB | 글로벌 신작 (Trending/Upcoming/Discover) | 0.85 | daily |
| 2 | KOBIS | 한국 개봉예정 + 박스오피스 | 0.95 | daily |
| 3 | KMDB | 한국영화 풀백필 | 0.92 | daily |
| 4 | OMDb | IMDb 글로벌 보완 | 0.80 | on-demand |

소스별 발굴 영역 표(글로벌/한국/장르별 매트릭스).

#### §3 승격 가드 (자동 금지)
- 자동 승격 금지: confidence ≥ 0.95 여도 SEED → Content 자동 전환 금지
- 검토 잠금: 동시 편집 방지 — locked_by + locked_at, TTL 15분
- bulk-promote: max 50건/요청, 하나라도 dedup 충돌 발견 시 전체 abort
- 승격 직후 ExternalMetaSource 자동 작성: source_type=발굴 소스, external_id=원본 ID

#### §4 dedup 정책
- SEED 적재 전 mediaX Content 와 비교 (compute_match_score ≥ 0.85 → SEED 미적재, MatchEdge 만 추가)
- SEED 간 중복: 동일 source_type + external_id → UPSERT
- SEED 간 fuzzy match (title+year) ≥ 0.92 → 기존 SEED 에 alt_external_ids 누적

#### §5 Beat 스케줄
- 03:00 KST: discover_tmdb (Trending day + Upcoming)
- 03:30 KST: discover_kobis (개봉예정 + 박스오피스 일)
- 04:00 KST: discover_kmdb (신규 등록 영화)
- 주 1회 일요일 05:00: discover_tmdb_trending_week (백필)
- OMDb 는 SEED 검수 화면에서 on-demand 보강

#### §6 비용·운영
- TMDB rate limit: 50 req/sec — 안전 30 req/sec
- KOBIS: 무제한 (정부 공개) — 정중함을 위해 1 req/sec
- KMDB: 무제한 — 1 req/sec
- OMDb free tier: 1000/day — Redis daily counter 필수

## Acceptance Criteria
```bash
bash .claude/verify.sh phase-c-step0
```

검증 항목:
- `docs/dev/meta-intelligence-phase-c.md` 존재 + 6개 섹션 모두 포함
- 코드 변경 0줄

## 금지사항
- 코드/마이그레이션 금지 — ADR 단계
- Phase D(WebSearch) 내용 포함 금지 — 별도 task
- "TODO 적기" 식 빈 섹션 금지 — 각 섹션 30줄 이상
