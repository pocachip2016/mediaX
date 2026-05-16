# Step 1: 백엔드 /ai-review-queue 계산형 API

## 목적
검수 화면이 `/queue`·`/staging`·`/recommendations`·`/poster-candidates`·`/dam-assets`를 직접 조합하지 않도록 단일 queue row API 제공. **신규 테이블은 만들지 않는다** — 모두 계산형.

## 응답 스키마
`backend/api/programming/metadata/schemas.py` (append):

```python
class AiReviewQueueRow(BaseModel):
    content_id: int
    title: str
    content_type: str
    input_type: Literal["bulk", "manual", "existing"]
    content_status: str
    metadata_status: Literal["missing", "conflict", "enhancement", "clean"]
    poster_status: Literal["poster_ok", "needs_selection", "dam_match_found", "external_only", "no_candidate"]
    dam_match_count: int = 0          # include_dam=false 일 때 0
    risk_level: Literal["low", "medium", "high"]
    confidence: float                  # 0.0~1.0
    updated_at: datetime

class AiReviewQueueSummary(BaseModel):
    total: int
    missing: int
    conflict: int
    needs_poster: int
    dam_match: int
    high_risk: int

class PaginatedAiReviewQueue(BaseModel):
    items: list[AiReviewQueueRow]
    summary: AiReviewQueueSummary
    total: int
    page: int
    size: int
```

## 분류 헬퍼 (service.py)

```python
def _classify_input_type(content, db) -> str:
    """bulk: ContentBatchJob 매핑 존재.
       manual: ExternalMetaSource(source_type='manual' or 'bulk_upload') 만 존재.
       existing: 그 외 (TMDB/Watcha/KOBIS 등 외부 소스 보유)."""

def _classify_metadata_status(rec_out: RecommendationsOut) -> str:
    if rec_out.conflicts: return "conflict"
    if rec_out.missing_fields: return "missing"
    if rec_out.auto_fill: return "enhancement"
    return "clean"

def _classify_poster_status(images: list[ContentImage], dam_count: int) -> str:
    primary = next((i for i in images if i.is_primary), None)
    if not images: return "no_candidate"
    if dam_count > 0 and not primary: return "dam_match_found"
    if primary and primary.source not in ("tmdb",): return "poster_ok"
    if primary and primary.source == "tmdb": return "external_only"
    return "needs_selection"

def _risk_level(metadata_status, poster_status, confidence) -> str:
    if metadata_status == "conflict" or poster_status == "no_candidate" or confidence < 0.5:
        return "high"
    if metadata_status == "missing":
        return "medium"
    return "low"

def build_ai_review_queue(
    db,
    *,
    status: str | None = None,
    input_type: str | None = None,
    metadata_status_filter: str | None = None,
    poster_status_filter: str | None = None,
    risk_level: str | None = None,
    include_dam: bool = False,
    page: int = 1,
    size: int = 50,
) -> PaginatedAiReviewQueue:
    """1) Content + ContentImage + ExternalMetaSource를 eager-load
       2) 각 콘텐츠에 대해 get_content_recommendations() 호출 (경량 모드 — DB만, 외부 호출 없음)
       3) include_dam=True 면 content_id 별 dam-assets 조회 (httpx 병렬, timeout 2s, 실패는 dam_count=0)
       4) 분류 함수로 row 채움
       5) 필터 적용 후 페이지네이션 + summary 집계
    """
```

`get_content_recommendations`가 외부 API를 호출하지 않는다는 가정 확인 필요. 호출한다면 경량 버전 `get_content_recommendations_lite(db, content_id)` 분리 — 외부 fetch 없이 DB의 ExternalMetaSource + ContentAIResult만으로 auto_fill/conflicts 계산.

## 라우트
`backend/api/programming/metadata/router.py`:

```python
@router.get("/ai-review-queue", response_model=PaginatedAiReviewQueue)
def get_ai_review_queue(
    status: str | None = None,
    input_type: str | None = None,
    metadata_status: str | None = None,
    poster_status: str | None = None,
    risk_level: str | None = None,
    include_dam: bool = False,
    page: int = 1,
    size: int = 50,
    db: Session = Depends(get_db),
):
    return service.build_ai_review_queue(...)
```

## 테스트
`backend/tests/api/programming/test_ai_review_queue.py`:
- `test_classify_metadata_status_*` — 4 분류 단위
- `test_classify_poster_status_*` — 5 분류 단위
- `test_risk_level_*` — 3 분류 단위
- `test_queue_endpoint_filters` — fixture 4건 (missing/conflict/clean/no-poster) 기준 필터별 응답 검증
- `test_queue_endpoint_include_dam_off` — dam_match_count=0 보장 (DAM 호출 없음 mock)
- `test_queue_endpoint_summary` — summary 합계 검증

## 변경 파일
- `backend/api/programming/metadata/schemas.py` — append만
- `backend/api/programming/metadata/service.py` — 헬퍼 4개 + build_ai_review_queue 추가
- `backend/api/programming/metadata/router.py` — endpoint 1개 추가
- `backend/tests/api/programming/test_ai_review_queue.py` (신규)

## 검증
```bash
docker compose exec backend pytest backend/tests/api/programming/test_ai_review_queue.py -v
docker compose exec backend python -c "
import httpx
r = httpx.get('http://localhost:8000/api/programming/metadata/ai-review-queue?size=5')
print(r.status_code, len(r.json()['items']), r.json()['summary'])
"
```

## 주의
- DAM 호출은 timeout 2s + 실패 = 0 처리. 한 콘텐츠 실패가 전체 응답을 끌어내리지 않게.
- `include_dam=true` 시 N+1 회피: `asyncio.gather`로 병렬, 단 동시성 5 제한.
- `get_content_recommendations` 외부 호출 여부는 코드 읽고 결정 — 외부 호출하면 lite 분리 필수.
