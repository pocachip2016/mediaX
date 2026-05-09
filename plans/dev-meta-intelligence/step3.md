# Step 3: score-disambiguation

> GitHub: 미생성 | Milestone: dev-meta-intelligence (Phase A)

## 읽어야 할 파일
- `docs/dev/meta-intelligence.md` (§3 — 두 점수 정의)
- `backend/api/meta_core/scoring.py` (step2 산출 — match_score 모듈)
- `backend/api/programming/metadata/ai_engine.py` (현 `_calculate_quality_score`)
- `backend/api/programming/metadata/models/content.py` (ContentMetadata.quality_score / score_breakdown)
- `backend/api/programming/metadata/CLAUDE.md`

## 목적
`quality_score` 와 `match_score` 가 같은 이름으로 혼용되는 일을 막는 **명명·문서·로깅 정리** step.
실제 산식 변경 0건. 다음 step 들에서 두 개념이 섞이지 않게 가드만 친다.

## 작업

### 1. ai_engine 의 `_calculate_quality_score` 함수 docstring 보강
- 함수 위에 docstring 5~10줄 추가:
  - "콘텐츠 메타 완성도 점수 (0~100). 외부 후보와의 동일성 점수와 다름."
  - "동일성 비교는 `api.meta_core.scoring.compute_match_score` 참조."
- 변수명·로직 변경 금지.

### 2. `ContentMetadata.score_breakdown` JSON 키 컨벤션 명문화
- `models/content.py` 의 `score_breakdown` 컬럼 위에 한 줄 docstring:
  ```python
  # quality_score 의 분해. 키 고정: synopsis_completeness, genre_classification,
  # tag_count, external_meta, basic_fields_filled. (match_score 와 별도)
  ```

### 3. 신규 모듈 `api/meta_core/scoring.py` 의 docstring 보강
- 모듈 상단에 5~10줄:
  - "candidate ↔ Content 동일성 판정용 (0.0~1.0). 콘텐츠 메타 완성도와 다름."
  - "완성도는 `api.programming.metadata.ai_engine._calculate_quality_score`."

### 4. `backend/api/programming/metadata/CLAUDE.md` 갱신
- 한 섹션 추가 (Score Conventions, ~10줄):
  | 점수 | 정의 | 범위 | 위치 |
  |---|---|---|---|
  | quality_score | 콘텐츠 메타 완성도 | 0~100 | ContentMetadata.quality_score |
  | match_score | candidate↔Content 동일성 | 0.0~1.0 | MatchEdge.score |

### 5. `backend/api/meta_core/CLAUDE.md` 신설 (없으면)
- 60줄 이하. meta_core 디렉토리 역할 설명 + 위 표 + Phase B 까지의 모듈 위치 인덱스 (gap.py / scoring.py / field_strategy.py / aggregator.py / public_api/)
- 구현 미완료 모듈은 "(예정)" 표시.

### 6. 로깅 prefix 컨벤션
- `api.meta_core.*` 모듈은 logger prefix `[meta_core]`
- `_calculate_quality_score` 가 로그 찍는 곳이 있으면 prefix `[quality]`
- 두 prefix 가 grep 으로 명확히 구분되도록.
- 본 step 에서는 코드에 logger 추가 X — 컨벤션만 CLAUDE.md 에 적시.

## Acceptance Criteria
```bash
# 1. 두 위치 docstring 존재
grep -q "동일성" backend/api/programming/metadata/ai_engine.py
grep -q "완성도" backend/api/meta_core/scoring.py

# 2. CLAUDE.md 두 곳에 표
grep -q "match_score" backend/api/programming/metadata/CLAUDE.md
grep -q "match_score" backend/api/meta_core/CLAUDE.md

# 3. 산식 미변경 확인 (quality_score 함수 내용 hash 가 step 전후 동일해야 함)
# 본 step 에서는 _calculate_quality_score 의 docstring 만 추가. 함수 본체 라인 변경 0.

# 4. /verify
bash .claude/verify.sh meta-intelligence-step3
```

## 금지사항
- **`_calculate_quality_score` 산식·변수명·반환값 변경 금지.** docstring 한정.
  이유: production 점수 의미 보존.
- **DB 마이그레이션 금지.** score_breakdown 키 변경도 X.
  이유: 본 step 은 명명/문서 정리. 데이터 의미 변경은 별도 task.
- **logger 호출 추가 금지.** 컨벤션 문서화만.
  이유: 코드 변경 면적 최소화.
- **api/meta_core/CLAUDE.md 60줄 초과 금지.** 모듈 인덱스 + 점수 표만.
  이유: 프로젝트 CLAUDE.md 컨벤션 (60줄 이하).
