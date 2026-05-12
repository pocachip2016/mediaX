# Step 5: Content Add Flow + sources_aggregator

> GitHub: (미생성) | Milestone: dev-api-consolidation

## Context

신규 콘텐츠 등록 플로우의 4가지 엔드포인트를 구현한다:
1. 등록 전 외부 매칭 미리보기 (dry-run)
2. CSV 배치 dry-run
3. 외부 소스 통합 검색 (TMDB, KOBIS, KMDB, Watcha 병렬)
4. 매칭 결과 기반 콘텐츠 생성

이를 위해 sources_aggregator.py 신규 모듈을 작성한다.

## 읽어야 할 파일

- Step 0~4 완료 후: 스키마들, 모든 service/router
- `backend/api/programming/metadata/models/content.py` — ExternalMetaSource, Content
- 기존 TMDB/KOBIS/KMDB 클라이언트 코드

## 작업

### 1. 신규 모듈: `backend/api/programming/metadata/sources_aggregator.py`

```python
class SourcesAggregator:
    """TMDB, KOBIS, KMDB, Watcha 통합 검색."""
    
    async def search(
        self, 
        query: str, 
        sources: List[str]  # ['tmdb', 'kobis', 'kmdb', 'watcha']
    ) -> Dict:
        """
        병렬 호출 (asyncio.gather).
        단일 source 실패 시 다른 source 결과 반환 + errors[] 포함.
        각 결과: {title, year, director, source, match_percent, metadata}.
        """
        
        async def _search_tmdb(q): ...
        async def _search_kobis(q): ...
        # ...
        
        tasks = [_search_tmdb(query), _search_kobis(query), ...]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # ...
```

### 2. Service 함수: `backend/api/programming/metadata/service.py`

```python
async def enrich_preview(
    db: Session, content_id: int, fields: Optional[List[str]] = None
) -> Dict:
    """
    Content {content_id}를 외부 소스와 매칭 (dry-run).
    DB 변경 없음. enriched_fields + external_sources 반환.
    """

async def batch_preview(
    db: Session, 
    csv_data: List[Dict]
) -> BatchPreviewOut:
    """
    CSV dry-run.
    valid_count, missing_count, error_count, duplicate_count.
    actual processing은 하지 않음.
    """

async def sources_search(
    db: Session,
    query: str,
    sources: List[str]  # ['tmdb', 'kobis']
) -> SourceSearchOut:
    """SourcesAggregator 사용해서 병렬 검색."""

async def create_from_sources(
    db: Session,
    source_id: int,
    selected_fields: List[str],
    cp_name: str
) -> CreateFromSourcesOut:
    """
    ExternalMetaSource {source_id}에서 Content 생성.
    Content + ExternalMetaSource를 한번에 생성 (atomic).
    """
```

### 3. Routes: `backend/api/programming/metadata/router.py`

```python
@router.post("/metadata/contents/{tmp_id}/enrich")
async def api_enrich_preview(
    tmp_id: int, preview: bool = Query(False), db: Session = Depends(get_db)
):
    ...

@router.post("/metadata/upload/batch")
async def api_batch_preview(csv_data: List[Dict], preview: bool = Query(False)):
    ...

@router.get("/metadata/sources/search")
async def api_sources_search(
    q: str = Query(...),
    sources: str = Query("tmdb,kobis"),  # 쉼표 구분
    db: Session = Depends(get_db)
):
    source_list = [s.strip() for s in sources.split(",")]
    ...

@router.post("/metadata/contents/from_sources", response_model=CreateFromSourcesOut)
async def api_create_from_sources(req: CreateFromSourcesRequest, db: Session = Depends(get_db)):
    ...
```

### 4. 테스트: `backend/tests/api/programming/metadata/test_dev_api_consolidation_add_flow.py`

- enrich_preview: dry-run 확인 (DB 변경 없음)
- batch_preview: CSV 분석 통계
- sources_search: 병렬 호출, 단일 source 실패 시 다른 결과 포함
- create_from_sources: Content + ExternalMetaSource 생성 (atomic)

## Acceptance Criteria

```bash
cd backend
bash .claude/verify.sh dev-api-step5
# 또는
pytest tests/api/programming/metadata/test_dev_api_consolidation_add_flow.py -v

# 통합 검증
curl http://localhost:8000/openapi.json | jq '.paths | keys' | grep metadata
# → 18개 신규 경로 확인
```

## 금지사항

- sources search는 병렬 호출 필수 (asyncio.gather)
- preview=true 시 DB write 절대 금지
- batch preview는 실제 처리 금지 (count만 반환)
- 기존 quota cache 시스템 재사용 필수 (rate limit)
