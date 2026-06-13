# TODO — mediaX

> VOD AI Transformation Platform. 구현 현황 표는 `CLAUDE.md` 참조.
> **세션 재개 프롬프트**: "TODO.md 확인하고 `## Now`부터 이어서 진행해"

## Now (진행 중, 1~3개)
- [ ] facet 백필 드레인 — 1,186건 failed 큐 자동 드레인(141 오염 + 1,045 tmdb-authoritative-genre genres 보강 백필). nightly beat 21:40 + watchdog 10min 작동 중.

## Next (이번 마일스톤)

## Later (백로그)
- [ ] 1.4 결재 워크플로우
- [ ] 1.5 CP 수급 관리

## Done (최근 5개만)
- [x] **TMDB overview ko→en 폴백 + 주기 beat** — discover ko-KR 복원 + 전체 호출처 폴백 일관화 + 535k 백필 스크립트 + beat 자동화(09:10 KST) (#25, 2026-06-13)
- [x] **facet confidence 계약 버그 수정** — _decide_facet_outcome top-level 폴백 추가(facet nested) + MediSearch top-level confidence 미러, 1297건 NULL 해소 대기 (2026-06-13)
- [x] **D3 tmdb_movie_meta + copyright guard** — TmdbMovieMeta 테이블(0053) + _apply_copyright_guard(story 제거) + include_meta=True payload (2026-06-13)
- [x] **facet 실시간 이벤트 로그 UI** — tail 모드 + KST 시간 + 콘텐츠 제목 + content-centric 행 레이아웃 (2026-06-12)
- [x] **MediSearch enrich 성능 최적화 (A+B)** — LLM 직렬 3회→1회 병합 + fast 레인(구조화만, ~3s) + full 보강(백그라운드, ~40s) + FE 2단 로딩 (2026-06-12)
- [x] **보안 후속** — 8000/3000/8080 바인딩 127.0.0.1 제한 + postgres 비밀번호 변경 (2026-06-12)
- [x] **dev-medisearch-freetext OMDB fix** — evaluate 경로 content_type end-to-end 전달(MediSearch BE + mediaX BE/FE) — OMDB type=series 정상 동작 확인 (2026-06-12)
- [x] **dev-medisearch-ondemand** — 편집 페이지 MediSearch 3단 패널(현재값|기본메타+출처|facet) + 필드 Apply + ExternalSourceType.medisearch + 0052 alembic (2026-06-12)
