# Meta Intelligence — Architecture Decision Record

> 상태: **draft** | 작성: 2026-05-09 | 관련 task: `plans/dev-meta-intelligence/`
> 원천 설계: `backend/crosscheck.md`
> 본 문서는 dev-meta-intelligence Phase A~D 의 모든 step 이 참조하는 단일 진실원이다.
> 산식·임계·정책의 변경은 본 문서를 먼저 수정한 뒤 step 진행.

---

## §1. 용어 정의 (5단계 데이터 흐름)

외부 소스에서 시작해 내부 Content 까지 도달하는 데이터의 5단계를 명확히 분리한다.
"정확히 무엇이 무엇과 다른지" 를 단계별로 못 박아두지 않으면 테이블·API·검수 UI 가
같은 이름을 다른 의미로 사용하게 된다.

### 1.1 `source_item` — 원천 raw 1건

외부 소스에서 발견한 단일 항목의 **있는 그대로** 의 기록.

```text
"TVING 신작 페이지의 N번째 카드"
"TMDB discover 응답의 N번째 결과"
"KMDb search API 응답의 N번째 row"
```

특징:
- 원본 URL + raw payload 그대로 보존 (가공 없음)
- 1 source_item = 1 외부 소스의 1 항목
- 본 phase 에서 별도 테이블로 분리하지 않고 `metadata_candidates.raw_payload + source_url` 컬럼에 합쳐서 보존 (Phase C 에서 source_items 테이블 분리 검토)

**이게 아닌 것**: 정규화된 메타. raw 만 보존.

### 1.2 `metadata_candidate` — 정규화된 외부 후보

source_item 을 mediaX 내부 스키마(title/year/cast/synopsis 등)로 파싱한 결과.

원칙:
- 1 source_item → 1 candidate (다대일 안 만든다 — 추적성 보존)
- candidate 는 **아직 어느 내부 Content 와도 매칭이 확정되지 않은 상태**
- title_norm, year, content_type 등 비교 가능한 정규화 필드 포함
- 같은 (source_type, source_external_id) 는 UNIQUE — 재방문 시 upsert

**이게 아닌 것**:
- 매칭 확정 외부 ID 저장소(=`ExternalMetaSource`)
- 콘텐츠 그 자체(=`Content`)

### 1.3 `field_suggestion` — 필드 단위 후보값

candidate 에서 **특정 필드 1개의 후보값** 을 떼어낸 단위.

원칙:
- 1 candidate → N suggestions (필드 수만큼)
- "이 콘텐츠의 synopsis 후보로 이 값을 제안" 이라는 의미
- target 은 항상 내부 `content_id` (매칭이 끝난 다음에 생성됨)
- 같은 (content_id, field_name) 에 여러 source 의 suggestion 이 공존 가능

**예**: 한 `Content` 의 synopsis 에 대해 TMDB·KMDb·네이버 source 가 각각 다른 줄거리를
제안하면, suggestion 3 row.

**이게 아닌 것**: 적용된 값. suggestion 은 "후보" 일 뿐, 적용 결정은 `field_resolution` 의 책임.

### 1.4 `match_edge` — candidate ↔ Content 매칭

candidate 가 어느 내부 Content 와 같은 작품인지에 대한 **점수 + 사유** 를 담는 연결선.

원칙:
- 1 candidate 가 N Content 와 후보 매칭될 수 있음 (동명이인 영화 등)
- score (0.0~1.0) + sub_scores (필드별) + reasons (사유 태그)
- decided=true 가 되어야 매칭 확정 (자동 또는 검수자 결정)
- 매칭 확정 시 `ExternalMetaSource` row 가 함께 생성됨

**이게 아닌 것**: 동일성 자체의 사실. 매칭은 점수에 기반한 판정이며, 임계 미달 시 폐기.

### 1.5 `seed_candidate` — 신규 콘텐츠 후보

매칭 실패한 candidate 를 "내부 DB 에 없는 작품" 으로 보고 신규 Content 후보로 승격한 row.

원칙:
- 모든 match_edge 가 임계 미달 → SEED 생성
- `pending_review → approved → 새 Content 생성` 흐름
- approved 시 candidate 의 정규화 필드를 새 Content 로 복사
- Phase C 에서 본격 사용 (Phase A·B 는 테이블만 신설하고 흐름은 미가동)

**이게 아닌 것**: 미매칭 candidate 자체. SEED 는 **승급된** candidate. 승급되지 않은 미매칭
candidate 는 그냥 candidate 로 남아 다음 enrich 사이클을 기다림.

---

## §2. 필드 5분류 (Field Type Taxonomy)

검수 작업량을 결정하는 핵심 결정. 모든 필드를 "검수 큐" 로 직행시키면 운영 불가능.
필드의 의미적 성격에 따라 자동 확정 정책을 분기한다.

| 분류 | 예시 필드 | 합의 의미 | 자동 확정 정책 |
|---|---|---|---|
| **A. 단일값·이산** | director(주연출), primary_genre, release_year, runtime, country, content_type | "같은 값" 이 곧 "정답 일치" | 2+ 소스 일치 → 자동 확정 |
| **B. 다중값·이산** | cast, secondary_genres, mood_tags, keyword_tags | 멤버별 등장 빈도 | 2+ 소스 등장 멤버만 자동 채택, 단일 소스 멤버는 검수 |
| **C. 자유 텍스트** | synopsis, description, episode_summary | 두 소스가 같을 수 없음 | 항상 pending — 검수자 pick / LLM merge / 원문 유지 |
| **D. 자산 URL** | poster, backdrop, logo, stillcut | 해상도·소스 신뢰도가 정답 | 품질 점수 1위 자동 채택, 나머지는 alternates |
| **E. 외부 ID** | tmdb_id, kobis_id, kmdb_id, watcha_id | 소스별 1:1, 충돌 불가 | 모든 소스의 id 항상 저장 |

### 2.1 분류별 운영 의미

- **A** 가 자동 확정 효과가 가장 큼. 운영 첫 달의 검수 부담 절감 핵심.
- **B** 는 cap 필요 (cast top-20, secondary_genres top-3) — 양적 폭주 방지.
- **C** 는 자동 확정 불가. 검수자 의사결정만 가능. LLM merge 는 옵션이지 자동 적용 아님.
- **D** 는 source_priority 우선. TMDB > KMDb > KOBIS > CP. 동률 시 해상도.
- **E** 는 충돌 없음. 모든 소스의 id 보존이 곧 정답.

### 2.2 분류 결정의 단일 출처

`backend/api/meta_core/field_strategy.py:FIELD_STRATEGIES` (Phase B step6) 가 단일 카탈로그.
검수 UI·Aggregator·운영 도구 모두 이 카탈로그만 참조한다. 카탈로그를 우회한 분기 분기점이
생기면 운영 시 정책 변경이 코드 여러 곳을 흩어 다니게 됨.

### 2.3 분류 추가·변경 절차

새 필드 추가 시:
1. 본 ADR §2 표에 한 줄 추가
2. `FIELD_STRATEGIES` 카탈로그에 entry 추가
3. 정규화 함수가 필요하면 `meta_core/scoring.py` 또는 `meta_core/field_strategy.py` 에 추가
4. Aggregator 단위 테스트 추가

분류 자체의 변경(예: poster 를 D → C 로) 은 운영 영향이 크므로 별도 ADR 갱신 PR 로 처리.

---

## §3. 신뢰도 산식 — 2축 분리

같은 이름의 점수가 두 가지 의미로 혼용되는 일을 막는다.

### 3.1 `match_score` — candidate ↔ Content 동일성

**범위**: 0.0 ~ 1.0
**위치**: `MatchEdge.score` (DB) / `api.meta_core.scoring.compute_match_score` (코드)
**용도**: candidate 가 내부 Content 와 같은 작품인지 판정

**가중치**:
```
match_score =
    0.30 * title_score
  + 0.20 * year_score
  + 0.15 * cast_overlap_score
  + 0.15 * multi_source_agreement
  + 0.10 * external_id_score
  + 0.05 * source_reliability
  + 0.05 * image_asset_quality
```

**임계**:
| 점수 | 분류 | 처리 |
|---|---|---|
| ≥ 0.90 | auto | 자동 매칭 — match_edge.decided=true, ExternalMetaSource 생성 |
| 0.70 ~ 0.89 | review | 검수 큐 |
| 0.50 ~ 0.69 | hold | 후보 보류 (다음 사이클 재평가) |
| < 0.50 | drop | 폐기 (해당 (candidate, content) 쌍 매칭 시도 중단) |

**유의**: 본 산식은 **2개 객체 사이의 동일성** 점수다. 콘텐츠가 "얼마나 잘 정리됐는지" 와 무관.

### 3.2 `quality_score` — Content 메타 완성도

**범위**: 0 ~ 100
**위치**: `ContentMetadata.quality_score` / `api.programming.metadata.ai_engine._calculate_quality_score`
**용도**: 콘텐츠의 메타 정보가 얼마나 채워졌고 일관된지 판정

**기존 산식 보존** (변경하지 않음):
```
quality_score =
    30% * synopsis_completeness
  + 20% * genre_classification
  + 15% * tag_count
  + 20% * external_meta_mapped
  + 15% * basic_fields_filled
```

**임계** (Content.status 자동 전환에 사용):
- 90+ → approved
- 70~89 → review
- < 70 → review + 재처리 제안

### 3.3 두 점수의 관계

| 측면 | match_score | quality_score |
|---|---|---|
| 비교 대상 | candidate vs Content (2 객체) | Content 단독 |
| 범위 | 0.0~1.0 | 0~100 |
| 적재 위치 | MatchEdge.score | ContentMetadata.quality_score |
| 책임 모듈 | meta_core.scoring | programming.metadata.ai_engine |
| 변경 영향 | 매칭 자동화 비율 | 콘텐츠 상태 전환 |

**이름 충돌 금지** — 변수명·로그 prefix·docstring 모두에서 두 점수가 섞이지 않도록.

---

## §4. 소스 신뢰도 가중치

source_reliability 는 match_score 의 한 항이자 자동 확정 가드(§5)의 가중치 합산에도 쓰인다.

### 4.1 기본값

| 소스 | 가중치 | 근거 |
|---|---|---|
| TMDB | 1.00 | 메타 정확도·갱신 빈도·다국어 지원 가장 높음 |
| KOBIS | 0.95 | 한국 영화 박스오피스의 1차 공식 소스 |
| KMDb | 0.95 | 한국영상자료원 — 한국 작품 메타 풍부 (감독·배급·등급 컨텍스트) |
| WATCHA | 0.80 | 메타 풍부하나 한국 OTT 편향 |
| 네이버/다음 | 0.70 | 검색 메타 수준, 정확도 변동 |
| WebSearch (Brave/Serp) | 0.50 | 노이즈 큰 보조 채널, 검증 필수 |
| other | 0.50 | 미분류 소스 기본 |

### 4.2 환경변수 override

```
META_SOURCE_WEIGHT__TMDB=1.00
META_SOURCE_WEIGHT__KOBIS=0.95
META_SOURCE_WEIGHT__KMDB=0.95
META_SOURCE_WEIGHT__WATCHA=0.80
META_SOURCE_WEIGHT__WEBSEARCH=0.50
```

미설정 시 코드 기본값 사용. 운영 중 false positive 발견 시 env 만으로 즉시 조정 가능.

### 4.3 가중치 사용처

1. `match_score` 의 source_reliability 항 (가중치 5%)
2. `field_resolutions` 의 자동 확정 가드 (§5) — agreeing_sources 의 weight 합산
3. D 분류(자산) 의 source_priority 정렬

세 곳 모두 `api.meta_core.scoring.source_reliability(source_type)` 한 함수만 호출.

---

## §5. 자동 확정 가드

검수자 부담을 줄이는 핵심 장치. 단, 잘못된 자동 확정 1건의 비용이 크므로 보수적으로 시작.

### 5.1 A 분류 (단일값·이산)

**가드 조건** (둘 다 만족):
1. `agree_threshold ≥ 2` — 2개 이상 소스가 같은 값 제안
2. `sum(source_weight) ≥ 1.5` — 합산 신뢰도 1.5 이상

**예시**:
- TMDB(1.0) + KMDb(0.95) 동의 → 합 1.95 ≥ 1.5 ✓ 자동 확정
- 네이버(0.70) + 다음(0.70) 동의 → 합 1.40 < 1.5 ✗ 검수 큐

### 5.2 B 분류 (다중값·이산)

**가드 조건**:
- 멤버별 등장 ≥ 2 sources → 자동 union 에 포함
- 단일 소스 멤버 → alternates 로 보존, 검수 시 추가 옵션

**Cap**:
- cast: 자동 채택 top-20 (TMDB cast_order 우선)
- secondary_genres: top-3
- mood_tags: top-10

Cap 초과분은 alternates 로만 보존.

### 5.3 D 분류 (자산 URL)

**가드 조건**:
1. `source_priority` 1순위 소스가 값을 제공 → 그 값 자동 채택
2. 동률 또는 1순위 소스 없으면 `quality_fn` (해상도·파일크기) 1위 자동
3. 나머지는 alternates 로 보존 (수동 교체 가능)

source_priority: `[tmdb, kmdb, kobis, cp]` (poster/backdrop) / `[cp, tmdb, kmdb]` (logo)

### 5.4 자동 확정 롤백 경로

모든 자동 확정 row 는 `field_resolutions.applied_to_content=true` 와 함께 `decision=auto_*` 로
표시된다. 다음 절차로 되돌릴 수 있다:

1. 검수 백엔드 `POST /resolutions/{field}/reject` 호출
2. `decision=rejected, applied_to_content=false` 로 갱신
3. ContentMetadata 의 해당 필드를 이전 값으로 복원 (이전 값이 비어 있었으면 NULL)

**자동 확정에도 audit trail 필수**: chosen_suggestion_ids 와 agreeing_sources 가 항상 채워져야 함.

### 5.5 운영 첫 달 보수값

운영 시작 시 보수적으로 출발:
- A 분류 가드 활성: director / release_year / runtime / country / content_type
- A 분류 가드 보류: primary_genre (장르 표기 차이로 false positive 가능)
- B 분류 cap 보수: cast top-10 / secondary_genres top-2
- D 분류 활성: poster / backdrop (stillcut 은 검수)

운영 데이터 기반으로 한 달 후 임계 재조정.

---

## §6. KMDb 추가

본 phase 에서 신규 외부 소스로 KMDb 를 추가한다.

### 6.1 KMDb 개요

- 운영: 한국영상자료원(KOFA)
- API: `http://api.kmdb.or.kr/openapi-data2/`
- 키 발급: 무료 신청 (https://www.kmdb.or.kr/info/api/main)
- 응답 포맷: JSON (or XML)
- 강점: 한국 영화 메타 (감독·작가·배급·제작·등급·관련작) 정보 풍부
- 약점: TV 시리즈 메타는 약함

### 6.2 ENUM 변경 (Phase A step1)

`backend/api/programming/metadata/models/external.py:ExternalSourceType` 에 `kmdb` 멤버 추가.
PostgreSQL 의 `externalsourcetype` enum 에 `ALTER TYPE ... ADD VALUE 'kmdb'` 적용 (마이그레이션 0011).

### 6.3 클라이언트 (Phase B step5)

`backend/api/meta_core/clients/kmdb_client.py`:
```
KmdbClient(api_key=env KMDB_API_KEY, base_url="http://api.kmdb.or.kr/openapi-data2/")
  .search_movie(title: str, year: int = None) -> list[dict]
  .get_movie_detail(docid: str) -> dict
```

키 미설정 시 silent skip (다른 소스만으로도 enrich 동작 보장).

### 6.4 사용처

- on-demand enrich (Phase B): TMDB enrich 후 한국 작품(country=KR) 에 한해 KMDb 보강
- Daily Beat: **본 phase 에선 등록하지 않음**. Phase C 의 SEED 흐름에서 일괄 통제.

### 6.5 가중치

§4 표 참조 — 0.95 (KOBIS 와 동일선). 한국 작품 컨텍스트에선 TMDB 와 비등하게 신뢰.

### 6.6 SyncSource ENUM 보강

`TmdbSyncSource` 에 `kmdb_daily`, `kmdb_backfill` 추가는 **별도 마이그레이션 0012** 로 분리.
이유: PostgreSQL 의 `ADD VALUE` 는 트랜잭션 밖 실행 필요. 0011 과 같은 트랜잭션에 묶으면 실패.

---

## §7. 비용·운영 가드

### 7.1 LLM merge 비용

**규칙**: synopsis 등 C 분류 필드의 LLM merge 는 **검수자 수동 요청** 시에만 호출.
Daily 자동 호출 금지. Aggregator 가 자동으로 merge 수행하지 않음.

**비용 가시화**:
- 호출 1회당 `external_sync_log` 에 `external_source=llm_merge` row 1개 기록
- 일별·월별 호출량 모니터링 가능

### 7.2 WebSearch 비용 (Phase D)

**Provider**:
- 1차: Brave Search (무료 2,000/월)
- 2차: SerpAPI (유료, 키 없으면 skip)

**캐시**: 기존 `web_search_cache` 7일 TTL 유지

**호출 한도**:
- `WEBSEARCH_DAILY_CAP` env (기본 50) — Redis counter 일별 누적
- `WEBSEARCH_MONTHLY_CAP` env (기본 1,500) — 한도 초과 시 silent skip

**호출 위치**:
- on-demand: Gap Analyzer 가 외부 DB 미커버 시 트리거 (콘텐츠당 24h 쿨다운)
- Daily Batch: 사전 정의 쿼리 ≤ 5개/일 (월 ~150)

**미설정 시**: `source="none"` 캐시 적재 후 silent skip (현재 동작 유지)

### 7.3 자동 확정 모니터링

`external_sync_log` 에 본 phase step1 마이그레이션으로 추가될 컬럼:
- `auto_resolved_count INT NULL DEFAULT 0` — 해당 sync 사이클에서 자동 확정된 field_resolution 수
- `manual_review_count INT NULL DEFAULT 0` — 검수 큐로 들어간 수

대시보드에 일별 추이를 노출해 false positive 발견 시 즉시 가드 조정.

### 7.4 잘못된 자동 확정 회수

발견 시:
1. 해당 `field_resolutions` 를 `decision=rejected, applied_to_content=false` 로 갱신
2. ContentMetadata 의 필드 복원
3. 원인 분석 → §5.5 임계 또는 §4 가중치 조정
4. 운영 노트에 케이스 기록

### 7.5 KMDb API 호출 절약

- on-demand 만 (Daily Beat 미등록)
- 한국 작품(country=KR) 에 한해 호출
- candidate 응답을 `metadata_candidates` 에 적재해 같은 작품 중복 호출 방지
