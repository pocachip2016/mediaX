# Step 2: scoring-module

> GitHub: 미생성 | Milestone: dev-meta-intelligence (Phase A)

## 읽어야 할 파일
- `docs/dev/meta-intelligence.md` (§3 신뢰도 산식, §4 소스 신뢰도 가중치)
- `backend/api/meta_core/models/intelligence.py` (step1 산출 — MatchEdge.sub_scores_json 스키마)
- `backend/api/programming/metadata/ai_engine.py` (현재 quality_score 산정 — 참고만, 수정 X)

## 목적
candidate ↔ Content 동일성 판정용 `match_score` 산식을 단일 모듈에 격리.
Phase B step5 의 enrich 가 이 모듈을 호출해 MatchEdge 를 채운다.
**이 step 은 순수 계산 함수 + 단위 테스트만.** DB 접근 없음.

## 작업

### 1. `backend/api/meta_core/scoring.py` 신설

#### 1-1. 정규화 유틸 (모두 순수 함수)
```python
def normalize_title(s: str) -> str:
    """소문자 + 한글/영문/숫자만 남김 + 공백 단일화. 시즌·연도 표기 제거."""

def normalize_person_name(s: str) -> str:
    """성명 정규화. 영문 KMDb/TMDB 표기 차이 흡수."""

def title_score(a: str, b: str) -> float:
    """0.0~1.0. exact(1.0) / token_set_ratio (0.7~) / 한자·로마자 변형 고려."""

def year_score(a: int | None, b: int | None) -> float:
    """동일 1.0 / ±1년 0.7 / 그 외 0.0. None 둘 중 하나면 0.5 (중립)."""

def cast_overlap_score(cast_a: list[str], cast_b: list[str]) -> float:
    """jaccard. 최대 top-10 만 비교. 빈 리스트 한쪽이면 0.0."""

def external_id_score(ids_a: dict, ids_b: dict) -> float:
    """동일 source 의 id 일치 시 1.0, 일치 없음 0.0, 비교 불가 None→0.0."""

def source_reliability(source_type: str) -> float:
    """env META_SOURCE_WEIGHT__<source> 우선, 없으면 기본 표 (TMDB 1.0 / KOBIS 0.95 / KMDb 0.95 / WATCHA 0.80 / WebSearch 0.50 / other 0.5)."""
```

#### 1-2. 메인 함수
```python
@dataclass
class MatchScoreBreakdown:
    title: float
    year: float
    cast: float
    multi_source: float
    external_id: float
    source_reliability: float
    image: float

@dataclass
class MatchScoreResult:
    score: float                    # 0.0~1.0
    breakdown: MatchScoreBreakdown
    reasons: list[str]              # ["title_exact", "year_match", "cast_overlap"]

def compute_match_score(
    candidate: dict,                 # MetadataCandidate row → dict
    content: dict,                   # Content + ContentMetadata join → dict
    *,
    other_candidates: list[dict] = None,  # multi_source 산정용 (같은 content 의 다른 source candidate들)
) -> MatchScoreResult:
    """
    가중치 (ADR §3):
        title 0.30 + year 0.20 + cast 0.15 + multi_source 0.15
      + external_id 0.10 + source_reliability 0.05 + image 0.05

    reasons: 각 sub-score >= 0.7 일 때 "<field>_match" 추가.
    """
```

#### 1-3. 임계 분류
```python
def classify_match(score: float) -> Literal["auto", "review", "hold", "drop"]:
    """
    score >= 0.90 → auto
    0.70 ~ 0.89  → review
    0.50 ~ 0.69  → hold
    < 0.50       → drop
    """
```

### 2. 단위 테스트 — `backend/tests/meta_core/test_scoring.py`
- 동일 작품 3 시나리오 (title 완전 일치 / 변형 / 다른 작품) 각 score 검증
- year_score: None / ±1년 / 동일 / 다른 4 케이스
- cast_overlap_score: 완전 일치 / 50% / 0% 3 케이스
- compute_match_score: TMDB candidate vs DB Content 한 케이스 — score >= 0.85 검증
- classify_match 4 임계 경계값

테스트 의존성: pytest 만 (fixture 없이 dict 리터럴로 충분)

### 3. 환경변수 문서화
`backend/.env.example` 에 추가:
```
META_SOURCE_WEIGHT__TMDB=1.00
META_SOURCE_WEIGHT__KOBIS=0.95
META_SOURCE_WEIGHT__KMDB=0.95
META_SOURCE_WEIGHT__WATCHA=0.80
META_SOURCE_WEIGHT__WEBSEARCH=0.50
```
(미설정 시 코드 기본값 사용)

## Acceptance Criteria
```bash
# 1. 테스트 통과
cd backend && pytest tests/meta_core/test_scoring.py -v

# 2. 동일 작품 매칭 smoke
python3 -c "
from api.meta_core.scoring import compute_match_score, classify_match
cand = {'title_norm':'tears of the queen','year':2024,'cast_json':['김수현','김지원'],'source_type':'tmdb','external_ids_json':{'tmdb':'1234'}}
content = {'title':'눈물의 여왕','production_year':2024,'cast':['김수현','김지원'],'external_ids':{'tmdb':'1234'}}
r = compute_match_score(cand, content)
assert r.score >= 0.85, f'expected high match, got {r.score}'
assert classify_match(r.score) == 'auto'
print('OK', r.score)
"

# 3. /verify
bash .claude/verify.sh meta-intelligence-step2
```

## 금지사항
- **DB 접근 금지.** 순수 함수 + dict 입출력만.
  이유: scoring 모듈은 Aggregator·enrich·테스트 어디서든 부르는 라이브러리. DB 엮으면 테스트 못 함.
- **fuzzy match 라이브러리 추가 금지** (rapidfuzz 등).
  이유: 한국어 토큰화 특성상 외부 라이브러리가 오히려 노이즈. 내장 difflib + token set 으로 충분.
- **MatchEdge row 생성 금지.** 본 step 은 함수만. row 생성은 step5 enrich.
  이유: scoring 과 persistence 분리.
- **`quality_score` 코드 손대지 마라.** 산식·이름·필드 모두 그대로.
  이유: ADR §3 — 두 점수는 다른 축. 충돌 방지.
