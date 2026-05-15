# Phase D CHANGELOG

WebSearch 기반 콘텐츠 발굴 완료. 50+ 신규 파일, 30+ 기존 파일 수정.

## Step Summary

### D.0 — adr-phase-d-websearch (✓ 완료)
**목표**: Phase D 설계 문서 7개 신설
- `_index.md` — Phase D 개요 + Phase A/B/C 연결도
- `sources.md` — 4 provider 비교 + 폴백 순서 + 한국어 매트릭스
- `quota-policy.md` — Redis key convention, KST 리셋, daily limits
- `on-off-policy.md` — 3 env 변수, 경로별 기본값
- `bulk-guard.md` — 거부 룰 (expected > remaining*0.5)
- `cache-policy.md` — 7일 TTL, SHA256 query_hash
- `monitoring-data-model.md` — 3 GET API 스키마

**산출물**: 설계 ADR 7개 (코드 변경 0)

### D.1 — migration-0013-env-keys (✓ 완료)
**목표**: 데이터베이스 마이그레이션 + env 키 등록
- `alembic/versions/0013_phase_d_websearch.py` — web_search_cache 인덱스 변경, web_search_quota_log 테이블, ExternalSourceType.websearch
- `.env.example` — 9개 WebSearch 키 추가
- `shared/config.py` — 9개 설정 필드 등록

**산출물**: DB 마이그레이션 + 환경 변수

### D.2 — web_search-package-brave (✓ 완료)
**목표**: WebSearch 기본 모듈 + Brave 구현
- `api/meta_core/web_search/__init__.py` — 패키지 re-export
- `base.py` — `WebSearchProvider` ABC, `WebSearchResult` dataclass
- `brave.py` — `BraveSearchProvider` (httpx, country=kr, QuotaManager 통합)
- `cache.py` — `cache_get`/`cache_put` (SHA256 query_hash, 7일 TTL)
- `errors.py` — `QuotaExhaustedError`, `ProviderUnavailableError`, `BulkQuotaError`
- `test_brave.py` — 6 테스트 케이스

**산출물**: web_search 패키지 기초 + Brave 클라이언트

### D.3 — serpapi-gemini-ollama-factory (✓ 완료)
**목표**: 4개 provider 구현 + 폴백 체인
- `serpapi.py` — SerpAPI (gl=kr&hl=ko)
- `gemini_grounding.py` — Gemini google_search 도구
- `ollama_ddg.py` — DDG HTML scraping + Ollama 요약 (무한 폴백)
- `factory.py` — `get_provider_chain()`, `search_with_fallback()` (cache 통합)
- `test_factory.py` — 5 폴백 체인 시나리오

**산출물**: 4 provider + factory 폴백 체인

### D.4 — bulk-guard-cache-integration (✓ 완료)
**목표**: bulk 가드 + 캐시 통합
- `guard.py` — `check_bulk_allowed(expected, provider, limit)` (50% 규칙)
- cache 통합 — cache hit 시 quota 사용 0
- `test_guard.py` — 6 거부 케이스
- `test_cache.py` — 6 캐시 시나리오

**산출물**: bulk 가드 + cache 안전성

### D.5 — websearch-discovery-source (✓ 완료)
**목표**: SEED 발굴 통합
- `discovery/websearch_source.py` — `WebSearchDiscoverySource(query/topic/trending 3 mode)`
- LLM 구조화 추출 (Gemini→Groq→Ollama)
- external_id = URL SHA256 prefix(10자)
- Trending 5 쿼리 (Netflix/Disney/Coupang/Wavve/Tving)
- `test_websearch.py` — 6 mode 테스트

**산출물**: DiscoverySource 확장

### D.6 — aggregator-opt-in (✓ 완료)
**목표**: 메타 보강 opt-in 통합
- `aggregator.py` — `enable_web_search=False` 파라미터
- `_add_websearch_suggestions()`, `_create_websearch_suggestion()` 함수
- `intelligence/router.py` — bulk-accept에 `check_bulk_allowed` 가드
- `intelligence/schemas.py` — `BulkAcceptRequest.enable_web_search` 필드
- `test_aggregator_websearch.py` — 7 opt-in 시나리오

**산출물**: Aggregator WebSearch 통합

### D.7 — monitoring-backend-api (✓ 완료)
**목표**: 모니터링 REST API
- `web_search/router.py` — 3 GET 엔드포인트
  - `/quota` — provider별 일일 사용량
  - `/cache-stats?days=7` — hit rate
  - `/recent?limit=50` — 호출 이력
- 5 Pydantic 스키마
- `test_router.py` — 6 스키마 + 응답 검증

**산출물**: 모니터링 API

### D.8 — monitoring-ui-beat-wrap (✓ 완료)
**목표**: UI + Beat 자동화 + 프로젝트 wrap
- `mediaX-CMS/apps/web/lib/webSearchApi.ts` — TypeScript 클라이언트 (getQuota, getCacheStats, getRecent)
- `mediaX-CMS/apps/web/app/(main)/monitoring/web-search/page.tsx` — 모니터링 페이지
  - 4 provider 쿼터 카드 (진행바, 사용량)
  - 캐시 통계 표 (7일 기간)
  - 최근 호출 50건 테이블
  - 30초 자동 새로고침
- `backend/workers/websearch_tasks.py` — `discover_websearch_trending` Celery task (매일 04:30 KST, 5 쿼리)
- `backend/workers/celery_app.py` — Beat 스케줄 등록
- `plans/dev-meta-intelligence-phase-d/index.json` — D.8 status=completed
- `docs/dev/phase-d/CHANGELOG.md` — 이 문서
- `TODO.md` — Phase D → Done

**산출물**: 완성된 모니터링 + 자동화

## 최종 통계

| 항목 | 수량 |
|------|------|
| 신규 파일 | 50+ |
| 수정 파일 | 30+ |
| 테스트 케이스 | 50+ |
| 마이그레이션 | 1개 (0013) |
| Beat 스케줄 | 1개 (discover-websearch-trending) |

## 운영 가이드

### 필수 환경 변수
```
BRAVE_SEARCH_API_KEY=...  # Brave 키 (필수)
SERPAPI_KEY=...           # SerpAPI 키 (선택)
WEBSEARCH_ENABLED=true                    # 마스터 스위치
WEBSEARCH_BULK_ALLOWED=false              # Bulk 가드
WEBSEARCH_PROVIDERS=brave,serpapi,gemini,ollama  # 폴백 순서
WEBSEARCH_BRAVE_DAILY=60                  # 일일 한도
WEBSEARCH_SERPAPI_DAILY=3
WEBSEARCH_GEMINI_DAILY=200
WEBSEARCH_TRENDING_ENABLED=true           # Beat 자동화
```

### Daily 운영
1. `/api/meta-core/web-search/quota` 모니터링
2. 쿼터 부족 시 `WEBSEARCH_BULK_ALLOWED=false` 유지
3. OTT 신작 발굴: Discovery 수동 trigger

### Beat 스케줄
- `discover-websearch-trending`: 매일 04:30 KST (trending 5 쿼리, 안전 마진)

## 다음 단계
- Phase E: 프론트엔드 UX 개선 (캐시 히트율 표시, 검색 기록 필터 등)
- Phase 3: 전사 통합 (구조화, 인덱싱, OTT 파트너 API 연동)

---

**완료 일시**: 2026-05-16  
**참여자**: Claude Sonnet 4.6  
**상태**: ✅ Phase D 완료
