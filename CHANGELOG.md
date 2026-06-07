# CHANGELOG — mediaX

## 2026-06-07

- **feat(catalog-workspace-ux2)** — 네비 카탈로그→카테고리관리/생성 + 건별탭 서브토글(단건/텍스트일괄) + 대량(CSV) 파일전용 + SetListPanel 단일행+클릭 인라인 트리미리보기(◀템플릿저장·▶작업반영)
- **feat(catalog-workspace-redesign)** — 3컬럼 레이아웃(InputPanel 탭/프리셋+SetListPanel 작업반영) + SetBar→SetDialogs/SetListPanel 리팩터 + BulkImportPanel onClose 옵셔널
- **feat(catalog-sets)** — 카테고리 세트 다중 저장 관리 (set_service + router 6종 + SetBar UI + 17테스트 + e2e)
- **feat(catalog-category-workspace)** — DnD(@dnd-kit 3존)/BulkImport(indent·path)/TEST데이터 30+노드/인라인 rename/CategoryDetailPanel + CategorySet 모델·0041 마이그레이션 + bulk API(13테스트)

## 2026-06-06

- **dev-catalog-pricing** — 가격 정책 + 홀드백 (1.2.2 + 1.2.3) — BE 4테이블/마이그레이션/pricing·holdback 서비스(25 테스트)/11 API + FE pricing·holdback 2페이지 + typecheck 통과
- **feat(catalog-category-tree)** — 카탈로그 카테고리 트리(1.2.1) — BE 모델/마이그레이션/서비스(18 테스트)/API(15 테스트) + FE 트리 화면(읽기+생성+삭제+nav)
- **feat(contents-hierarchy)** — 콘텐츠 목록 계층 트리(평면/계층 토글, 기본 계층) + 파이프라인 S1 기본 트리 + lib/contentTree 공유 유틸 + 시즌/에피 포스터 숨김

## 2026-06-05

- **revert/재검수 단계 AUTO OFF** — revert/re-review 시 도착 단계(검수 s4_auto) 자동 OFF + auto_hold 미사용(재-ON 시 재개) + RevertResponse.disabled_stages + FE 토글 동기화(syncStageAuto). reject hold 유지. e2e/backward-hold 신정책 테스트
- **dev-child-inheritance** — 시즌/에피소드 상속을 quality_score 채점에 완전 배선 + 스칼라 필드 자식 DB autofill(apply_parent_inheritance, empty-only·멱등, title/synopsis 제외) + FE (상속) 표시 + 테스트 8건
- **feat(series-meta)** — TmdbTvCache→ContentMetadata 시리즈 6필드 보강 + alembic 0038 + FE 표시 + worker watchmedo 핫리로드 인프라 + apply_migration 훅
- **feat(pipeline)** — cascade advance + 계층 상세 메타 패널 + 외부소스 master-detail + 건수 breakdown 라벨 + 부모 브레드크럼

## 2026-06-04

- **dev-pipeline-auto-worker** — 파이프라인 진행 엔진 FE→Celery 워커 이관 (ADR-010): Beat 15s tick + bucket 병행 + AI per-item fan-out + SKIP LOCKED claim + 멱등 advance/approve + auto_hold + FE 콘솔 모니터화. Steps 0~8 + 운영픽스 4종 + UX복원 + S4 미승인 자동 반려

## 2026-06-03

- **dev-auto-headless BE 회귀 pytest** — enrich_content KMDB 한도 초과 graceful degrade 단위 테스트 3건
- **dev-stage-auto-autofill 회귀 가드** — recompute_quality_score 단위 테스트 9케이스 + verify.sh `stage-auto-autofill-guard`
- **dev-s4-auto-residual** — S4 AUTO 잔류 유지(임계값 미만 미승인) + s4ReviewedRef 재검수 차단 + 임계값 변경 시 재평가
- **dev-auto-headless** — AUTO 헤드리스 단계 자동 연쇄(뷰 비종속): run-to-stable runAutoPipeline + per-stage 취소 + 콘솔별 stage-게이트 패널 + null-고착·stale-클로저·revert-clear 픽스 + BE KMDB graceful degrade + quality_score 완성도 기반 재계산. PR #18

## 2026-05-31

- **dev-pipeline-console-controls A1–C1** — BE 상태머신 분리 + AiTask registry + 5개 Phase1 LLM 태스크(translate/short/genre/mood/keywords) + FE ContentStatus 마이그레이션(raw/enriched/ai)
- **dev-pipeline-console-controls 설계** — ADR-007(회수 우선·AI Task registry·번역 ko↔en) + 12-step plan + IMPROVEMENTS 백로그
- **fix(pipeline-console)** — 생성 입력 3탭 통합(CreationTabsPanel) + status 기준 카드 정렬
- **chore(env)** — OLLAMA_MODEL qwen3:4b 전환 (모델명 불일치 LLM 전체 실패 해소)
- **fix(tmdb-cache)** — search API poster 필터 + popularity 정렬 추가

## 2026-05-29

- **dev-curation-workbench Step 11** — FE 완성 (usedMock 배지, 에러 알림, Suspense fallback, 반응형)
- **dev-curation-workbench Steps 7-10** — wizard-12 + external-curation-backfill + wizard-34 + external-import
- **dev-curation-workbench Step 6** — manual 수동 묶기 master-detail (api.ts 8함수, 생성폼, 상세 2컬럼, ContentPicker+ItemRow)
- **dev-curation-workbench Steps 3-5** — matcher(45 pytest) + copy-proposer LLM(17 pytest) + FE landing/nav
- **dev-service-module-split Steps 0~8** — service.py(3534줄) → 8개 도메인 파일 분할 + shim(296줄) + pre-commit shadowing guard
- **dev-curation-workbench Steps 0-2** — ADR(3-모드·OTT 1-Depth=Copy·SSOT) + schema-extend(alembic 0025·6컬럼) + ott-multi-section(OttSection·multi-section fetch·Watcha 파싱) 25 pytest

## 2026-05-27

- **dev-service-distribution Step 3** — service-category CRUD API (7 엔드포인트·20 pytest) → PR #11 merge
- **dev-service-distribution Step 2** — ott-popularity-sync: OttSource ABC + Watcha(SSR)/Netflix(Tudum TSV) + Wave/Tving stub + 4 Celery tasks + Beat 4건 + GET /sync/status + pytest 19 pass
- **dev-external-poster-audit Steps 0~3** — poster audit 완료: diagnostic + parsing fix + content-image sync (KMDB poster_urls/stillcut_urls → ContentImage + Beat 07:15)

## 2026-05-26

- **dev-pipeline-detailed-flow Steps 0~9** — ADR-006(9-stage+6-gate) + schema/service/API + PipelineBoard Master-Detail + GatePanel Drawer + ContentTimelineV2 + Live Event Log 전체 완료

## 2026-05-20

- **dev-detail-unified-shell Steps 0-2, 5-7** — ADR + ContentShell + ViewPane + URL ?mode= SSOT + 큐 통합 + wrap
- **pt-pipeline-test-console Steps 0~9** — 6단계 파이프라인 검증 콘솔 완료 (시드+API+타임라인+FE S0~S5 전 패널)

## 2026-05-19

- **dev-meta-hierarchy Phase A~E** — content_kind SSOT + read-time 상속 + bulk movie/series + FE 검색/3탭/추천 조건부 분기 (Steps 0~16, 38 tests)
- 외부 소스 동기화 진단 — Beat 타임존 UTC→KST 수정, CP 메일 폴링 빈도 조정, Backfill 정상화

## 2026-05-18

- 외부 소스 대시보드 — 통합 sync log + TMDB/KOBIS 로컬 캐시 UI
- **link-kmdb-to-contents** — KMDB 캐시(673건) → contents 링크 (exact+fuzzy 매칭) + Beat 07:00
- **sqlite-to-postgres** — SQLite → PostgreSQL 전환 완료 (alembic 0016·0017, 2,126건)
- **kmdb-front-monitoring** — KMDB 모니터링 페이지(KPI/동기화 로그/캐시 검색)
- **kobis-quota-backfill** — KOBIS quota-aware 백필 Beat 06:30 KST
- **dev-kmdb-cache** — KMDB 로컬 캐시(kmdb_movie_cache) + quota-aware 백필 + enrich 캐시 우선 조회

## 2026-05-17

- **dev-recommend-detail-page Steps 1.0~1.6** — 추천 상세 화면 (sticky 액션바·포스터·메타 3단·줄거리·AI 종합·SecondaryAccordion)
- **dev-recommend-cast-enrich Steps 2–4** — KobisClient.movie_info + enrich_external_credits + cast 5명 슬라이스

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
