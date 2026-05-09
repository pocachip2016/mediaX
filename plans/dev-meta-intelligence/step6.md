# Step 6: field-strategy-catalog

> GitHub: 미생성 | Milestone: dev-meta-intelligence (Phase B — 골격, B 진입 시점에 상세화)

## 읽어야 할 파일
- `docs/dev/meta-intelligence.md` (§2 필드 5분류, §5 자동 확정 가드)
- `backend/api/meta_core/models/intelligence.py`

## 목적
필드별 결정 정책(자동/검수/머지)을 단일 카탈로그에 박는다.
Aggregator(step7) 와 검수 백엔드(step9) 가 모두 이 카탈로그만 참조.

## 작업 (윤곽)
- `backend/api/meta_core/field_strategy.py`
  - `FieldType` Enum: A_SINGLE, B_MULTI, C_TEXT, D_ASSET, E_EXTERNAL_ID
  - `FieldStrategy` dataclass: type, agree_threshold, weight_threshold, normalizer, source_priority, allow_llm_merge, max_auto, tolerance
  - `FIELD_STRATEGIES: dict[str, FieldStrategy]` — director/primary_genre/release_year/runtime/country/content_type (A), cast/secondary_genres/mood_tags (B), synopsis/description (C), poster/backdrop/stillcut (D), tmdb_id/kobis_id/kmdb_id (E)
- 정규화 함수
  - `person_norm`, `genre_norm`, `iso3166_norm`, `runtime_round` 등
  - 가능한 한 step2 scoring.py 의 normalize_* 재사용
- 단위 테스트: 분류별 1 케이스씩 (A 일치/불일치, B union, C pending, D quality_pick, E append)

## Acceptance Criteria
```bash
python3 -c "
from api.meta_core.field_strategy import FIELD_STRATEGIES, FieldType
assert FIELD_STRATEGIES['director'].type == FieldType.A_SINGLE
assert FIELD_STRATEGIES['cast'].type == FieldType.B_MULTI
assert FIELD_STRATEGIES['synopsis'].type == FieldType.C_TEXT
print('OK')
"
pytest backend/tests/meta_core/test_field_strategy.py
bash .claude/verify.sh meta-intelligence-step6
```

## 금지사항
- **DB 접근 금지.** 카탈로그·정규화 모두 순수 Python.
  이유: Aggregator/검수 백엔드 어디서나 부르는 라이브러리.
- **필드별 임계 직접 하드코딩 금지.** env override 가능한 한 가지 채널만 (`META_FIELD_THRESHOLD__<field>`).
  이유: 운영 중 조정.
