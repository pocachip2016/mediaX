# D.8 — Monitoring UI + Beat + wrap

## 목표
Phase D 완성: 프론트엔드 모니터링 페이지 + Beat 자동화 + 최종 문서.

## 산출물

### 프론트엔드 파일
1. **`mediaX-CMS/apps/web/lib/webSearchApi.ts`**
   - webSearchApi client (getQuota, getCacheStats, getRecent)
   - TypeScript 타입 정의

2. **`mediaX-CMS/apps/web/app/(main)/monitoring/web-search/page.tsx`**
   - `/monitoring/web-search` 페이지
   - 4 provider 카드 (진행바 + 사용량)
   - 캐시 통계 표 (7일 기간)
   - 최근 호출 50건 테이블
   - 30초 자동 새로고침

### 백엔드 파일
1. **`backend/workers/websearch_tasks.py`** (신규)
   - `discover_websearch_trending` Celery task
   - 매일 04:30 KST 실행 (WEBSEARCH_TRENDING_ENABLED 체크)
   - 5개 쿼리 trending mode

2. **`backend/workers/celery_app.py`** (수정)
   - Beat schedule 등록: websearch_trending

### 문서 & 메타
1. **`docs/dev/phase-d/CHANGELOG.md`** (신규)
   - D.0~D.8 스텝 요약

2. **`plans/dev-meta-intelligence-phase-d/index.json`** (수정)
   - D.8 status=completed
   - 최종 summary

3. **`TODO.md`** (수정)
   - "dev-meta-intelligence Phase D" → Done 이동

4. **`plans/dev-meta-intelligence-phase-d/step8.md`** (신규)
   - 이 문서

## 구현 세부

### UI Layout

```
┌─ WebSearch 모니터링 ──────────────────────────────────┐
│                                                        │
│  Provider 쿼터 현황 (4 카드)                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │ Brave    │ │ SerpAPI  │ │ Gemini   │ │ Ollama   │ │
│  │ 30/60    │ │ 1/3      │ │ 150/200  │ │ ∞        │ │
│  │ [███  50%] │ [██ 33%]  │ │ [████ 75%] │ │ [███ 99%] │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
│                                                        │
│  캐시 통계 (7일)          최근 호출 (최대 50건)      │
│  총 쿼리: 100             시간 | Provider | 쿼리    │
│  히트: 70 (70%)           ...                        │
│  미스: 30                                            │
│                                                        │
│  마지막 업데이트: 2026-05-16 16:00:00 KST           │
└────────────────────────────────────────────────────────┘
```

### Beat Schedule

```python
# celery_app.py
app.conf.beat_schedule = {
    # ...existing...
    'discover-websearch-trending': {
        'task': 'discover.websearch_trending',
        'schedule': crontab(hour=4, minute=30, tz=pytz.timezone('Asia/Seoul')),
        'options': {'expires': 3600},
    },
}
```

### API 호출 흐름

1. Page load → useEffect → fetchData()
2. Promise.all([getQuota, getCacheStats, getRecent])
3. setState → re-render with data
4. setInterval(30초) → auto-refresh

## Verify 체크

```bash
bash .claude/verify.sh phase-d-step8
```

- ✓ webSearchApi.ts 존재 (3 메서드 + 타입)
- ✓ web-search/page.tsx 존재
- ✓ websearch_tasks.py 존재 (discover_websearch_trending)
- ✓ D.8 status=completed in index.json
- ✓ CHANGELOG.md 존재
- ✓ TODO.md "Phase D" → Done 이동

## Phase D 최종 요약

| Step | 파일 | 완료 |
|------|------|------|
| D.0 | ADR 7개 | ✓ |
| D.1 | Migration + Config | ✓ |
| D.2 | web_search 패키지 | ✓ |
| D.3 | 4 provider + factory | ✓ |
| D.4 | bulk-guard + cache | ✓ |
| D.5 | WebSearchDiscoverySource | ✓ |
| D.6 | Aggregator opt-in | ✓ |
| D.7 | Monitoring API | ✓ |
| D.8 | UI + Beat + wrap | ✓ |

**총 9 스텝, 50+ 신규 파일, 30+ 기존 파일 수정**

## 운영 가이드

### 환경 변수 (필수)
- `BRAVE_SEARCH_API_KEY` — Brave 키 (필수)
- `SERPAPI_KEY` — SerpAPI 키 (선택)
- `WEBSEARCH_ENABLED=true` — 마스터 스위치
- `WEBSEARCH_TRENDING_ENABLED=true` — Beat 자동화

### Daily 운영
1. `/api/meta-core/web-search/quota` 모니터링
2. 쿼터 부족 시 `WEBSEARCH_BULK_ALLOWED=false` 유지
3. OTT 신작 발굴: Discovery 수동 trigger

### 다음 단계
- D.9: Phase E — 프론트엔드 UX 개선
- Phase 3: 전사 통합 (구조화, 인덱싱)

## 참고
- Beat: 매일 04:30 KST (한국 자정 기준)
- Trending 안전: 5쿼리만 (Brave 5건 < 일일 60)
- WebSearch confidence: 0.5 (인간 검수 필수)
- Cache TTL: 7일 (shadow 정보 안정성)
