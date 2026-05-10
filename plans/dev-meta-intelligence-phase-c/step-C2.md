# Step C.2: discovery-framework-tmdb

> GitHub: 미생성 | Milestone: dev-meta-intelligence-phase-c

## 읽어야 할 파일
- C.1 산출물 — `models/seed.py`, alembic 0012
- `backend/api/programming/metadata/clients/` (기존 TmdbClient — 재사용)
- `docs/dev/meta-intelligence-phase-c.md` §2 (소스 우선순위), §5 (Beat 스케줄)

## 작업

### 1. `api/meta_core/discovery/__init__.py` + `base.py`

**`DiscoverySource` 추상 인터페이스**:
```python
class DiscoveryResult:
    source_type: str
    external_id: str
    title: str
    original_title: str | None
    content_type: str  # movie/series
    production_year: int | None
    poster_url: str | None
    synopsis: str | None
    raw: dict        # 원본 응답

class DiscoverySource(ABC):
    source_type: str  # 클래스 변수

    @abstractmethod
    def discover(self, mode: str, **kwargs) -> Iterator[DiscoveryResult]: ...

    def log(self, db, mode, total, new, matched, dup, errors, duration_ms, meta):
        # SeedDiscoveryLog UPSERT
```

### 2. `api/meta_core/discovery/tmdb_source.py`

**`TmdbDiscoverySource`** — 기존 TmdbClient 래퍼:
- `mode='trending_day'` → `/trending/movie/day` + `/trending/tv/day`
- `mode='trending_week'` → `/trending/{movie,tv}/week`
- `mode='upcoming'` → `/movie/upcoming?region=KR`
- `mode='discover'` → `/discover/{movie,tv}?region=KR&sort_by=popularity.desc&with_origin_country=KR`
- 페이지네이션: max 5 pages per call (TMDB 페이지당 20건 → 100건/소스/일)

**필터링**:
- 한국 시장 가용성 필터: `with_watch_providers` 또는 `region=KR`
- 19+ 등급 제외 (`certification.lte=18`)
- 미공개·취소작 제외 (`status` whitelist)

### 3. `api/meta_core/discovery/runner.py`

`run_discovery(db, source: DiscoverySource, mode: str)` — 단일 진입점:
1. `source.discover(mode, ...)` 이터레이터 소비
2. 각 결과 → `_normalize_to_seed_payload()` (정규화)
3. dedup match 는 C.6 step 에서 추가 — 일단 raw insert 만
4. content_seeds UPSERT (source_type, external_id) ON CONFLICT
5. seed_discovery_log 1건 작성

### 4. CLI 진입점
`python -m api.meta_core.discovery.tmdb_source --mode trending_day` 동작 보장
(workers/ 에 Celery task 등록은 C.9 에서)

### 5. 단위 테스트
- `tests/meta_core/test_discovery_tmdb.py` ≥ 8개:
  - 빈 응답 → log 만 작성, content_seeds 0건
  - 정상 응답 → upsert + log
  - 동일 external_id 두 번 → UPDATE (dup count)
  - 19+ 등급 → 제외
  - 페이지 끝 도달 → loop 종료
  - mock httpx — 실제 TMDB 호출 없음

## Acceptance Criteria
```bash
bash .claude/verify.sh phase-c-step2
```

- `from api.meta_core.discovery import DiscoverySource, TmdbDiscoverySource, run_discovery` 통과
- pytest tests/meta_core/test_discovery_tmdb.py 8 pass
- CLI: `python -m api.meta_core.discovery.tmdb_source --mode trending_day --limit 5` 가 0 exit 로 종료 (실제 TMDB 호출 — TMDB_API_KEY 있을 때만)
- seed_discovery_log 1건 이상 생성

## 금지사항
- 기존 TmdbClient 코드 수정 금지 — 래핑만
- match/dedup 로직 금지 — C.6 의 영역
- Celery task 등록 금지 — C.9 의 영역
- 자동 promote 금지 — 항상 candidate 상태로 등록
