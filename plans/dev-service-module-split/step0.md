# Step 0: ADR — service.py 분할 컨벤션 + Shadowing 영구 방지

> GitHub: 미생성 | Milestone: dev-service-module-split

## 배경 (Why)

`backend/api/programming/metadata/service.py` (3,534줄·70+ 함수)는 **콘텐츠 CRUD / 검수 / 배치 / 메타 / AI 추천 / 외부소스 / Bulk / 추천**이 한 파일에 뒤섞여 있다.

### shadowing 사고 타임라인
| Commit | 내용 | 결과 |
|--------|------|------|
| `530ddb5` feat(dpf) | dpf phase 머지로 **빈 service/__init__.py 생성** | `service.py`가 가려져 500 에러 |
| `7520709` fix(service) | service.py 전체 내용을 service/__init__.py로 **복사** | 미봉책 — 두 파일 동일(128,615 bytes)로 공존 |

### 메커니즘 (왜 반복되는가)
- git에 두 파일 모두 추적된 상태로 누가 `service.py`만 수정 → Python은 패키지 우선이라 `service/__init__.py`만 import → 변경 미반영 → 외부소스 캐시 목록이 stale → 사용자 rollback → **구조가 그대로면 또 반복**.

### 직접 트리거
사용자 발화: *"외부소스 각 페이지의 로컬 캐시 검색 및 목록이 다시 몇 개만 보이도록 rollback했어. 왜 자꾸 반복하는지 원인을 찾아 고."*

## 결정 (Decisions)

### D1. 파일명 컨벤션 — `service_<domain>.py` prefix
- 도메인별 별도 파일.
- **`service/` 디렉토리(패키지)는 만들지 않는다** — shadowing 위험 영구 차단.
- 새 도메인 추가 시: 새 `service_<domain>.py` 신규 생성 → shim에 한 줄 import 추가.

후보 `<domain>` 9개 (라인 기준):
| 파일 | 라인 | 키 함수 |
|------|------|---------|
| `service_content.py` | 39–459 | create/update/get/list_contents, review_queue, dashboard, staging, pipeline_status |
| `service_batch_import.py` | 490–888 | create_batch_job, _process_movie_row, _process_series_rows, process_batch_rows |
| `service_meta.py` | 888–1320 | text/image/video meta CRUD, propagate_text_completion, service_readiness |
| `service_ai_suggest.py` | 1375–1559 | suggest_text_meta, suggest_image_meta, add_content_image |
| `service_external_mapping.py` | 1559–1697 | list_tmdb_synced, list_external_mapped_contents |
| `service_external_cache.py` | 1697–1971 | **KMDB/KOBIS/TMDB cache stats/sync_log/search** ← 사용자 rollback 영역 |
| `service_bulk.py` | 1972–2400 | bulk_reprocess/enrich/process/recall/delete, job_status, undo, retry, partial_reprocess |
| `service_sources.py` | 2496–2870 | changelog, lock_fields, preview, sources_search, create_from_sources |
| `service_recommendations.py` | 2891–3534 | resolve_metadata, get_content_recommendations |

### D2. Shim 정책 — 명시 re-export
`service.py`는 약 80줄 shim으로 축소.

```python
# service.py
"""Public service namespace — re-exports for backward compat + monkeypatch.

새 함수는 도메인별 service_<domain>.py에 추가하고 여기 import에 등록한다.
service/ 패키지 디렉토리를 만들지 말 것 (shadowing 위험).
"""
from .service_content import (
    create_content, update_content, get_content, list_contents,
    get_review_queue, apply_review_action, get_dashboard_stats,
    get_staging_queue, bulk_approve_staging, bulk_reject_staging,
    get_content_hierarchy, get_pipeline_status,
    _primary_poster_url, _content_to_staging_item,
)
from .service_external_cache import (
    get_tmdb_cache_stats, list_tmdb_sync_log, list_tmdb_cache_recent,
    get_external_source_stats, list_external_source_sync_log,
    search_kmdb_cache, search_tmdb_cache, search_kobis_cache,
    search_external_sources,
)
# ... (각 도메인 import) ...

__all__ = ["create_content", "update_content", ...]  # 명시
```

**왜 명시 import인가:**
- `from .x import *`는 `_prefix` 함수를 누락 → mock.patch에서 attribute lookup 실패.
- `test_ai_review_queue.py`에서 `patch("api.programming.metadata.service._fetch_dam_counts", ...)` 등 private 함수 patch 다수.

### D3. Pre-commit Guard
- 신규: `backend/scripts/check_no_module_package_shadowing.sh`.
  - `find` 로 `.py` 파일 수집 (제외: `.venv`, `__pycache__`, `.next`, `node_modules`).
  - 각 파일에 대해 `<parent>/<stem>/` 디렉토리 존재 시 exit 1.
- 신규: `.git/hooks/pre-commit` — 위 스크립트 실행.
- 효과: 누군가 빈 `service/__init__.py`를 생성해도 commit 단계에서 즉시 차단.

### D4. Migration 순서 — 사용자 영향 큰 도메인 우선
1. **Step 2**: `service_external_cache.py` (rollback 영역, 최우선).
2. Step 3 이후: 의존성 적은 도메인 순으로.
3. Step 7: shim 정리(__all__ 정의 + docstring 경고).
4. Step 8: 전체 회귀 + UI smoke + commit.

각 분할 step 공통 절차:
1. 새 파일 생성 + 함수+의존 import 이동.
2. `service.py`에서 해당 블록 제거.
3. `service.py` 상단에 명시 re-export 추가 (shim 유지).
4. `pytest tests/api/programming/metadata/ -x` + curl smoke.
5. `/verify <step-id>`.

### D5. 회귀 위험 통제
- shim이 모든 함수 attribute 유지 → `router.py`/`tests/` **무변경**.
- `workers/`는 metadata.service import 없음 (확인됨) → 영향 없음.
- 함수 본문 변경 금지 — 순수 이동만.

## 읽어야 할 파일

- `backend/api/programming/metadata/service.py` (3534줄, 분할 대상).
- `backend/api/programming/metadata/router.py` (47번 라인: `from api.programming.metadata import service`).
- `backend/tests/api/programming/metadata/test_ai_review_queue.py` (mock.patch attribute 의존성).
- `/home/ktalpha/.claude_acc2/projects/-home-ktalpha-Work/memory/feedback_overwrite_impact_check.md` (사용자 메모리: 덮어쓰기 영향도 확인).

## 금지사항

- **`service/` 디렉토리(패키지) 만들지 말 것** — 이유: shadowing 사고 재발. 동일 이름 모듈/패키지 공존은 Python 패키지 우선 원칙으로 모듈 무시됨.
- **함수 본문 수정 금지** — 이유: 분할은 순수 이동. 로직 변경 시 회귀 원인 추적 불가.
- **`from .x import *` 금지** — 이유: `_prefix` 함수 누락 → monkeypatch 깨짐.
- **distribution/service.py 손대지 말 것** — 이유: 179줄로 안전, scope 밖.

## Acceptance Criteria

```bash
# doc-only step
/verify --skip "ADR — 분할 컨벤션·shim 정책·guard 사양 문서화"
```
