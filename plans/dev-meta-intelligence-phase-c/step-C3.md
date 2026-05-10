# Step C.3: kobis-discovery

> GitHub: 미생성 | Milestone: dev-meta-intelligence-phase-c

## 읽어야 할 파일
- C.2 산출물 — `discovery/base.py`, `discovery/runner.py`
- 기존 KOBIS 워커 (있다면) — `workers/sync_kobis_*.py`
- `docs/dev/meta-intelligence-phase-c.md` §2 KOBIS 행

## 작업

### 1. `api/meta_core/discovery/kobis_source.py`

**`KobisDiscoverySource`**:
- `mode='upcoming'` → KOBIS 개봉예정작 API (`searchMovieList.json` + `prdtStatNm=개봉예정`)
- `mode='box_office_daily'` → 일별 박스오피스 (`searchDailyBoxOfficeList.json`)
- `mode='box_office_weekly'` → 주간 박스오피스
- `mode='new_release'` → 최근 30일 신규 등록 영화 (`openStartDt` 기준)

**KOBIS 응답 → DiscoveryResult 매핑**:
- `external_id = movieCd`
- `title = movieNm`, `original_title = movieNmEn`
- `production_year = prdtYear`
- `content_type = 'movie'` (KOBIS는 영화만)
- `synopsis = None` (KOBIS 시놉시스 없음 — KMDB/TMDB 보강 영역)
- `poster_url = None` (KOBIS 포스터 없음)

### 2. KOBIS 클라이언트 재활용 또는 신설
기존 `workers/` 에 KOBIS 클라이언트가 있으면 import, 없으면 `clients/kobis_client.py` 신설:
- `KOBIS_API_KEY` 환경변수 사용 (`shared/config.py` 에 있음)
- httpx async, timeout 30s

### 3. 한국 시장 특화 필터
- 19세 미만 제외 (`watchGradeNm`)
- 단편(`prdtTypeNm == '단편'`) 제외 — 옵션
- 외국 직배 제외 옵션 (`repNationNm` whitelist)

### 4. 단위 테스트
- `tests/meta_core/test_discovery_kobis.py` ≥ 6개:
  - 4가지 mode 각각 정상 동작
  - 19+ 제외 검증
  - 빈 응답 처리
  - mock httpx

## Acceptance Criteria
```bash
bash .claude/verify.sh phase-c-step3
```

- `from api.meta_core.discovery import KobisDiscoverySource` 통과
- pytest 6+ pass
- `python -m api.meta_core.discovery.kobis_source --mode box_office_daily` 0 exit (KOBIS_API_KEY 있을 때)
- run_discovery 로 호출 시 seed_discovery_log + content_seeds 적재 확인

## 금지사항
- TMDB 호출 금지 — KOBIS 만
- 영화 외 콘텐츠 타입 금지 — KOBIS 영역 = 영화
- `production_year` NULL 허용 (KOBIS prdtYear 가끔 비어있음 — discard 금지)
