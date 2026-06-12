# TODO — mediaX

> VOD AI Transformation Platform. 구현 현황 표는 `CLAUDE.md` 참조.
> **세션 재개 프롬프트**: "TODO.md 확인하고 `## Now`부터 이어서 진행해"

## Now (진행 중, 1~3개)
- [ ] facet 백필 상시 가동 모니터링 — run 17 완료 후 skipped 잔여 ~378건 force 배치 추가 필요(limit=100 적용됨) + pending ~39,900건 Beat 자동 처리
- [ ] 보안 후속 — backend 8000/frontend 3000/medisearch 8080 바인딩 검토 + postgres 비밀번호 변경 (Redis 침해 2026-06-11 여파)

## Next (이번 마일스톤)

## Later (백로그)
- [ ] 1.4 결재 워크플로우
- [ ] 1.5 CP 수급 관리

## Done (최근 5개만)
- [x] **dev-medisearch-freetext OMDB fix** — evaluate 경로 content_type end-to-end 전달(MediSearch BE + mediaX BE/FE) — OMDB type=series 정상 동작 확인 (2026-06-12)
- [x] **dev-medisearch-ondemand** — 편집 페이지 MediSearch 3단 패널(현재값|기본메타+출처|facet) + 필드 Apply + ExternalSourceType.medisearch + 0052 alembic (2026-06-12)
- [x] **facet 소스 출처 추적** — provider detail 이벤트 로그 배지 + require_namu=False + skipped 478건 backfill (run 17) (2026-06-11)
- [x] **facet stale run watchdog** — check_stale_facet_runs Beat(10분) + 재디스패치. _handle_stale_running_runs 반환값 추가 + 6 tests pass (2026-06-11)
- [x] **미커밋 변경 커밋** — MediSearch 4-provider + Dockerfile/compose + mediaX watchdog 30파일 커밋 (2026-06-11)
- [x] **facet 배치 중지 기능 + 대시보드 UI 개선** — stop_batch 엔드포인트 + 진입 guard(cancelled run skip) + 연속체인 가드. 배치+이벤트 50:50 레이아웃(각 3~4줄 scroll) + 결과 success 기본값 + 전체 facet_json 표시 + 스타일 통일(rounded-xl bg-card shadow-sm). vote_count 필터 상향(10→50) (2026-06-11)
