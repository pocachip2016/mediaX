# CHANGELOG — mediaX

## 2026-05-10

### feat(meta-intelligence): Phase C — SEED 신규 콘텐츠 발굴 파이프라인

**C.0** ADR docs/dev/phase-c/ 신설 — SEED 라이프사이클·소스 우선순위·승격가드·dedup·Beat·비용 정책 (7파일 200+줄)

**C.1** alembic 0012 — content_seeds·seed_discovery_log 테이블, ExternalSourceType.omdb, MetadataCandidate.target_type/target_id

**C.2** TmdbDiscoverySource — DiscoverySource ABC + trending/upcoming/discover KR (테스트 11개)

**C.3** KobisDiscoverySource — upcoming/box_office_daily/weekly/new_release 4 mode (테스트 12개)

**C.4** KmdbDiscoverySource — new_release/discover_drama/discover_movie 3 mode, HTML 태그·!HS 마커 제거 (테스트 17개)

**C.5** OmdbDiscoverySource — by_imdb_id/search_title 2 mode, N/A 포스터·시놉시스→None 처리 (테스트 16개)

**C.6** match_or_create_seed — Content 매칭(≥0.85)/SEED 중복(≥0.92)/alt_id 누적/신규생성 4단계 dedup (테스트 9개)

**C.7** promote_seed — 잠금 TTL/dedup 재확인/Content+ExternalMetaSource INSERT/Celery enqueue (테스트 10개)

**C.8** SEED 검수 API — GET /seeds(필터/페이징)/stats/{id}, POST lock/unlock/accept/reject/edit/bulk-promote (테스트 15개)

**C.9** Celery Beat 4스케줄(04:30~05:30 KST) + /seeds/discovery-log·discovery-stats·funnel 모니터링 API (테스트 12개)

---

## 2026-05-09

### feat(meta-intelligence): Phase B MVP1 — 메타 인텔리전스 파이프라인

gap→enrich→field_strategy→aggregator→resolution API→검수 백엔드 write API. 테스트 104개.

### feat(dam-bridge): Dam 연동 public API

/contents/since, /dam-events changefeed, Dam 피드백 수신.

### feat(meta-core-extraction): meta_core 모듈 분리

ExternalMetaSource SSOT, external_sync_log, KOBIS sync/backfill, WebSearchCache, 레거시 컬럼 제거.

---

## 2026-05-07

### feat(tmdb-cache): TMDB 로컬 캐시 DB

백필 워커 + Daily Beat + 모니터링 UI.

### chore(infra): systemd 자동 구동

mediaX/Dam/TabGet 8개 서비스, 재시작 시 자동 기동.
