# Step 0: adr-meta-intelligence

> GitHub: 미생성 | Milestone: dev-meta-intelligence (Phase A)

## 읽어야 할 파일
- `backend/crosscheck.md` (설계 원본)
- `backend/api/programming/metadata/models/external.py` (현 ExternalSourceType ENUM)
- `backend/api/programming/metadata/ai_engine.py` (현 quality_score 산식)
- `docs/sync-architecture.md` (있으면 — Dam 연동 경계)

## 목적
이 phase 의 모든 코드 변경은 ADR 문서에 정의된 개념·정책·필드 분류를 따른다.
ADR 없이 마이그레이션부터 들어가면 다음 step 에서 의미 다툼이 일어나므로,
**먼저 한 곳에 박아두는 것** 이 이 step 의 유일한 목적.

## 작업

### 1. `docs/dev/meta-intelligence.md` 신설

다음 섹션을 모두 포함 (각 섹션 분량 가이드: 30~80줄):

#### §1 용어 정의 (5단계)
- `source_item` — 외부 소스 raw 1건
- `metadata_candidate` — source_item 정규화 결과 (1 source_item → 1 candidate 원칙)
- `field_suggestion` — candidate 에서 필드 단위로 쪼갠 후보값 (1 candidate → N suggestions)
- `match_edge` — candidate ↔ 내부 Content 매칭 (점수 + 사유)
- `seed_candidate` — 매칭 실패한 candidate 의 신규 콘텐츠 후보화 (Phase C 에서 활성화)

각 용어마다 "이게 아닌 것" 도 한 줄 명시. 예: "candidate ≠ 매칭 확정. 매칭 확정은 ExternalMetaSource."

#### §2 필드 5분류 (Field Type Taxonomy)
| 분류 | 예시 | 정책 |
|---|---|---|
| A. 단일값·이산 | director, primary_genre, release_year, runtime, country, content_type | 2+ 소스 일치 → 자동 확정 |
| B. 다중값·이산 | cast, secondary_genres, mood_tags | 2+ 소스 등장 멤버만 자동 채택 |
| C. 자유 텍스트 | synopsis, description | 검수자 pick / LLM merge / 원문 유지 |
| D. 자산 URL | poster, backdrop, stillcut | 품질 점수 1위 자동, 나머지 alternates |
| E. 외부 ID | tmdb_id, kobis_id, kmdb_id | 항상 모두 저장 (충돌 없음) |

#### §3 신뢰도 산식 (2축 분리)
- **`match_score`** (candidate ↔ Content 동일성)
  - 가중치: title 0.30 / year 0.20 / cast 0.15 / multi_source 0.15 / external_id 0.10 / source_reliability 0.05 / image 0.05
  - 임계: ≥0.90 자동매칭, 0.70~0.89 검수, 0.50~0.69 보류, <0.50 폐기
- **`quality_score`** (Content 메타 완성도) — 기존 산식 유지
- 두 점수는 **이름 충돌 금지**. ContentMetadata.quality_score 는 그대로, MatchEdge.score 는 별도.

#### §4 소스 신뢰도 가중치 (env 화)
```
TMDB     1.00
KOBIS    0.95   (한국 영화 박스오피스 1차 소스)
KMDb     0.95   (한국영상자료원 — 한국 작품 메타 풍부)
WATCHA   0.80
WebSearch (Brave/Serp) 0.50
```
환경변수 `META_SOURCE_WEIGHT__<source>` 로 override 가능.

#### §5 자동 확정 가드
- A 분류: `agree_threshold=2 AND 합산 source_weight ≥ 1.5` 동시 만족
- B 분류: 멤버별 등장 ≥ 2 sources, 단 cast 는 top-20 / secondary_genres top-3 cap
- D 분류: 품질 1위 자동, 단 source_priority=[tmdb, kmdb, kobis, cp] 동률 시 우선순위 적용
- 자동 확정도 `field_resolutions.applied_to_content=false` 로 되돌릴 수 있는 롤백 경로 보장

#### §6 KMDb 추가 (이번 phase 에서 신규 ENUM 멤버)
- `ExternalSourceType` 에 `kmdb` 추가 (마이그레이션 0011)
- `TmdbSyncSource` 에 `kmdb_daily`, `kmdb_backfill` 추가 (Phase B step5 에서 사용 시점에 alembic 보강)
- KMDb Open API 베이스: `http://api.kmdb.or.kr/openapi-data2/`, env: `KMDB_API_KEY`
- 영화 위주 (TV 약함) — 한국 영화 보강 채널로 사용

#### §7 비용·운영 가드
- LLM merge (Phase B6 의 synopsis 머지): on-demand 만, Daily 호출 금지
- 자동 확정 비율 모니터링: `external_sync_log` 에 `auto_resolved_count` 필드 검토 (step1 에서 추가 검토)
- 잘못된 자동 확정 발견 시 `field_resolutions.decision=rejected` + `applied_to_content=false` 롤백

### 2. CLAUDE.md 갱신
`backend/api/CLAUDE.md` 의 모듈 트리 설명에 `meta_core/` 항목 보강 (Phase B 까지 끝나면 추가될 파일 목록 미리 명시 안 함, 디렉토리 존재만 언급).

## Acceptance Criteria
- `docs/dev/meta-intelligence.md` 가 §1~§7 모두 포함하고 각 섹션이 30줄 이상
- 새 코드 0줄, 마이그레이션 0건. **문서 step**
- 검증:
```bash
test -f docs/dev/meta-intelligence.md && \
  grep -q "field_suggestion" docs/dev/meta-intelligence.md && \
  grep -q "match_score" docs/dev/meta-intelligence.md && \
  grep -q "kmdb" docs/dev/meta-intelligence.md
```
- `/verify --skip "ADR 문서 step (코드 변경 없음)"` 로 통과 처리

## 금지사항
- **코드 수정 금지.** 다음 step 에서 마이그레이션 시작.
  이유: ADR 이 다음 모든 step 의 reference 라 먼저 박혀야 함.
- **API 키 발급/외부 호출 금지.** KMDb 키 신청은 Phase B step5 직전에.
  이유: 발급된 키가 미사용 상태로 환경에 떠있는 시간을 줄임.
- **기존 quality_score 산식 변경 금지.** Phase A step3 에서 분리만 정리.
  이유: production 운영 중인 점수 — 의미 변경은 이력 호환성 깨짐.
