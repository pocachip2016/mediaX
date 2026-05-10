# Step C.4: kmdb-discovery

> GitHub: 미생성 | Milestone: dev-meta-intelligence-phase-c

## 읽어야 할 파일
- C.2/C.3 산출물 — `discovery/base.py`, `tmdb_source.py`, `kobis_source.py`
- `backend/api/meta_core/clients/kmdb_client.py` (Phase B step5 산출물 — 재사용)
- `docs/dev/meta-intelligence-phase-c.md` §2 KMDB 행

## 작업

### 1. `api/meta_core/discovery/kmdb_source.py`

**`KmdbDiscoverySource`**:
- `mode='new_release'` → KMDB 최근 90일 등록 영화 (`releaseDts` filter)
- `mode='discover_drama'` → KMDB 드라마 검색 (`collection=kmdb_dr`)
- `mode='discover_movie'` → KMDB 영화 풀스캔 페이지네이션 (백필 용도)

**KMDB 응답 → DiscoveryResult 매핑**:
- `external_id = DOCID` (또는 movieId 형태)
- `title = title` (HTML 태그 제거)
- `original_title = titleEng`
- `production_year = prodYear`
- `content_type = 'movie' | 'series'` — collection 필드로 분기
- `synopsis = plot` (KMDB는 시놉시스 보유 — 보강에 유용)
- `poster_url = posters[0]` (배열 첫번째)

### 2. kmdb_client.py 확장
Phase B `enrich_content` 용도로 만든 KmdbClient 에 discovery 메서드 추가:
- `search_recent(days: int)` — 최근 N일 등록작
- `iter_collection(collection: str)` — 페이지네이션 이터레이터

### 3. 시리즈 처리
KMDB 는 영화·드라마 분리 collection — `kmdb_dr` 는 한국 드라마.
드라마 결과는 `content_type='series'` 로 매핑. 시즌·에피소드는 SEED 단계에서 다루지 않음
(드라마 = 1 SEED → 승격 후 시즌·에피소드는 별도 enrich).

### 4. 단위 테스트
- `tests/meta_core/test_discovery_kmdb.py` ≥ 5개:
  - 영화/드라마 collection 분기
  - HTML 태그 제거(title, plot)
  - poster 배열 처리 + None 폴백
  - mock kmdb client

## Acceptance Criteria
```bash
bash .claude/verify.sh phase-c-step4
```

- `from api.meta_core.discovery import KmdbDiscoverySource` 통과
- pytest 5+ pass
- `python -m api.meta_core.discovery.kmdb_source --mode new_release --days 7` 0 exit (KMDB_API_KEY 있을 때)
- ContentSeed 가 KMDB 출처로 적어도 1건 생성 (실제 호출 시)

## 금지사항
- 시즌/에피소드 SEED 금지 — 시리즈는 1 SEED 로 압축
- KMDB plot 자동 confidence 조정 금지 — Phase B field_strategy 가 이미 처리
- 영문 제목 한 일치 시 무조건 import 금지 (`titleEng == title` 가짜 케이스 → original_title=NULL)
