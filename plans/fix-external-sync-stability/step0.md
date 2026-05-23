# Step 0: fess-plan (Phase A)

> Milestone: fix-external-sync-stability

## 작업
plan 디렉토리 + index.json + step{0..4}.md skeleton 작성. 진단 결과 문서화.

산출:
- `plans/fix-external-sync-stability/index.json` — 5 step metadata + diagnosis
- `plans/fix-external-sync-stability/step0.md` ~ `step4.md` — step별 spec

## 진단 결과 요약
- Beat 컨테이너 `mediax-beat-1` Restart Count 26회
- `redis.exceptions.LockNotOwnedError: Cannot extend a lock that's no longer owned`
- 5/19~5/20 이틀간 kobis_backfill 트리거 자체 누락
- `sync_log.items_inserted=0` 은 ExternalMetaSource(Content link) 카운터로 캐시 실적과 별개
- `link_kmdb_cache_to_contents` 가 `kmdb_link` 대신 `kmdb_backfill` enum 으로 로깅 (소스 분리 안 됨)

## 검증
```bash
/verify --skip "doc skeleton only"
```

## 금지사항
- 코드 수정 금지. 이 step은 doc 전용.
