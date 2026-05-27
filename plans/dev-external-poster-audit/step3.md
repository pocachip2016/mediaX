# Step 3 — kmdb-content-image-sync

> GitHub: (해당 없음 — poster audit 내부 step)

## 목표
`kmdb_movie_cache.poster_urls` / `stillcut_urls` (Step 2에서 백필된 JSON 컬럼)를  
`content_images` 테이블로 동기화하는 Celery 태스크 + 07:15 KST Beat 등록.

## 전제 조건
- Step 2 완료: `kmdb_movie_cache.poster_urls` / `stillcut_urls` JSON 컬럼 존재 (migration 0023)
- `external_meta_sources` 테이블에 `source_type='kmdb'` + `external_id=docid` 매핑 존재
  (link_kmdb_cache_to_contents Beat 07:00 에서 채워짐)
- `content_images` 테이블 기존 컬럼: `content_id, image_type, url, source(str20), is_primary, width, height`
- **No migration needed** — source 컬럼에 "kmdb" 문자열만 추가하면 됨

## Beat 시간 선택
| 시각 | 태스크 | 이유 |
|------|--------|------|
| 07:00 | link-kmdb-to-contents | ExternalMetaSource KMDB 링크 |
| **07:15** | **kmdb-content-image-sync (신규)** | KMDB 링크 완료 직후 |
| 07:30 | link-tmdb-to-contents | 기존 TMDB 링크 (이미 점유) |
| 07:45 | link-kobis-to-contents | 기존 KOBIS 링크 |

## 구현 범위

### A. `workers/tasks/kmdb_cache.py`에 태스크 추가

```python
@shared_task(name="workers.tasks.kmdb_cache.sync_kmdb_poster_to_content_images", max_retries=0)
def sync_kmdb_poster_to_content_images():
    """kmdb_movie_cache.poster_urls/stillcut_urls → content_images 동기화 (idempotent).
    
    로직:
    1. external_meta_sources (source_type=kmdb) JOIN kmdb_movie_cache ON docid
    2. 각 content 에 대해:
       - poster_urls → ImageType.poster, source="kmdb"
         - 첫 번째 URL: is_primary=True (단, 이미 is_primary poster 가 있으면 False)
         - 중복 URL(content_id+image_type+url) 스킵
       - stillcut_urls → ImageType.stillcut, source="kmdb"
         - 중복 스킵
    3. 100건 단위 커밋
    Returns: {posters_added, stillcuts_added, contents_processed, errors}
    """
```

### B. `workers/celery_app.py` Beat 등록

```python
"sync-kmdb-posters-to-content-images": {
    "task": "workers.tasks.kmdb_cache.sync_kmdb_poster_to_content_images",
    "schedule": crontab(hour=7, minute=15),  # 07:15 KST (link-kmdb 07:00 직후)
},
```

### C. `tests/workers/test_kmdb_content_image_sync.py` (신규)

테스트 케이스 (5개 이상):
1. `test_poster_urls_inserted` — poster_urls 있는 캐시 → ContentImage(poster) 정상 삽입
2. `test_first_poster_is_primary` — 기존 primary 없으면 첫 URL이 is_primary=True
3. `test_first_poster_not_primary_when_existing` — 이미 is_primary poster 존재하면 is_primary=False
4. `test_idempotent_rerun` — 동일 태스크 2번 실행 → 중복 없음
5. `test_stillcut_urls_inserted` — stillcut_urls → ImageType.stillcut 삽입
6. `test_no_match_skipped` — ExternalMetaSource 없는 캐시 → ContentImage 없음
7. `test_empty_poster_urls_skipped` — poster_urls=[] → 아무것도 삽입 안 됨

## 변경 파일
| 파일 | 변경 |
|------|------|
| `workers/tasks/kmdb_cache.py` | `sync_kmdb_poster_to_content_images` 태스크 추가 |
| `workers/celery_app.py` | Beat `sync-kmdb-posters-to-content-images` 07:15 등록 |
| `tests/workers/test_kmdb_content_image_sync.py` | 신규 (7개 테스트) |

## 완료 기준 (verifiable)
- [ ] `pytest tests/workers/test_kmdb_content_image_sync.py` — 7개 pass
- [ ] 기존 test suite (`pytest tests/workers/test_kmdb_extract.py`) 회귀 없음
- [ ] Beat 스케줄 07:15 등록 확인 (`celery_app.py` diff)
- [ ] 수동 트리거 실행 → 로그에 `[kmdb-image-sync] 완료` 출력
