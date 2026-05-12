# Step 0: Schemas + Foundation

> GitHub: (미생성) | Milestone: dev-api-consolidation

## Context

18개 엔드포인트의 요청/응답 스키마를 정의하고 기존 모델들이 제대로 import 되는지 검증한다. 
이후 Step 1~5에서는 이 스키마들을 route handler와 service function에서 사용하게 된다.

## 읽어야 할 파일

- `backend/api/programming/metadata/models/content.py` — 기존 모델 (Content, ContentAIResult, ExternalMetaSource, ContentBatchJob 등)
- `backend/api/programming/metadata/schemas.py` — 기존 스키마 (ContentOut, ContentDetailOut 등)
- `docs/dev/ui-consolidation/03_content_add.md`, `04_content_detail.md`, `05_bulk_action.md` — 18개 엔드포인트 스펙

## 작업

`backend/api/programming/metadata/schemas.py`에 아래 ~15개 Pydantic 모델을 추가한다. 기존 방식 따르기 (BaseModel from pydantic, Config 클래스 with orm_mode=True).

### Content Add Flow (4개)
- `EnrichPreviewRequest` — body: `{fields: List[str] | None}`, query: `preview=bool`
- `EnrichPreviewOut` — `{enriched_fields: Dict[str, Any], external_sources: List[ExternalMetaSourceOut], errors: List[str] | None}`
- `BatchPreviewOut` — `{valid_count: int, missing_count: int, error_count: int, duplicate_count: int, estimated_cost: str, estimated_duration_seconds: int}`
- `SourceSearchOut` — `{results: List[{title: str, year: int, source: str, match_percent: float, metadata: Dict}], errors: List[str] | None}`
- `CreateFromSourcesRequest` — `{source_id: int, selected_fields: List[str], cp_name: str}`
- `CreateFromSourcesOut` — `{id: int, title: str, status: str}`

### Content Detail (6개)
- `PromoteAIResultRequest` — `{ai_result_id: int}`
- `PromoteAIResultOut` — `{id: int, is_final: bool}`
- `PartialReprocessRequest` — query param: `fields=synopsis,genre,...`
- `ApplyExternalFieldsRequest` — `{source_id: int, fields: List[str]}`
- `ContentChangelogOut` — `{changes: List[{field: str, old_value: Any, new_value: Any, changed_by: str, changed_at: datetime}]}`
- `LockFieldsRequest` — `{fields: List[str], reason: str | None}`

### Bulk Actions (8개)
- `BulkActionRequest` — `{ids: List[int], reason: str | None, filter_query: dict | None}`
- `BulkActionResponse` — `{job_id: str, ids_accepted: int, ids_rejected: int, errors: List[str] | None}`
- `JobStatusOut` — ContentBatchJob 필드 + `progress_percent: int` (계산 필드)
- `RetryFailedRequest` — `{}`
- `UndoActionRequest` — `{action_id: str}`
- `UndoActionOut` — `{id: int, status: str, reverted_count: int}`

### 핵심 불변 규칙

1. 모든 스키마는 `Config.orm_mode = True`로 SQLAlchemy 모델과 호환
2. `*Out` 스키마는 response_model 용 — List, Optional 등 수정 가능
3. errors 필드는 항상 `List[str] | None`로 통일
4. datetime은 ISO8601 문자열로 직렬화
5. Float 필드 (match_percent, progress_percent)는 0-100 범위

## Acceptance Criteria

```bash
cd backend
pytest tests/api/programming/metadata/test_dev_api_consolidation_schemas.py -v
# → 모든 스키마 직렬화 테스트 통과
python -c "from api.programming.metadata.schemas import *; print('OK')"
# → import 성공
```

## 금지사항

- 기존 스키마 수정 금지. 신규 모델만 추가
- Pydantic v2의 Field() 사용 금지 — 기존 코드 style 유지 (Config 클래스)
