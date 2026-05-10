# TODO — mediaX

> KT 지니TV VOD AI Transformation Platform. 구현 현황 표는 `CLAUDE.md` 참조.
> **세션 재개 프롬프트**: "TODO.md 확인하고 `## Now`부터 이어서 진행해"

## Now (진행 중, 1~3개)
<!-- 지금 당장 작업 중인 것 -->

## Next (이번 마일스톤 — Dam 연동)
- [ ] Dam dev-asset-content-mapping M.1 — mediaX backend 재시작 후 /verify M.1 실행, 이후 M.2(CLIP 매핑) 착수
- [ ] dev-meta-intelligence Phase D — WebSearch 기반 콘텐츠 발굴 (별도 task)

## Later (백로그)
- [ ] dev-service-distribution — ContentDistribution(IPTV/OTT), ServiceCategory, DeviceVariant
- [ ] 1.2 카탈로그 모듈 스텁 → 실구현 전환
- [ ] 1.3 큐레이션 모듈 설계 확정

## Later (백로그)
- [ ] 1.4 결재 워크플로우
- [ ] 1.5 CP 수급 관리

## Done (최근 5개만)
- [x] dev-meta-intelligence — Phase C 완료 (SEED 발굴 파이프라인: discovery×4소스, dedup, promote, 검수 API×8, Beat×4, 모니터링 3API, 테스트 91개) (2026-05-10)
- [x] dev-meta-intelligence — Phase B MVP1 완료 (gap→enrich→strategy→aggregator→resolution API→검수 백엔드, 테스트 104개) (2026-05-09)
- [x] dev-dam-bridge — meta_core public API(/contents/since, /dam-events), changefeed webhook, Dam 피드백 수신 (2026-05-09)
- [x] dev-meta-core-extraction — meta_core 모듈, ExternalMetaSource SSOT, external_sync_log, KOBIS sync/backfill, WebSearchCache, 레거시 컬럼 제거 (2026-05-09)
- [x] dev-tmdb-cache — TMDB 로컬 캐시 DB + 백필 워커 + Daily Beat + 모니터링 UI (2026-05-07)
- [x] systemd 자동 구동 — mediaX/Dam/TabGet 8개 서비스, 재시작 시 자동 기동 (2026-05-07)
- [x] 1.1 메타데이터 AI 기반 — 백엔드/프론트 완료
- [x] 1.1 파이프라인 자동화 — staging 상태 + Beat 6개 + 3개 화면
- [x] 1.1 TMDB 동기화 — 일일 Beat + 탐색 페이지
