# Step 2 — ott-popularity-sync

> **목표**: 4개 OTT 채널 (Watcha/Netflix/Wave/Tving) 의 Top 콘텐츠 인기 데이터를 주기적으로 수집해 `content_distributions` 테이블에 반영한다. 미매칭 콘텐츠는 카운트만 남기고 드롭한다 (orphan row 방지).

## 사전 컨텍스트 (모든 sub-step 공통)
- Step 0 산출물: `backend/api/distribution/` (`models.py` · `router.py` · `service.py` · `schemas.py`) + alembic `0014_distribution_tables.py`
- 매칭 helper 재사용: `backend/api/meta_core/scoring.py` 의 `normalize_title()`
- Watcha 사이트 정찰: `backend/scripts/watcha_real/RECON.md` (selector, UA, sleep 정책)
- Celery Beat 패턴: `backend/workers/tasks/discovery_tasks.py` + `backend/workers/celery_app.py`
- ContentDistribution 컬럼: `content_id` NOT NULL · `channel` · `popularity_rank` · `popularity_score` · `raw_data` · `synced_at` · UNIQUE(content_id, channel)

## 결정 사항
- **Wave/Tving 는 stub**: 공식 API 없음 / 데이터 소스 미확정 → 인터페이스만 구현 (Step 2.4). 추후 데이터 확정되면 별도 task.
- **Watcha 는 사이트 SSR 파싱**, **Netflix 는 Tudum 공개 TSV** 사용.
- **미매칭 콘텐츠는 drop**: `match_content()` → None 이면 ContentDistribution 생성 X, SyncSummary `dropped` 카운트만 증가.
- 외부 호출 실패는 빈 리스트 반환 → 다음 Beat 에서 자연 재시도. retry 무한 금지.

## 산출 파일 (sub-step 전체)
```
backend/api/distribution/ott/
├── __init__.py
├── base.py          # OttSource ABC + OttItem dataclass
├── matcher.py       # match_content(db, item) -> int|None
├── writer.py        # upsert_distribution(db, ...) -> ContentDistribution
├── runner.py        # run_source(db, source) -> SyncSummary
├── watcha.py        # WatchaTopSource
├── netflix.py       # NetflixTudumSource
├── wave.py          # WaveTopSource (stub)
└── tving.py         # TvingTopSource (stub)

backend/workers/tasks/distribution.py     # sync_ott_* 4 Celery tasks
backend/workers/celery_app.py             # Beat 4건 추가
backend/api/distribution/router.py        # GET /sync/status 추가
backend/api/distribution/service.py       # get_sync_status() 추가
backend/api/distribution/schemas.py       # SyncStatusOut

backend/tests/distribution/
├── __init__.py
├── test_ott_base.py
├── test_ott_watcha.py
├── test_ott_netflix.py
├── test_ott_kr_stubs.py
└── test_sync_status_api.py
```

---

## **2.1** — ott-base-infra
**Scope**: 추상 인터페이스 + 매칭 helper + upsert helper. 어댑터 구현 X.

**시그니처**:
```python
# base.py
@dataclass
class OttItem:
    title: str
    production_year: int | None
    rank: int
    external_id: str | None = None
    raw: dict = field(default_factory=dict)

class OttSource(ABC):
    channel: ClassVar[str]            # "ott_watcha" 등
    channel_type: ClassVar[str] = "ott"
    @abstractmethod
    def fetch_top(self, limit: int = 20) -> list[OttItem]: ...

# matcher.py
def match_content(db: Session, item: OttItem) -> int | None: ...

# writer.py
def upsert_distribution(
    db: Session, *, content_id: int, channel: str,
    rank: int, score: float, raw: dict, external_id: str | None,
) -> ContentDistribution: ...

# runner.py
@dataclass
class SyncSummary:
    channel: str
    fetched: int
    matched: int
    upserted: int
    dropped: int

def run_source(db: Session, source: OttSource, limit: int = 20) -> SyncSummary: ...
```

**핵심 규칙**:
- `match_content`: `normalize_title(item.title)` == `normalize_title(content.title)` AND `(item.year is None OR content.production_year == item.year)`. 다중 매칭 시 `id DESC` 첫 1건.
- `upsert_distribution`: `(content_id, channel)` UNIQUE 충돌 시 INSERT 대신 UPDATE (`popularity_rank`/`popularity_score`/`raw_data`/`external_id`/`synced_at` 갱신).
- `run_source`: 예외 한 건도 전체 sync 중단 안되도록 item 단위 try/except 로 격리.

**verify**: `bash .claude/verify.sh distribution-step2.1`
- 파일 존재 확인
- pytest 8 케이스+ pass: match hit / match miss (title 불일치) / match miss (year 불일치) / 다중 후보 / upsert insert / upsert update / run_source 정상 / run_source item 예외 격리

---

## **2.2** — watcha-top-source
**Scope**: Watcha 인기 차트 어댑터 1건. Beat 등록은 2.5 에서.

**시그니처**:
```python
class WatchaTopSource(OttSource):
    channel = "ott_watcha"
    URL = "https://pedia.watcha.com/ko?domain=movie"

    def fetch_top(self, limit: int = 20) -> list[OttItem]:
        """SSR HTML → carousel 카드 → OttItem 리스트. HTTP/파싱 실패 시 []"""
```

**핵심 규칙**:
- UA: `"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"` (RECON.md §6)
- selector: `a[href^="/ko/contents/"]` (RECON.md §4). 카드 순서 = `rank` (1-indexed).
- `external_id` = href 의 slug
- `popularity_score` = `max(0.0, 1.0 - (rank - 1) * 0.05)`
- HTTP timeout 10초, 실패 시 `[]`
- production_year 추출 어려우면 `None` 허용 (matcher 가 year 없으면 title-only 매칭)

**verify**: `bash .claude/verify.sh distribution-step2.2`
- pytest 5 케이스+ pass: mocked HTML → 카드 N개 파싱, slug 추출, rank 부여, HTTP 실패 → [], run_source 통합 (matched/dropped 분리)

---

## **2.3** — netflix-tudum-source
**Scope**: Netflix Tudum Top10 (한국) 어댑터.

**시그니처**:
```python
class NetflixTudumSource(OttSource):
    channel = "ott_netflix"
    URL = "https://www.netflix.com/tudum/top10/data/all-weeks-countries.tsv"

    def fetch_top(self, limit: int = 20) -> list[OttItem]:
        """공식 TSV → KR country + 최신 week → OttItem 리스트. 실패 시 []"""
```

**핵심 규칙**:
- TSV 컬럼: `country_iso2`, `week`, `category` (films/tv), `rank`, `show_title`, `season_title`, `cumulative_weeks_in_top_10`...
- `country_iso2 == "KR"` 필터 → `week` DESC 정렬 → 최상위 1개 week 만 사용
- `external_id` = `f"{week}:{category}:{rank}"`
- `popularity_score` = `max(0.0, 1.0 - (rank - 1) * 0.1)` (Top10이므로 0.1 step)
- production_year 없음 → `None`
- HTTP/parse 실패 시 `[]`

**verify**: `bash .claude/verify.sh distribution-step2.3`
- pytest 4 케이스+ pass: mocked TSV → KR 필터링, 최신 week 선택, 빈 응답 graceful, 컬럼 누락 graceful

---

## **2.4** — kr-otts-stub
**Scope**: Wave / Tving 어댑터 stub. fetch_top 빈 리스트. 데이터 소스 확정 시 별도 task.

**시그니처**:
```python
class WaveTopSource(OttSource):
    channel = "ott_wave"
    def fetch_top(self, limit: int = 20) -> list[OttItem]:
        # TODO: Wave 공식 Top 차트 데이터 소스 확정 후 구현
        return []

class TvingTopSource(OttSource):
    channel = "ott_tving"
    def fetch_top(self, limit: int = 20) -> list[OttItem]:
        return []
```

**핵심 규칙**:
- 빈 리스트 → run_source 가 `SyncSummary(fetched=0, matched=0, upserted=0, dropped=0)` 정상 반환
- 클래스만으로 Beat 등록 가능 → 2.5 의 task 구조 일관성 확보

**verify**: `bash .claude/verify.sh distribution-step2.4` — pytest 2 케이스 pass (각 클래스 인스턴스화 + fetch_top == [])

---

## **2.5** — beat-and-monitoring
**Scope**: Celery 태스크 4건 + Beat 4건 + 모니터링 엔드포인트 1건.

**파일/시그니처**:
```python
# workers/tasks/distribution.py
@shared_task(name="workers.tasks.distribution.sync_ott_watcha",
             bind=True, max_retries=2, default_retry_delay=600)
def sync_ott_watcha(self) -> dict:
    """run_source(db, WatchaTopSource()) 후 summary dict 반환"""
# netflix / wave / tving 동일 패턴 3건 추가

# api/distribution/router.py 추가
@router.get("/sync/status", response_model=list[SyncStatusOut])
def get_sync_status(db: Session = Depends(get_db)): ...

# api/distribution/schemas.py 추가
class SyncStatusOut(BaseModel):
    channel: str
    total_rows: int
    last_synced_at: datetime | None
```

**Beat 등록 시각** (기존 충돌 회피 — celery_app.py 의 기존 06:00 sync-primary-posters-to-dam 다음):
- `sync-ott-watcha`: `crontab(hour=6, minute=30)`
- `sync-ott-netflix`: `crontab(hour=6, minute=40)`
- `sync-ott-wave`: `crontab(hour=6, minute=50)`
- `sync-ott-tving`: `crontab(hour=7, minute=0)`

**핵심 규칙**:
- 각 태스크는 자체 `SessionLocal()` 으로 DB 세션 관리, finally close
- 태스크 예외 시 retry 2회, 그래도 실패면 dict `{error: str}` 반환 (raise X — Beat 누적 실패 방지)
- `get_sync_status`: `SELECT channel, COUNT(*), MAX(synced_at) FROM content_distributions GROUP BY channel`. 4개 채널 모두 빈 결과여도 4 row 반환 (UNION ALL with constants).

**verify**: `bash .claude/verify.sh distribution-step2.5`
- pytest 3 케이스+ pass: get_sync_status 빈 DB → 4 채널 0 row / 데이터 있을 때 정확한 count / API 200
- import 검증: `python3 -c "from workers.tasks.distribution import sync_ott_watcha, sync_ott_netflix, sync_ott_wave, sync_ott_tving"`
- Beat 등록 검증: `python3 -c "from workers.celery_app import celery_app; assert 'sync-ott-watcha' in celery_app.conf.beat_schedule"`

---

## **2.6** — wrap (doc only)
**Scope**: 회고 + plans/TODO 갱신. 코드 변경 없음.

**파일**:
- `plans/dev-service-distribution/index.json` — step 2 `status: completed` + summary + completed_at
- `TODO.md` — Step 2 → Done, Step 3 (service-category) → Now
- `backend/api/distribution/CLAUDE.md` 신규 (선택): 모듈 구조 한 장

**verify**: `/verify --skip "doc only"`

---

## 후속 step (이번 plan 범위 외)
- **Step 3 (service-category)**: `ServiceCategory` + `ServiceCategoryItem` CRUD + 큐레이션 UI
- **Step 4 (device-variant)**: `DeviceVariant` CRUD + 디바이스별 가용성 조회 API

## 주의사항 (금지 + 이유)
- ❌ **Wave/Tving 실 스크래핑 시도 금지** (2.4) — 공식 API 없음, 사이트 구조 빈번히 변경, 비용 대비 가치 낮음. stub 으로 시작.
- ❌ **미매칭 OTT 항목으로 ContentDistribution row 생성 금지** — content_id NOT NULL 제약 + orphan 정리 비용. dropped 카운트만 남긴다.
- ❌ **외부 호출 무한 retry 금지** — Top 차트는 1일 1회로 충분. max_retries=2 + 600s 지연 고정. 실패 시 다음 Beat 에서 재시도.
- ❌ **raw_data 5KB 이상 저장 금지** — DB row 비대화. 항목별 dict (~1KB) 만 저장.
- ❌ **conftest.py `db` fixture 외 별도 `db` fixture 작성 금지** — Step 0 에서 `StaticPool` conftest 에 적용 완료. 새 테스트는 conftest 의 `db` 만 사용.
- ❌ **verify.sh 케이스 누락 금지** — 각 sub-step 구현 시 `distribution-step2.X` 케이스를 `.claude/verify.sh` 에 동시 추가. `$BACKEND` 변수 사용 (PROJECT_ROOT 아님).
