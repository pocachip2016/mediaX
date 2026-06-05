# TODO — mediaX

> VOD AI Transformation Platform. 구현 현황 표는 `CLAUDE.md` 참조.
> **세션 재개 프롬프트**: "TODO.md 확인하고 `## Now`부터 이어서 진행해"

## Now (진행 중, 1~3개)
- (없음)

## Next (이번 마일스톤)
(없음)

## Later (백로그)
- [ ] 1.2 카탈로그 — 가격 정책(pricing + holdback) 구현
- [ ] 1.3 큐레이션 모듈 설계 확정
- [ ] 1.4 결재 워크플로우
- [ ] 1.5 CP 수급 관리

## Done (최근 5개만)
- [x] **feat(catalog-category-tree)** — 카탈로그 카테고리 트리(1.2.1) — BE 모델/마이그레이션/서비스(18 테스트)/API(15 테스트) + FE 트리 화면(읽기+생성+삭제+nav) (2026-06-06)
- [x] **feat(contents-hierarchy)** — 콘텐츠 목록 계층 트리(평면/계층 토글, 기본 계층) + 파이프라인 S1 기본 트리 + lib/contentTree 공유 유틸 + 시즌/에피 포스터 숨김 (2026-06-06)
- [x] **반려/실패 콘솔 S4 배치** — RejectedConsole 3컬럼(목록+이전단계 / 상세+필드편집+재검수 / WebSearch) + 승인·반려 AUTO 토글 숨김 + 승인 체크박스 폴링 풀림 수정(idsKey) + 반려 목록 밑 다음단계→이전단계 (2026-06-05)
- [x] **revert/재검수 단계 AUTO OFF** — revert/re-review 시 도착 단계(검수 s4_auto) 자동 OFF + auto_hold 미사용(재-ON 시 재개) + RevertResponse.disabled_stages + FE 토글 동기화(syncStageAuto). reject hold 유지. e2e/backward-hold 신정책 테스트 (2026-06-05)
- [x] **dev-child-inheritance** — 시즌/에피소드 상속을 quality_score 채점에 완전 배선(synopsis/genre/country/year/cast/director) + 스칼라 필드(year/country) 자식 DB autofill(apply_parent_inheritance, empty-only·멱등, title/synopsis 제외) + FE (상속) 표시 + 테스트 8건 + 우영우 시즌1 22→78·에피 32→88 보정 (2026-06-05)
- [x] **feat(series-meta)** — TmdbTvCache→ContentMetadata 시리즈 6필드 보강(apply_series_meta_from_cache, S2 AUTO 배선, 멱등, series 한정) + alembic 0038 + FE 표시 + worker watchmedo 핫리로드 인프라(stale 코드 차단) + apply_migration 훅. 우영우/오징어게임/무빙 백필 (2026-06-05)
- [x] **feat(pipeline)** — cascade advance(시리즈/시즌 동일버킷 자손 포함) + 계층 상세 메타 패널(포스터+필드→하위목록) + 외부소스 master-detail(TMDB/KOBIS/KMDB 행 클릭 상세) + 건수 breakdown 라벨(N시즌/M편) + 부모 브레드크럼 (2026-06-05)
- [x] **feat(pipeline-tree-drilldown)** — 계층 트리 + 타입별 드릴다운 (PipelineTreeList 평면/계층 토글 + PipelineDrilldownDetail 타입 디스패치 + ChildrenTable ASC 정렬 + list_contents size 100→500) (2026-06-05)
- [x] **dev-pipeline-auto-worker** — 파이프라인 진행 엔진 FE→Celery 워커 이관 (ADR-010): Beat 15s tick + bucket 병행 + AI per-item fan-out(pipeline_ai 큐) + SKIP LOCKED claim + 멱등 advance/approve + auto_hold(수동 override) + FE 콘솔 모니터화(auto-status/auto-log 폴링·처리건 스크롤 로그·advance 시 목록 제거). Steps 0~8 + 운영픽스 4종 + UX복원 + S4 미승인 자동 반려(bucket 6, 잔류 폐지) (2026-06-04)
- [x] **fix(tmdb-cache)** — TMDB 캐시 목록 정렬 불안정 해소 (id tiebreaker 추가 — popularity/last_fetched_at 비유일 정렬 + daily sync 값 변동으로 새로고침마다 행 섞임) (2026-05-30)
- [x] **dev-auto-headless BE 회귀 pytest** — enrich_content KMDB 한도 초과 graceful degrade(kmdb:daily_limit, 500 아님) 단위 테스트 3건 + verify.sh `auto-headless-be`. KMDB 한도는 _fetch_kmdb_with_cache 1개만 monkeypatch로 시뮬레이션 (2026-06-03)
- [x] **dev-stage-auto-autofill 회귀 가드** — recompute_quality_score 단위 테스트 9케이스(mock 없음) + verify.sh `stage-auto-autofill-guard`(pytest + 빈필드보존/status불변/재계산 grep 가드). empty-only는 grep 가드로 대체 (2026-06-03)
- [x] **dev-s4-auto-residual** — S4 AUTO 잔류 유지(임계값 미만 미승인) + s4ReviewedRef 재검수 차단 + 임계값 변경 시 재평가. verify.sh `s4-auto-residual` + plan(plans/dev-s4-auto-residual). E2E: 잔류 3건 모두 점수 기준 정상 미달 확인 (2026-06-03)
- [x] **dev-auto-headless** — AUTO 헤드리스 단계 자동 연쇄(뷰 비종속): run-to-stable runAutoPipeline + autoPendingKey 재트리거 + per-stage 취소 + 콘솔별 stage-게이트 패널 + 포커스 단계 뷰 동기화 + null-고착·stale-클로저·revert-clear 픽스 + BE KMDB graceful degrade + quality_score 완성도 기반 재계산(S2/S3 autofill+advance) + verify.sh `auto-headless`(12체크). plan: plans/dev-auto-headless (13 steps). PR #18 (2026-06-03)
- [x] **dev-stage-auto-autofill** — 콘솔 AUTO 완성: S2 enrich-autofill/S3 ai-autofill(빈 필드만, 기존값 보존) + S4 quality_threshold 자동승인(0036) + AutoRunPanel/runAuto + seed 재귀 clean. ⚠ 전용 pytest/verify 미추가(후속) (2026-06-02)
- [x] **dev-pipeline-console-3col** — S2~S5 단계별 3단 카드 재구성(목록/상세/요약), StageActionBar 공용화, 단계 이동 후 상세 자동 초기화 (2026-06-01)
- [x] **dev-stage-bulk-buttons** — S2/S3/S4 개별+전체 다음단계 버튼 통일(2건↑ 전체 버튼 표시) (2026-06-01)
- [x] **dev-seed-dedup** — 시드 멱등화 — 전체 카탈로그 중복검사 + skipped_in_pipeline/registered 리포트 + pytest 4건 (2026-06-01)
- [x] **dev-s6-rejected-card** — S6 반려/실패 버킷 + RejectedPanel + 재검수 복귀 + bucket 6 분기 + pytest 5건 (2026-06-01)
- [x] **dev-pipeline-review-edit** — S2 멀티소스배지 + S4 검수 인라인 편집(9필드 클릭→적용) + short_synopsis 한국어 강제 + result_preview 버그픽스 + PipelineBoard 정리 (2026-06-01)
- [x] **dev-s3-enrich-boost-panel** — S3 통합 보강 패널 — RAG/AI번역/AI축약 3버튼 + 전체 필드 테이블(현재값 항상 표시) + 유사값 자동 ✓(runtime/country/cast/genres) + synopsis_ko·en 필드 (2026-05-31)
- [x] **dev-rag-field-extract** — Wikidata/Wikipedia RAG 보강 — ExternalSourceType enum + 0034 migration + reference_extract 서비스 + /test/pipeline/reference-extract 엔드포인트 + FE STEP B UI + E2E 검증 (2026-05-31)
- [x] **dev-stage-two-axis** — 위치(current_stage)/완료(status) 두 축 분리(advance=위치+produce status, CP무관 by_stage 카운트) + EnrichFieldRow 현재값/WebSearch 수동입력 + WebSearch 검색 복구(DDG/cache) + seed clean 동적삭제 (2026-05-31)
- [x] **dev-pipeline-console-controls D1** — E2E 5케이스(auto_chain 회귀 가드) + verify.sh D1 등록 (2026-05-30)
- [x] **dev-pipeline-console-controls C4** — ProgressLog(10초 폴링) + BE GET /test/pipeline/events(content_id, limit) + FE PipelineEventLog 타입 + 우측 패널 하단 배치 (2026-05-30)
- [x] **dev-pipeline-console-controls C3** — AiProcessPanel(Task on/off + AI 결과 diff + 벌크 실행) + BE 2 엔드포인트(GET /contents/{id}/ai-results, POST /test/pipeline/process-ai) + FE 타입/함수 (2026-05-30)
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
