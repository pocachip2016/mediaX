# TODO — mediaX

> VOD AI Transformation Platform. 구현 현황 표는 `CLAUDE.md` 참조.
> **세션 재개 프롬프트**: "TODO.md 확인하고 `## Now`부터 이어서 진행해"

## Now (진행 중, 1~3개)
- [ ] facet 백필 상시 가동 모니터링 — run 8+ auto 체인 진행 중 (모집단 89,374건, rate_limit 제거 후 ~36~67s/항목, 7b 평가)

## Next (이번 마일스톤)
- [ ] 보안 후속 — backend 8000/frontend 3000/medisearch 8080 바인딩 검토 + postgres 비밀번호 변경 (Redis 침해 2026-06-11 여파)

## Later (백로그)
- [ ] 1.4 결재 워크플로우
- [ ] 1.5 CP 수급 관리

## Done (최근 5개만)
- [x] **facet stale run watchdog** — check_stale_facet_runs Beat(10분) + 재디스패치. _handle_stale_running_runs 반환값 추가 + 6 tests pass (2026-06-11)
- [x] **미커밋 변경 커밋** — MediSearch 4-provider + Dockerfile/compose + mediaX watchdog 30파일 커밋 (2026-06-11)
- [x] **facet 배치 중지 기능 + 대시보드 UI 개선** — stop_batch 엔드포인트 + 진입 guard(cancelled run skip) + 연속체인 가드. 배치+이벤트 50:50 레이아웃(각 3~4줄 scroll) + 결과 success 기본값 + 전체 facet_json 표시 + 스타일 통일(rounded-xl bg-card shadow-sm). vote_count 필터 상향(10→50) (2026-06-11)
- [x] **facet 백필 정상화 + Redis 침해 차단 + 7b 전환** — MediSearch stale env 교체(실검색 3-provider + 도커 Ollama + chromium) → 기생충 검증 pass. 큐 유실 원인 = 외부 봇 FLUSHALL(Redis 0.0.0.0 노출) → 인프라 4종 127.0.0.1 바인딩 + 공격 키 제거. rate_limit=30/h 제거(페이스 ~125s→~40s, 3배) + Ollama qwen2.5:7b 전환(NAMU 30s) + 소스보유 구간 거의 전건 success 확인. run 6~10 auto 체인 정상(실패 0) (2026-06-11)
- [x] **dev-curation (1.3 홈 큐레이션)** — HomeSlot+BannerPlan+slot/banner서비스+12EP+SlotBoard+BannerReviewPanel+weekly Beat + 41 tests pass. PR#23 (2026-06-09)
