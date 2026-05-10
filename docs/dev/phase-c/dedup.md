# §4. dedup 정책

> 소속: Phase C ADR — `_index.md` | 인접: §1 [lifecycle.md](lifecycle.md), §3 [promotion-guard.md](promotion-guard.md)

SEED 적재 전·SEED 간 두 단계로 중복을 막는다.
모두 Phase B `compute_match_score` (`api/meta_core/scoring.py`) 를 재사용한다.

## 4.1 적재 전 dedup (vs 기존 Content)

DiscoverySource 가 정규화 직후, content_seeds 행 생성 *전에* 실행:

1. mediaX `Content` 중 (title_norm, year, content_type) 1차 후보 SELECT
2. 후보별 `compute_match_score(seed_normalized, content)` 계산
3. 결과 분기:
   - `score ≥ 0.85` → SEED 적재 X, 기존 Content 에 `MatchEdge` 만 추가 (target_type=`content`)
   - `0.70 ≤ score < 0.85` → SEED 적재 + `suspected_match_content_id` 컬럼에 후보 1순위 기록 (검수자 힌트)
   - `score < 0.70` → 일반 SEED 적재

임계 0.85 는 Phase B `>=0.95` 자동확정과 다르다. SEED 단계는 *적재 회피* 임계
이므로 더 관대하게 잡아 false negative (기존 Content 누락하고 신규 SEED 적재) 를 줄인다.

## 4.2 SEED 간 dedup (동일 소스)

같은 (source_type, source_external_id) → UPSERT.

- UNIQUE 제약: `content_seeds(source_type, source_external_id)`
- 재발굴 시: metadata 만 갱신, `status` 는 보존 (rejected 는 sticky)
- `last_seen_at` 컬럼 갱신 → 운영자에게 "최근 재출현" 표시

## 4.3 SEED 간 fuzzy dedup (다른 소스, 같은 작품)

다른 소스가 같은 작품을 발굴한 경우 (예: TMDB·OMDb 동시 발견):

1. 신규 SEED 정규화 직후, 기존 SEED (status=`candidate` or `under_review`) 와
   `compute_match_score` 비교
2. `score ≥ 0.92` → 신규 SEED 미적재, 기존 SEED 의 `alt_external_ids` 에 누적
   ```json
   "alt_external_ids": [{"source": "omdb", "id": "tt1234567", "score": 0.94}]
   ```
3. `score < 0.92` → 별도 SEED 적재 (검수자가 수동 병합)

임계 0.92 는 *같은 작품* 판정 — 한국어/영문 제목 변형, 발음 표기 차이를
수용하면서도 "다른 시리즈의 동명 에피소드" 는 분리하는 균형점.

## 4.4 dedup 통계 노출

- `seed_discovery_log` 에 `dedup_decision` 컬럼: `appended_to_content` / `appended_to_seed` / `created_seed`
- `GET /seeds/stats` 가 일/소스별 비율 노출 → 발굴 효율 지표
