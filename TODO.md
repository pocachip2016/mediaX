# TODO — mediaX

> VOD AI Transformation Platform. 구현 현황 표는 `CLAUDE.md` 참조.
> **세션 재개 프롬프트**: "TODO.md 확인하고 `## Now`부터 이어서 진행해"

## Now (진행 중, 1~3개)
- [ ] facet 백필 skipped/pending 처리 — ~378건 force 배치 추가 필요(limit=100 적용됨) + ~39,900건 Beat 자동 처리

## Next (이번 마일스톤)

## Later (백로그)
- [ ] 1.4 결재 워크플로우
- [ ] 1.5 CP 수급 관리

## Done (최근 5개만)
- [x] **facet 실시간 이벤트 로그 UI** — tail 모드 + KST 시간 + 콘텐츠 제목 + content-centric 행 레이아웃 (2026-06-12)
- [x] **MediSearch enrich 성능 최적화 (A+B)** — LLM 직렬 3회→1회 병합 + fast 레인(구조화만, ~3s) + full 보강(백그라운드, ~40s) + FE 2단 로딩 (2026-06-12)
- [x] **enrich 게이트 분리 + timeout 조정** — enrich_gate 별도(timeout 90s) + mediaX fast 15s/full 120s timeout (2026-06-12)
- [x] **보안 후속** — 8000/3000/8080 바인딩 127.0.0.1 제한 + postgres 비밀번호 변경 (2026-06-12)
- [x] **dev-medisearch-freetext OMDB fix** — evaluate 경로 content_type end-to-end 전달(MediSearch BE + mediaX BE/FE) — OMDB type=series 정상 동작 확인 (2026-06-12)
- [x] **dev-medisearch-ondemand** — 편집 페이지 MediSearch 3단 패널(현재값|기본메타+출처|facet) + 필드 Apply + ExternalSourceType.medisearch + 0052 alembic (2026-06-12)
