# CHANGELOG — mediaX

## 2026-06-11

- **facet 백필 정상화 + Redis 침해 차단 + 7b 전환** — MediSearch stale env 교체(실검색 3-provider + 도커 Ollama + chromium) → 기생충 검증 pass. 큐 유실 원인 = 외부 봇 FLUSHALL(Redis 0.0.0.0 노출) → 인프라 4종 127.0.0.1 바인딩 + 공격 키 제거. rate_limit=30/h 제거(페이스 ~125s→~40s, 3배) + Ollama qwen2.5:7b 전환(NAMU 30s) + 소스보유 구간 거의 전건 success 확인. run 6~10 auto 체인 정상(실패 0)
- **dev-curation (1.3 홈 큐레이션)** — HomeSlot+BannerPlan+slot/banner서비스+12EP+SlotBoard+BannerReviewPanel+weekly Beat + 41 tests pass. PR#23

## 2026-06-09

- **1.3 큐레이션 모듈 설계 확정** — ADR-013 하이브리드(ProgrammingNode 재사용+curation 2테이블) + 8 step plan 스캐폴드 + verify curation-design PASS
- **dev-auto-schedule Step 8** — conflict_service 6 pytest pass + _exec_p5_conflict + GET /auto/sets/{id}/conflicts + ConflictPanel.tsx(ExposureCalendar 재사용) + verify pass
- **dev-auto-schedule Steps 1~7** — ADR-012 자동편성 파이프라인: 모델/0047 + auto_service + 엔드포인트 7종 + 트리거 3종 + FE 콘솔 3컬럼 + AutoRunPanel/StageEventLog. commit f9eddeb
- **dev-programming-link Phase 5.1~5.3** — migrate-catalog/curation-fe-api 어댑터 전환 + 레거시 ORM 0 + 125테스트 pass
- **dev-programming-link Phase 4.4** — BackrefList/ExposureCalendar/NodeGraph FE 3종 + GET /sets/{id}/graph
- **feat(scheduling Phase 3.4~4.3)** — suggest_service + 엔드포인트 3종 + schedulingApi 21함수 + 편성 보드 3컬럼(dnd-kit+pin+AI추천) + interpret_intent Tier1 + AiSuggestPanel

## 2026-06-08

- **feat(scheduling Phase 3.2c+3.3)** — node-embed-theme + tier2-semantic-match(match_service cosine+facet 가중합 + 23테스트)
- **feat(catalog-node-adapter)** — ProgrammingNode/Link DAG 완전 마이그레이션. alembic 0044 + 16테스트
- **feat(catalog-restore+facet-intensity)** — catalog workspace 6컴포넌트 복원 + facet intensity axis(9 tests)
- **dev-programming-link Phase 1~3.2** — CUP 모델(0042) + bge-m3 임베딩 + facet 통제어휘 + link-service + scheduling router(15 ep) + Tier0 rule engine + 110테스트
- **docs(scheduling)** — ADR-011 편성 통합 모델(ProgrammingNode+Link DAG) 설계 + plan 스캐폴드 17스텝
- **feat(catalog-workspace-ux3)** — Step 2 FE: dup_policy/loadSet opts + SaveSetDialog + verify.sh 신규 case 3종

## 2026-06-07

- **refactor(single-content-form-shared)** — SingleContentForm 공유화 + pipeline S1 건별 리치 폼 + 사이드바 3단 트리
- **feat(catalog-merge-preview)** — 세트 병합 신규/중복 카운트 표시
- **refactor(bulk-upload-shared)** — BulkUploadForm 공유화 (upload 345→24줄)
- **feat(contents-nav)** — 콘텐츠 관리 메뉴 정비 + TMDB/KOBIS/KMDB 백링크
- **feat(catalog-workspace-ux/ux2)** — 3컬럼 헤더/커스텀 템플릿 CRUD + 탭 서브토글/CSV 파일전용/인라인 트리미리보기
- **feat(catalog-workspace-redesign/sets)** — 3컬럼 레이아웃 + 카테고리 세트 다중 저장 관리(17테스트 + e2e)
- **feat(catalog-category-workspace)** — DnD(@dnd-kit)/BulkImport/30+노드/인라인 rename + CategorySet 모델·0041 + bulk API(13테스트)

## 2026-06-01~06-03

- **dev-auto-headless** — AUTO 헤드리스 단계 자동 연쇄: run-to-stable + stage-게이트 + quality_score 재계산. verify 12체크. PR #18
- **dev-auto-headless BE 회귀 pytest** — KMDB graceful degrade 단위 테스트 3건
- **dev-stage-auto-autofill 회귀 가드** — recompute_quality_score 단위 테스트 9케이스
- **dev-s4-auto-residual** — S4 AUTO 잔류 유지 + 재검수 차단 + 임계값 재평가. verify pass
- **dev-stage-auto-autofill** — S2 enrich-autofill/S3 ai-autofill(빈 필드만) + S4 quality_threshold 자동승인 + AutoRunPanel
- **dev-pipeline-console-3col** — S2~S5 단계별 3단 카드 재구성, StageActionBar 공용화
- **dev-stage-bulk-buttons** — S2/S3/S4 개별+전체 다음단계 버튼 통일
- **dev-seed-dedup** — 시드 멱등화 + pytest 4건
- **dev-s6-rejected-card** — S6 반려/실패 버킷 + RejectedPanel + pytest 5건
- **dev-pipeline-review-edit** — S2 멀티소스배지 + S4 검수 인라인 편집(9필드)
- **dev-pipeline-console-controls C3~D1** — AiProcessPanel + ProgressLog(10초 폴링) + E2E 5케이스

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
