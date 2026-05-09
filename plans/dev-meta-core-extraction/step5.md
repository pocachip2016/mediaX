# Step 5: external-fuzzy-match

> GitHub: 미생성 | Milestone: dev-meta-core-extraction (← Dam M.3 이관)

## 읽어야 할 파일
- `backend/api/programming/metadata/models/tmdb_cache.py` (WebSearchCache 추가 위치)
- `backend/workers/tasks/metadata.py:211-297` (sync_kobis — fuzzy 매칭 추가 위치)
- `plans/dev-meta-core-extraction/step4.md` (sync_kobis 재작성 패턴)

## 현황 문제점
1. sync_kobis 타이틀 정확 매칭(==) 실패 — "기생충" vs "기생충 (Parasite)", 띄어쓰기 차이 등
2. KOBIS/TMDB 완전 실패 시 폴백 없음 — 메타 보강 Dead-end
3. Brave/SerpAPI 호출 쿼터 낭비 가능성 — 동일 쿼리 반복 호출

## 작업

### 1. WebSearchCache 모델 추가 (`models/tmdb_cache.py`)
```python
class WebSearchCache(Base):
    __tablename__ = "web_search_cache"
    id = Column(Integer, primary_key=True, autoincrement=True)
    query_hash = Column(String(64), unique=True, nullable=False, index=True)
    query = Column(Text, nullable=False)
    source = Column(String(20), nullable=False)   # "brave" | "serp" | "none"
    results_json = Column(JSON)
    fetched_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
```

### 2. alembic 0008 — web_search_cache 테이블 생성
```python
op.create_table("web_search_cache",
    sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
    sa.Column("query_hash", sa.String(64), unique=True, nullable=False),
    sa.Column("query", sa.Text(), nullable=False),
    sa.Column("source", sa.String(20), nullable=False),
    sa.Column("results_json", sa.JSON()),
    sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
)
op.create_index("ix_web_search_cache_query_hash", "web_search_cache", ["query_hash"])
op.create_index("ix_web_search_cache_expires_at", "web_search_cache", ["expires_at"])
```

### 3. `_cached_web_search(query, db)` 헬퍼 (`ai_engine.py`)
- `hashlib.sha256(query.encode()).hexdigest()` → query_hash
- DB 캐시 히트 + `expires_at > now` → cached results 반환
- 미스 → BRAVE_SEARCH_API_KEY 설정 시 Brave Search API 호출, 없으면 SERP_API_KEY 시도
- API 키 모두 없으면 `source="none"`, `results_json=[]` 저장 + 반환 (1일 TTL)
- 성공 시 7일 TTL로 캐시 저장

### 4. sync_kobis fuzzy 매칭 추가 (`workers/tasks/metadata.py`)
- 기존 정확 매칭 후 미매칭 시 `difflib.SequenceMatcher(None, title_a, title_b).ratio() >= 0.85` 로 재시도
- DB에서 같은 연도 content 목록 사전 로드 → ratio 계산 (O(K), K = 해당 연도 콘텐츠 수, 통상 수십~수백)
- 매칭 성공 시 `match_confidence` 컬럼에 ratio 기록 (`ExternalMetaSource`)

### 5. meta_core models __init__.py에 WebSearchCache re-export

## Acceptance Criteria
```bash
cd /home/ktalpha/Work/mediaX/backend
source .venv/bin/activate
DATABASE_URL=sqlite:///./media_ax_dev.db alembic upgrade head
python3 -c "
from api.programming.metadata.models.tmdb_cache import WebSearchCache
from api.meta_core.models import WebSearchCache as WCC
assert WebSearchCache.__tablename__ == 'web_search_cache'
from workers.tasks.metadata import sync_kobis
print('ALL PASS')
"
```

## 금지사항
- Brave/SerpAPI 실제 호출 금지 (API 키 없는 환경 — graceful skip 필수)
- `_kobis_search_and_save` 함수 수정 금지 (enrich 흐름 전용, 그대로 유지)
- rapidfuzz 패키지 추가 금지 (표준 difflib 사용)
