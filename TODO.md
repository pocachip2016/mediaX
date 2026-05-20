# TODO — mediaX

> VOD AI Transformation Platform. 구현 현황 표는 `CLAUDE.md` 참조.
> **세션 재개 프롬프트**: "TODO.md 확인하고 `## Now`부터 이어서 진행해"

## Now (진행 중, 1~3개)
- [x] **dev-detail-3col-layout Step 0** — ADR-005 + dai cancelled (2026-05-20)
- [x] **dev-detail-3col-layout Step 1** — view 2컬럼 + ViewPane 삭제 (2026-05-20)
- [x] **dev-detail-3col-layout Step 2** — ThreeColumnShell + AISummaryBottom footer (2026-05-20)
- [ ] **dev-detail-3col-layout Step 3-5** — AI rec column + inline edit + row alignment

## Next (이번 마일스톤)

## Later (백로그)
- [ ] dev-service-distribution Step 2 — ott-popularity-sync (Watcha/Netflix/Wave/Tving Top10)
- [ ] 1.2 카탈로그 모듈 스텁 → 실구현 전환
- [ ] 1.3 큐레이션 모듈 설계 확정
- [ ] 1.4 결재 워크플로우
- [ ] 1.5 CP 수급 관리

## Done (최근 5개만)
- [x] dev-detail-unified-shell Steps 6-7 — 큐 통합 + wrap (2026-05-20)
- [x] dev-detail-unified-shell Step 5 — URL ?mode= SSOT + 3패널 dispatch + /edit,/recommend redirect (2026-05-20)
- [x] dev-detail-unified-shell Steps 0-2 — ADR + ContentShell + ViewPane (2컬럼 레이아웃) (2026-05-20)
- [x] pt-pipeline-test-console Steps 0~9 — 6단계 파이프라인 검증 콘솔 완료 (시드+API+타임라인+FE S0~S5 전 패널) (2026-05-20)
- [x] pt-pipeline-test-console Steps 5~7 — SampleSeedPanel + ContentPipelineTimeline + S1단건/S2벌크 embed (2026-05-20)
- [x] dev-meta-hierarchy Phase A~E — content_kind SSOT + read-time 상속 + bulk movie/series + FE 검색/3탭/추천 조건부 분기 (Steps 0~16, 38 tests, verify.sh 통합) (2026-05-19)
- [x] dev-meta-hierarchy Phase C — bulk movie/series 파이프라인 분리 (Steps 8~10) (2026-05-19)
- [x] 외부 소스 동기화 진단 — Beat 타임존 UTC→KST 수정, CP 메일 폴링 빈도 조정, Backfill 정상화 (2026-05-19)
- [x] 외부 소스 대시보드 — 통합 sync log + TMDB/KOBIS 로컬 캐시 UI (2026-05-18)
- [x] link-kmdb-to-contents — KMDB 캐시(673건) → contents 링크 (exact+fuzzy 매칭) + Beat 07:00 (2026-05-18)
- [x] sqlite-to-postgres — SQLite → PostgreSQL 전환 완료 (alembic 0016·0017, 2,126건, .env 전환) (2026-05-18)
- [x] kmdb-front-monitoring — KMDB 모니터링 페이지(KPI/동기화 로그/캐시 검색) + /kmdb/cache 엔드포인트 (2026-05-18)
- [x] kobis-quota-backfill — KOBIS quota-aware 백필 Beat 06:30 KST (잔여 quota>1000일 때 current_year→1990 역순) (2026-05-18)
- [x] dev-recommend-detail-page Step 1.6 — SecondaryAccordion (출연진·외부소스·AI이력 3개 collapsible) (2026-05-17)
- [x] dev-kmdb-cache — KMDB 로컬 캐시(kmdb_movie_cache) + quota-aware 백필 Beat 06:00 KST + enrich 캐시 우선 조회 (2026-05-18)
- [x] kmdb-year-param-fix — search_movie(year) YYYYMMDD 형식 버그 수정 (2026-05-18)
- [x] dev-kmdb-verify — KMDB 4 레이어 검증 (live API · pytest · discovery · enrich) + year 파라미터 버그 발견 follow-up (2026-05-18)
- [x] dev-recommend-cast-enrich Steps 2–4 — KobisClient.movie_info + enrich_external_credits(TMDB/KOBIS 헬퍼) + cast 5명 슬라이스 + enrich-credits endpoint (2026-05-17)
- [x] dev-recommend-detail-page Steps 1.0~1.5 — 추천 상세 화면 기본 구조 (sticky 액션바·포스터·메타 3단·줄거리·AI 종합) (2026-05-17)
- [x] dev-service-distribution Step 1 — service-bulk-import (한국어 헤더 CSV 파서 확장 + SMPTE 런타임 + 5,142건 import) (2026-05-18)
- [x] dev-service-distribution Step 0 — distribution-schema (4테이블 모델 + alembic 0014 + GET 3 엔드포인트 + pytest 8 pass) (2026-05-16)
- [x] dev-dam-poster-ingest P.1~P.3 — Dam poster 자동 등록 파이프라인 완료 (2026-05-16)
- [x] dev-meta-intelligence Phase D — WebSearch 기반 콘텐츠 발굴 (2026-05-16)
- [x] content-register Steps 1–3 — Hero card + 3탭 패널 + enrich=true 진입점 (2026-05-16)
- [x] dev-ai-review-queue Steps 5–6 — Dam Link Display(damApi+4상태) + Bulk Summary 보강(다중 필터+선택+Bulk Apply 가드) (2026-05-16)
- [x] dev-ai-review-queue Steps 1–4, 7 — unified review queue API(30 tests) + Review Queue 리스트 + MetadataDiffPanel + MetadataEnrichPanel 2패널 + VisualAssetCandidatePanel (2026-05-16)
- [x] dev-meta-recommendations-ui — Missing 배지 + 추천 패널(auto_fill + conflict 2단 비교 + AI 종합) + 백엔드 /recommendations 엔드포인트 (2026-05-15)
- [x] dev-flexible-meta-pipeline Step 5a~5d — DB 정리 + 크롤러 cast/director 추출 + CSV 12열 + Watcha 237건 재업로드 + credits E2E 검증 (2026-05-15)
- [x] dev-flexible-meta-pipeline Step 0–4 — Resolution Service + CSV 8열 + PUT 엔드포인트 + IA 재구성(/new /upload /external /edit) + E2E 검증 (2026-05-15)
- [x] dev-detail-page-vod-layout — 상세 페이지 VOD 스타일 재설계 + TMDB backfill task + 사이드바 UX 개선 (2026-05-15)
- [x] dev-poster-recommend Phase 2 — TMDB 다중 포스터 추천 + 운영자 primary 선택 UI 완료 (2026-05-15)
- [x] dev-poster-display Phase 1 — 리스트/상세 포스터 표시, Watcha 237건 backfill, TMDB idempotency 강화 (2026-05-14)
- [x] watcha-real-sampling — 237건 실데이터 크롤링, 포스터 다운로드, bulk upload + AI enrichment 트리거 완료 (2026-05-14)
- [x] Dam dev-asset-content-mapping M.2 — CLIP 매핑 UI 연결 (2026-05-14)
- [x] Dam dev-asset-content-mapping M.1 — backend SQLite 복원 + /verify M.1 통과 (2026-05-14)
- [x] dev-ui-api-wiring — 18개 엔드포인트 UI 연결 완료 (Step 0~3: types·bulk·detail·add flow) (2026-05-14)
- [x] dev-api-consolidation — 18개 신규 엔드포인트 구현 완료 (Step 0~5: 스키마·Bulk·Jobs·Detail·Add Flow) (2026-05-13)
- [x] dev-ui-implementation — 4-step UI 완료 (콘텐츠 목록, 상세 5탭, Add모달, Bulk모달, 처리현황 페이지) (2026-05-13)
- [x] dev-ui-consolidation — 8-step design + 4 prototypes 완료 (UI 구조 재설계, 5탭 상세, Bulk 액션, AI enrichment flow) (2026-05-13)
- [x] dev-watcha-sampling steps 4-5 — Real data rebuild + poster download (483 items, 241 with intentional omissions) (2026-05-13)
- [x] chore: fix external source cache display (mock fallback for empty data) + TMDB menu consolidation (2026-05-12)
- [x] dev-meta-intelligence — Phase B MVP1 완료 (gap→enrich→strategy→aggregator→resolution API→검수 백엔드, 테스트 104개) (2026-05-09)
- [x] dev-dam-bridge — meta_core public API(/contents/since, /dam-events), changefeed webhook, Dam 피드백 수신 (2026-05-09)
- [x] dev-meta-core-extraction — meta_core 모듈, ExternalMetaSource SSOT, external_sync_log, KOBIS sync/backfill, WebSearchCache, 레거시 컬럼 제거 (2026-05-09)
- [x] dev-tmdb-cache — TMDB 로컬 캐시 DB + 백필 워커 + Daily Beat + 모니터링 UI (2026-05-07)
- [x] systemd 자동 구동 — mediaX/Dam/TabGet 8개 서비스, 재시작 시 자동 기동 (2026-05-07)
- [x] 1.1 메타데이터 AI 기반 — 백엔드/프론트 완료
- [x] 1.1 파이프라인 자동화 — staging 상태 + Beat 6개 + 3개 화면
- [x] 1.1 TMDB 동기화 — 일일 Beat + 탐색 페이지
