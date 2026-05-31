# TODO — mediaX

> VOD AI Transformation Platform. 구현 현황 표는 `CLAUDE.md` 참조.
> **세션 재개 프롬프트**: "TODO.md 확인하고 `## Now`부터 이어서 진행해"

## Now (진행 중, 1~3개)
(없음)

## Next (이번 마일스톤)
(없음)

## Later (백로그)
- [ ] 1.2 카탈로그 모듈 스텁 → 실구현 전환
- [ ] 1.3 큐레이션 모듈 설계 확정
- [ ] 1.4 결재 워크플로우
- [ ] 1.5 CP 수급 관리

## Done (최근 5개만)
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
