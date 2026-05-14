# TODO — mediaX

> KT 지니TV VOD AI Transformation Platform. 구현 현황 표는 `CLAUDE.md` 참조.
> **세션 재개 프롬프트**: "TODO.md 확인하고 `## Now`부터 이어서 진행해"

## Now (진행 중, 1~3개)

## Next (이번 마일스톤 — Dam 연동)
- [ ] dev-meta-intelligence Phase D — WebSearch 기반 콘텐츠 발굴 (별도 task)
- [ ] dev-dam-poster-ingest (Phase 3) — Design AX → DAM 포스터 자동 등록

## Later (백로그)
- [ ] dev-service-distribution — ContentDistribution(IPTV/OTT), ServiceCategory, DeviceVariant
- [ ] 1.2 카탈로그 모듈 스텁 → 실구현 전환
- [ ] 1.3 큐레이션 모듈 설계 확정

## Later (백로그)
- [ ] 1.4 결재 워크플로우
- [ ] 1.5 CP 수급 관리

## Done (최근 5개만)
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
