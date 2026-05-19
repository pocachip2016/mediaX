# Step 10: mh-bulk-e2e (Phase C)

> Milestone: dev-meta-hierarchy

## 읽어야 할 파일
- backend/api/programming/metadata/service.py (process_batch_rows, _process_movie_row, _process_series_rows)
- backend/api/programming/metadata/inheritance.py (resolve_inherited_metadata, _SYNOPSIS_MIN=50)
- backend/api/programming/metadata/router.py (POST /upload/batch)
- backend/tests/conftest.py (db fixture — sqlite in-memory, StaticPool)
- backend/tests/api/programming/test_mh_bulk_movie.py (Step 8 단위테스트)
- backend/tests/api/programming/test_mh_bulk_series.py (Step 9 단위테스트)

## 작업
Phase C (Steps 8~9) 에서 분리된 movie/series bulk insert 경로의 통합 동작을 검증하는 E2E 테스트 작성.

**산출 파일**:
- `backend/tests/api/programming/test_mh_bulk_e2e.py` (신규, 8 시나리오)
- `.claude/verify.sh` — `mh-bulk-movie`/`mh-bulk-series`/`mh-bulk-e2e` 케이스 경로 정렬 (`test_bulk_*.py` → `test_mh_bulk_*.py`)
- `plans/dev-meta-hierarchy/index.json` — Steps 8/9/10 completed

**테스트 시나리오 (8개)**:
1. `test_mixed_movie_series_single_batch` — 혼합 dispatch, success=6
2. `test_router_upload_batch_e2e` — POST /upload/batch CSV E2E, DB state 검증
3. `test_episode_inherits_series_synopsis` — resolve_inherited_metadata 통합 (synopsis ≥50자)
4. `test_batch_job_status_transitions` — job.status=done, 카운트 정확성
5. `test_empty_batch_completes` — rows=[] 정상 처리
6. `test_partial_failure_counts` — 부분 실패 error_log 기록
7. `test_reupload_idempotent_mixed` — 2회 업로드 Content 수 불변
8. `test_dispatch_isolation` — movie series_title 누수 없음, series runtime 미매핑

## Acceptance Criteria
```bash
bash .claude/verify.sh mh-bulk-e2e
```

## 금지사항
- 외부 API 호출 금지 (TMDB/KOBIS/Gemini) — Celery 모킹으로 차단
- `_process_movie_row` / `_process_series_rows` 직접 호출 금지 — 진입점(`process_batch_rows` + 라우터)만 사용
- 실제 DB 파일 (`media_ax_dev.db`) 노터치 — sqlite in-memory 전용
