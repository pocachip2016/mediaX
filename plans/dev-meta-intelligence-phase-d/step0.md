# D.0 — ADR: Phase D WebSearch 설계 문서

## 목표
Phase D 설계 결정을 `docs/dev/phase-d/` 하위에 문서화. 코드 변경 0.

## 산출물
1. `docs/dev/phase-d/_index.md` — 메인 ADR (Context, 결정 요약 표, 의존성, Phase B/C 연결도)
2. `docs/dev/phase-d/01-provider-comparison.md` — Brave/SerpAPI/Gemini Grounding/Ollama-DDG 비교 (무료 한도·정확도·응답시간·한국어 지원)
3. `docs/dev/phase-d/02-quota-policy.md` — provider별 daily limit + Redis key 컨벤션 + KST 자정 리셋
4. `docs/dev/phase-d/03-on-off-policy.md` — `WEBSEARCH_ENABLED`/`WEBSEARCH_BULK_ALLOWED`/`WEBSEARCH_PROVIDERS` 3 env + opt-in 정책
5. `docs/dev/phase-d/04-bulk-guard.md` — bulk insert 시나리오 분석 + `expected > remaining * 0.5` 거부 룰
6. `docs/dev/phase-d/05-cache-policy.md` — `WebSearchCache` 7일 TTL + SHA256 key + provider 분리
7. `docs/dev/phase-d/06-monitoring-data-model.md` — `/quota`, `/cache-stats`, `/recent` 응답 스키마

## 검증
- 7 파일 모두 존재
- `_index.md`에 "Phase D" + "Provider 폴백" + "Quota" + "Bulk 가드" 키워드 grep 통과
