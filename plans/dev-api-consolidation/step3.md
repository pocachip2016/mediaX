# Step 3: Content Detail — Simple (promote/process/apply)

> GitHub: (미생성) | Milestone: dev-api-consolidation

## Context

Content 상세 페이지에서 3가지 동작을 구현한다:
1. AI 결과 채택 (is_final 토글)
2. 특정 필드만 재처리
3. 외부 소스에서 필드 선택 적용

모두 동기 처리 (즉시 완료).

## 읽어야 할 파일

- Step 0~2 완료 후: 스키마들
- `backend/api/programming/metadata/models/content.py` — Content, ContentAIResult, ExternalMetaSource
- `backend/api/programming/metadata/service.py` — 기존 service 패턴

## 작업

### 1. Service 함수: `backend/api/programming/metadata/service.py`

```python
async def promote_ai_result(db: Session, content_id: int, ai_result_id: int) -> PromoteAIResultOut:
    """
    ContentAIResult.is_final = True.
    기존 is_final인 다른 결과는 False로 변경.
    Content.final_* 컬럼들을 이 결과로 동기화.
    """

async def partial_reprocess(db: Session, content_id: int, fields: List[str]) -> JobStatusOut:
    """
    fields = ['synopsis', 'genre', 'tags', ...] (화이트리스트)
    AI 재처리하되, 지정된 필드만 갱신.
    locked_fields에 포함된 필드는 제외 (Step 4에서 추가).
    현재는 locked_fields 체크 없음 — Step 4 retrofit 필요.
    """

async def apply_external_fields(
    db: Session, content_id: int, source_id: int, fields: List[str]
) -> Dict[str, Any]:
    """
    ExternalMetaSource.body['fields'][field] → Content[field]에 적용.
    locked_fields 체크 없음 (Step 4 retrofit).
    """
```

### 2. Routes: `backend/api/programming/metadata/router.py`

```python
@router.post("/contents/{id}/ai-results/{result_id}/promote", response_model=PromoteAIResultOut)
async def api_promote_ai_result(id: int, result_id: int, db: Session = Depends(get_db)):
    ...

@router.post("/contents/{id}/process")
async def api_partial_reprocess(
    id: int, fields: str = Query(""),  # 쉼표 구분: "synopsis,genre"
    db: Session = Depends(get_db)
):
    field_list = [f.strip() for f in fields.split(",") if f.strip()]
    return await partial_reprocess(db, id, field_list)

@router.post("/contents/{id}/external/{source_id}/apply-fields", response_model=Dict)
async def api_apply_external_fields(
    id: int, source_id: int, req: ApplyExternalFieldsRequest, db: Session = Depends(get_db)
):
    ...
```

### 3. 테스트: `backend/tests/api/programming/metadata/test_dev_api_consolidation_detail_simple.py`

- promote: is_final toggle 확인, 기존 is_final reset 확인
- partial_reprocess: 화이트리스트 검증, 지정 필드만 갱신
- apply_external_fields: source 데이터 → content 필드 적용

## Acceptance Criteria

```bash
cd backend
bash .claude/verify.sh dev-api-step3
# 또는
pytest tests/api/programming/metadata/test_dev_api_consolidation_detail_simple.py -v
```

## 금지사항

- locked_fields 로직은 아직 구현 금지 (Step 4 retrofit)
- promote 시 다른 ai_result들의 is_final 일괄 False 처리 필수
- 화이트리스트 필드: ['synopsis', 'genre', 'tags', 'cast', 'director', 'production_year'] 정도로 제한
