│ “내부 메타 DB를 기준으로, 외부 소스들을 결합해 보강하고, 신규
│ 콘텐츠 발견 시 SEED 후보를 자동 생성하는 메타 인텔리전스
│ 시스템”

즉 단순 수집기가 아니라:

1. 기존 DB 보완
2. 외부 사이트/DB 통합
3. 신규 콘텐츠 감지
4. 메타 후보 생성
5. 신뢰도 점수화
6. 관리자 승인 또는 자동 반영

이 구조야.

────────────────────────────────────────────────────────────────

1. 핵심 개념

### 기존 메타 DB

이미 가지고 있는 콘텐츠 데이터.

```text
  내부 content_id
  제목
  장르
  출연진
  감독
  회차
  포스터
  방영일
  서비스 노출 정보
```

### 외부 수집 메타

여러 사이트에서 가져오는 후보 데이터.

```text
  TVING
  WATCHA
  iMBC
  SBS
  TMDB
  KMDb
  KOBIS
  TVDB
  검색 결과
  뉴스/편성 페이지
```

### SEED

아직 내부 DB에 없거나 불완전한 신규 콘텐츠 후보.

예:

```json
  {
    "seed_id": "seed_20260509_0001",
    "title": "신규 드라마 제목",
    "type": "series",
    "source": "TVING",
    "evidence_urls": ["https://..."],
    "confidence": 0.82,
    "status": "pending_review"
  }
```

────────────────────────────────────────────────────────────────

2. 전체 구조

```text
  [기존 메타 DB]
          ↓
  [Gap Analyzer]
    누락/불완전 필드 탐지

          ↓
  [Source Planner]
    어떤 소스에서 보완할지 결정

          ↓
  [Collectors]
    공식 DB / 허용 웹사이트 / sitemap / WebSearch

          ↓
  [Candidate Extractor]
    콘텐츠 후보, 포스터, 회차, 인물, 날짜 추출

          ↓
  [Resolver]
    기존 content_id와 매칭
    신규면 SEED 생성

          ↓
  [Confidence Scoring]
    신뢰도 계산

          ↓
  [Review Queue]
    자동 반영 / 수동 검수 / 보류

          ↓
  [내부 메타 DB 보완]
```

────────────────────────────────────────────────────────────────

3. 데이터 흐름을 두 갈래로 나누자

### A. 기존 DB 보완 플로우

이미 있는 콘텐츠를 더 풍부하게 만드는 플로우.

```text
  내부 DB에서 누락 필드 확인
  → 제목/연도/외부 ID 기준으로 외부 소스 검색
  → 후보 메타 수집
  → 기존 콘텐츠와 매칭
  → 필드별 신뢰도 계산
  → 업데이트 제안
```

예:

```json
  {
    "content_id": "ct_123",
    "missing_fields": ["poster", "cast", "episode_count"],
    "suggestions": {
      "poster": {
        "value": "https://...",
        "source": "TMDB",
        "confidence": 0.91
      },
      "cast": {
        "value": ["김수현", "김지원"],
        "source": "TVING+iMBC",
        "confidence": 0.87
      }
    }
  }
```

### B. 신규 콘텐츠 SEED 플로우

아직 내부 DB에 없는 콘텐츠를 발견하는 플로우.

```text
  신규/인기/예정 페이지 수집
  → 제목 후보 추출
  → 내부 DB 중복 검사
  → 외부 DB 매핑 시도
  → 충분히 신뢰되면 SEED 생성
```

예:

```json
  {
    "seed_type": "new_content",
    "title_ko": "새 드라마",
    "type": "series",
    "first_seen_source": "TVING",
    "other_sources": ["WebSearch", "iMBC"],
    "matched_external_ids": {
      "tmdb": "..."
    },
    "confidence": 0.78,
    "recommended_action": "review"
  }
```

────────────────────────────────────────────────────────────────

4. SEED 생성 전략

SEED는 2가지 방식으로 나누는 게 좋아.

### 1) WebSearch 기반 SEED

신규 콘텐츠 발견에 강함.

사용처:

- 아직 TMDB/KMDb에 없는 콘텐츠
- 예정작
- 편성 예정 프로그램
- OTT 오리지널
- 보도자료 기반 콘텐츠

검색 쿼리 예:

```text
  site:tving.com 신규 드라마
  site:imbc.com 새 프로그램
  2026 신규 예능 출연진 방송일
  넷플릭스 한국 오리지널 2026 공개 예정
```

결과에서 추출:

```text
  제목
  방영/공개일
  플랫폼
  출연진
  제작사
  장르
  근거 URL
```

장점:
- 빠르게 신규 콘텐츠를 찾음

단점:
- 노이즈 많음
- 제목 오인식 가능
- 반드시 검증 필요

그래서 WebSearch SEED는 기본적으로 pending_review가 맞아.

────────────────────────────────────────────────────────────────

### 2) 사전 DB 메타화 기반 SEED

안정성에 강함.

외부 DB/사이트를 주기적으로 수집해 “후보 DB”를 미리 만들어둠.

```text
  TMDB upcoming
  KOBIS 개봉 예정
  KMDb 신규 등록
  TVING 신작
  iMBC 프로그램
  SBS 신규 프로그램
```

이걸 내부 후보 테이블에 쌓아두고, 내부 DB와 매칭되지 않은 항목을
SEED로 제공.

장점:
- 정제된 후보 제공 가능
- 중복 제거 쉬움
- 반복 검색 비용 감소

단점:
- 신규성은 WebSearch보다 약할 수 있음

────────────────────────────────────────────────────────────────

5. 추천 운영 방식

둘 다 쓰되 역할을 분리하자.

```text
  사전 DB 메타화 = 기본 SEED 공급원
  WebSearch = 신규/누락/검증 보조
```

즉:

```text
  Daily Batch:
    외부 DB/사이트 수집 → 후보 DB 갱신 → SEED 생성

  On-demand:
    내부 DB에 없거나 메타 부족 → WebSearch로 보완 검색
```

────────────────────────────────────────────────────────────────

6. 신뢰도 점수 설계

이 시스템의 품질은 confidence가 좌우해.

```text
  confidence =
    0.30 * title_match
  + 0.20 * year_or_airdate_match
  + 0.15 * cast_director_match
  + 0.15 * multi_source_agreement
  + 0.10 * external_id_match
  + 0.05 * source_reliability
  + 0.05 * image_asset_quality
```

자동 반영 기준 예:

```text
  0.90 이상 → 자동 반영 가능
  0.70 ~ 0.89 → 관리자 검수
  0.50 ~ 0.69 → 후보 보류
  0.50 미만 → 폐기 또는 재검색
```

단, 신규 SEED는 0.90 이상이어도 처음엔 검수 권장이야.
오탐이 한번 들어가면 DB가 지저분해져.

────────────────────────────────────────────────────────────────

7. MVP 범위 재정의

포카칩 목표 기준 MVP는 이렇게 잡는 게 좋아.

### MVP 1: 기존 DB 보완

목표:

│ 기존 콘텐츠에 대해 누락된 포스터/외부ID/출연진/설명/방영일을
│ 보완 후보로 제공한다.

소스:

- TMDB
- KMDb/KOBIS
- TVING
- iMBC
- WATCHA

기능:

- 내부 DB import
- content_id 기준 보완 대상 추출
- 외부 후보 검색
- 매칭 점수 계산
- 보완 제안 API
- 검수 UI

────────────────────────────────────────────────────────────────

### MVP 2: 신규 콘텐츠 SEED

목표:

│ 내부 DB에 없는 신규 콘텐츠 후보를 자동 생성한다.

소스:

- TVING 신작/인기
- iMBC 프로그램
- SBS 모바일
- TMDB upcoming/trending
- KOBIS 개봉 예정
- WebSearch 보조

기능:

- 신규 후보 탐지
- 내부 DB 중복 검사
- external_id 매핑
- seed queue 생성
- 관리자 승인 후 content 생성

────────────────────────────────────────────────────────────────

8. 테이블 구조 초안

```text
  contents
  content_external_ids
  content_titles
  content_people
  episodes
  assets
  providers
  provider_availability

  source_items
  source_snapshots
  metadata_candidates
  field_suggestions
  seed_candidates
  match_edges
  review_tasks
```

특히 중요한 건 이 4개야.

### source_items

외부에서 발견한 원본 항목.

```json
  {
    "source": "tving",
    "source_item_id": "xxx",
    "url": "https://...",
    "raw_title": "눈물의 여왕",
    "raw_payload": {}
  }
```

### metadata_candidates

정규화된 후보 메타.

```json
  {
    "candidate_id": "cand_001",
    "source_item_id": "src_001",
    "title_ko": "눈물의 여왕",
    "type": "series",
    "cast": ["김수현", "김지원"],
    "poster_url": "https://..."
  }
```

### match_edges

후보와 내부 콘텐츠의 매칭 관계.

```json
  {
    "candidate_id": "cand_001",
    "content_id": "ct_001",
    "score": 0.92,
    "reason": ["title_exact", "cast_overlap", "airdate_match"]
  }
```

### seed_candidates

신규 콘텐츠 후보.

```json
  {
    "seed_id": "seed_001",
    "candidate_id": "cand_001",
    "status": "pending_review",
    "confidence": 0.81,
    "reason": ["not_found_in_internal_db", "seen_in_2_sources"]
  }
```

────────────────────────────────────────────────────────────────

9. 다음 설계 질문

이제 가장 먼저 정해야 하는 건 기존 메타 DB의 형태야.

포카칩, 현재 가지고 있는 메타 DB는 어떤 상태야?

1. DB가 이미 있음
    - MySQL / PostgreSQL / MongoDB / Elasticsearch 등
2. 엑셀/CSV/JSON 파일 형태
3. 아직 없음. 새로 구축 예정

그리고 기존 데이터에 최소한 어떤 필드가 있어?

예:

```text
  content_id
  title
  type
  year
  provider
  poster_url
  description
  cast
  episode
```
