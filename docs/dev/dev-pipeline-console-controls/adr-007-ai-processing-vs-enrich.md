# ADR-007: AI 처리 vs Enrich vs WebSearch — 메타 파이프라인 동작 재정의

**Status**: Accepted (2026-05-29 — 미해결 3건 결정 완료)
**Date**: 2026-05-29
**Phase**: dev-pipeline-console-controls / meta pipeline
**관련**: ADR-006(9-stage 파이프라인), [step0.md](../../../plans/dev-pipeline-console-controls/step0.md), [IMPROVEMENTS.md](../../../plans/dev-pipeline-console-controls/IMPROVEMENTS.md)

---

## Context

Pipeline Test Console을 수동 단계로 검증하던 중, "AI 처리"가 실제로 무엇을 하는지, Enrich·WebSearch·Scoring과 어떻게 다른지 경계가 불명확하다는 문제가 제기됐다. 코드를 정밀 조사한 결과 개념적 혼란이 확인됐다.

### 코드 근거 (현 구현)

| 동작 | 위치 | 실제 하는 일 | LLM | 외부 API |
|---|---|---|---|---|
| **AI 처리** | `ai_engine.process_content_ai` → `_generate_metadata_with_engine` | ① LLM이 **title에서 줄거리 200자+ 창작**(ai_engine.py:257) ② `_fetch_external_meta`로 TMDB/KOBIS 매칭 ③ `quality_score` 산정 | ①만 | ② |
| **Enrich** | `meta_core.enrich.enrich_content` | gap 분석 → TMDB/KMDB 검색 → MetadataCandidate·MatchEdge(유사도)·FieldSuggestion 적재 | NO | YES |
| **WebSearch** | `meta_core.aggregator._add_websearch_suggestions` (opt-in) | 빈 필드(synopsis/cast/director)를 Brave/SerpAPI/Gemini-grounding/Ollama-DDG로 grounded 검색 | provider 일부 | YES |
| **Discovery** | `meta_core.discovery.run_discovery` | DB에 **없는 신규 작품 발굴**(별개 레이어) | provider 일부 | YES |
| **Scoring** | `ai_engine._calculate_quality_score` / `meta_core.scoring.compute_match_score` | 완성도(0~100) / 유사도(0~1) — **결정론적 규칙** | NO | NO |

### 핵심 문제

1. **"AI 처리"가 인식론적으로 다른 셋을 뭉쳐놓음** — 창작(LLM) + 회수(외부매칭) + 채점(규칙).
2. **🔴 알려진 작품에도 LLM이 줄거리를 창작** — 기생충의 `ai_synopsis`는 LLM 환각 문장이고, TMDB의 권위 줄거리는 `tmdb_data`에 보관만 됨. 사실이 있는데 환각을 대표값으로 사용 = 메타 시스템 역설.
3. **외부 회수 로직 중복** — AI 처리(`_fetch_external_meta`)와 Enrich가 둘 다 TMDB/KOBIS 조회.
4. **점수가 AI가 아님** — `ai_engine`에 있지만 순수 규칙. 이름이 실제를 오도.
5. **단계 순서 역전** — 현재 카드 순서 ①생성 ②AI처리 ③Enrich ④검수. 그런데 AI처리(창작)가 회수(Enrich)보다 **앞**에 와서, 사실을 회수하기 전에 환각부터 생성. `process_content_ai`가 staging을 건너뛰고 review로 직행하는 것도 이 순서 혼란의 증상.

### 시스템 지향점

`meta_core`(gap→candidate→MatchEdge→FieldSuggestion→provenance)·ADR-006 게이트·검수 큐의 성숙도로 볼 때, 이 시스템의 지향은 **"출처 기반·검색 우선(retrieval-first)·사람이 검수하는 증거 파이프라인"**이다. `process_content_ai`의 LLM 줄거리 생성은 초기 MVP(1.1) 잔재로 이 방향과 충돌한다.

---

## Decision

**원칙: 회수(retrieval)가 1순위. 생성(generation)은 최후수단이며 항상 출처 플래그를 단다. LLM은 "회수된 사실"을 변환·정제·확장하는 데 쓰고, 무에서 창작하지 않는다.**

### 재정의된 단계 순서

회수를 먼저, AI 정제를 검수 직전에 배치한다. (현 ②AI처리 ↔ ③Enrich **순서 교체**)

```
status: raw → enriched → ai → review → approved/rejected

① 생성 (raw)
   └ 시드/건별/대량 입력 → 콘텐츠 골격 생성, 미처리

② 회수·보강 (raw → enriched)    [기존 Enrich + WebSearch 통합]
   └ TMDB/KMDB/KOBIS 검색 → 후보·매칭·필드제안 (권위 사실 회수)
   └ 구조화 소스가 못 채운 빈 필드 → WebSearch grounded 보강
   └ 외부 조회는 전부 여기 한 곳으로 통합

③ AI 처리 (enriched → ai)        [재정의 — 회수 이후, 검수 이전]
   └ 입력 = ②에서 회수된 권위 데이터 (무에서 창작 아님)
   └ 정제: 과도하게 긴 줄거리 축약, 표기 정규화, 자유 장르 → taxonomy 매핑
   └ 확장: 회수 사실 기반 확장 AI 메타 생성(요약/무드/키워드/카피 등)
   └ 소스 전무 시에만 LLM 창작 + source=ai_generated·unverified 플래그(검수 강제)

④ 검수 (ai → review → approved/rejected)
   └ 운영자가 ③ 산출물 확인·승인
```

### Status enum 재명명 (결정)

기존 `waiting → processing → staging → review`를 파이프라인 실제 순서에 맞춰 재명명한다 (마이그레이션 필요).

| 기존 | 신규 | 의미 |
|---|---|---|
| `waiting` | **`raw`** | 생성됨, 미처리 |
| `staging` | **`enriched`** | 회수·보강 완료 |
| `processing` | **`ai`** | AI 정제·확장 완료 |
| `review` | `review` | 검수 대기 (유지) |
| `approved`/`rejected` | 유지 | 최종 |

순서: `raw → enriched → ai → review`. (AI가 회수 **뒤**로 이동한 것이 enum 순서에도 반영됨)

### AI 처리 확장·정제 메타 항목 (결정)

모든 AI 동작은 **grounding**(회수 사실을 입력 제공)으로 환각을 억제한다. AI 로직 4종: 요약 / 분류 / 추출 / 생성.

| 항목 | AI 로직 | 입력(grounding) | 출력 | 환각 통제 | Phase |
|---|---|---|---|---|---|
| **short_synopsis** (카드 요약) | 요약(abstractive·길이제한) | 회수 full synopsis | ≤100자 | 입력 사실 압축만 | 1 |
| **genre_normalized** | 분류(taxonomy 매핑) | 회수 장르 텍스트/코드 | 내부 `GENRES` 코드 | 통제 어휘 강제 | 1 |
| **mood_tags** | 분류(multi-label) | 정제 synopsis | `MOOD_TAGS` 3~5 | 통제 어휘 강제 | 1 |
| **keywords/themes** | 추출(grounded) | 정제 synopsis | 키워드 N개(검색·추천) | 입력 내 추출만 | 1 |
| **tagline** (한 줄 카피) | 생성(grounded) | 회수 synopsis+장르 | ≤30자 | `ai_generated`+검수 강제 | 2 |
| **rating/audience 제안** | 분류 | 회수 데이터+synopsis | 등급 후보(제안) | 확정은 검수 | 2 |

- **요약**: 회수 긴 줄거리 → "이 내용만으로 N자 압축", 새 사실 금지.
- **분류**: 출력을 통제 어휘로 제한 → 어휘 밖 값 불가(최저 위험).
- **추출**: 입력 텍스트에 등장하는 것만.
- **생성**: 유일한 창작 — 회수 위에서 카피 작성 + 미검증 플래그 필수.

### 설정 on/off · provider 확장 · quota (결정)

- **항목별 on/off**: ③ AI 처리의 각 메타 항목(short_synopsis/genre_normalized/mood_tags/keywords/tagline/rating)과 ② WebSearch 보강은 **개별 토글**. 설정은 1차 패널 로컬, 추후 서버 정책으로 승격.
- **provider API 확장**: LLM은 기존 `AI_ENGINE` 체인(gemini/groq/ollama, `llm/` 패키지의 `AbstractLLMProvider`), WebSearch는 기존 체인(brave/serpapi/gemini-grounding/ollama-ddg, `web_search/factory.py`)을 **그대로 확장점으로 사용**. 신규 provider는 추상 클래스 구현 + factory 등록만으로 추가.
- **quota/cost**: 모든 외부 LLM·WebSearch 호출은 기존 QuotaManager(ADR quota-cache) 경유. AI 산출물은 **콘텐츠+항목+입력해시 키로 캐시**(idempotent) → 동일 입력 재처리 시 호출 스킵. 항목별 토큰/호출 비용 집계.

### 각 동작의 확정 정의

| 동작 | 정의 | LLM 역할 |
|---|---|---|
| **회수(Enrich)** | 권위 외부 소스(TMDB/KMDB/KOBIS)에서 사실을 검색·매칭해 후보/제안으로 적재 | 없음 |
| **WebSearch** | 구조화 소스 공백을 웹에서 grounded 보강 (회수의 일부) | grounding |
| **AI 처리** | 회수된 데이터를 **검수용으로 변환·정제·확장**. 긴 줄거리 축약, 정규화, 확장 메타 생성 | 변환/요약/확장 (창작 아님) |
| **생성(폴백)** | 어떤 소스에도 없을 때만 LLM 창작 + 미검증 플래그 | 명시적 격리 생성 |
| **Scoring** | 완성도/유사도 게이트 (`ai_` 네임스페이스에서 분리) | 없음 |

### 핵심 전환 3가지

1. **회수 우선**: 기생충 시놉시스 = TMDB 줄거리(필요 시 AI가 축약·정제), LLM 창작은 소스 없을 때만 + "AI생성·미검증" 표시.
2. **외부 조회 단일화**: `process_content_ai`의 `_fetch_external_meta` 제거 → 회수 단계(Enrich)로 통합. AI 처리는 회수 산출물 위에서만 동작.
3. **순서 정정**: 생성 → 회수(staging) → AI 정제/확장(processing) → 검수(review). AI가 회수보다 뒤로 이동.

---

## Consequences

### 코드 변경 함의 (후속 plan step에서 구체화)
- `process_content_ai`에서 LLM **창작** 로직과 `_fetch_external_meta` **회수** 로직 분리. 회수는 enrich로 이관.
- AI 처리 입력을 "회수된 데이터"로 바꾸고, 작업을 정제(축약/정규화)·확장으로 재정의.
- 콘솔 카드 ②↔③ 의미/순서 교체.
- `quality_score`/`_calculate_quality_score`를 `ai_` 네임스페이스에서 분리(명명 정리).

### Status enum 마이그레이션 (결정됨 → raw/enriched/ai/review)
`waiting→raw`, `staging→enriched`, `processing→ai` 재명명. alembic enum 값 변경 + 기존 행 값 변환 마이그레이션 필요. FE `ContentStatus` 타입·라벨·`STAGE_DEFS`·필터 전반 동기 수정.

### 검수 콘솔(dev-pipeline-console-controls) 반영
- ② 패널 = 회수(외부+WebSearch) 관찰/트리거.
- ③ 패널 = AI 정제/확장 관찰 — 사용 엔진/모델(`ollama:qwen3:4b`), 입력(회수데이터)→출력(축약/확장) diff, 점수 변화.
- IMPROVEMENTS #1·#2·#8·#9가 이 ADR로 근본 해소됨(자동 dispatch 가드, 단일 전이, bulk_process 의미 수정).

### 리스크
- 기존 `ai_synopsis`(창작본) 데이터의 의미 변경 — 마이그레이션/백필 시 출처 플래그 부여 필요.
- LLM 축약/확장 품질은 회수 데이터 품질에 종속 → 회수 실패 시 폴백 경로 명확화 필요.

---

## 결정 완료 (2026-05-29)
1. ✅ **Status enum 재명명** → `raw → enriched → ai → review → approved/rejected` (마이그레이션 필요).
2. ✅ **AI 메타 항목** → Phase1: short_synopsis(요약)·genre_normalized(분류)·mood_tags(분류)·keywords(추출) / Phase2: tagline(생성)·rating(분류). 로직·grounding 상기 표 참조.
3. ✅ **설정 on/off + provider 확장 + quota** → 항목별 토글, 기존 LLM/WebSearch provider 체인 확장점 재사용, QuotaManager 경유 + 입력해시 캐시.

## 남은 구현 결정 (후속 step 설계 시)
- AI 확장 메타 저장 스키마 — `content_metadata` 컬럼 추가 vs `content_ai_results` JSON vs 신규 테이블.
- 항목별 캐시 키 정의 (content_id + item + input_hash).
- enum 마이그레이션과 기존 `ai_synopsis`(창작본) 데이터의 출처 플래그 백필.
