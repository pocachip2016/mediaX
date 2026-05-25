# ADR-006 · Wireframes (3 Views)

> Companion to [adr-006-pipeline-stage-model.md]. ASCII 전용.

## View 1 — Pipeline Board (`/programming/contents/pipeline`)

```
┌─ 파이프라인 보드 ──────────────────────────────── [자동새로고침 ON] [↻] ┐
│  품질 평균 83.4점 · 게시율 72.1% · 24h 처리 412건                          │
├──────────────────────────────────────────────────────────────────────────┤
│ 입수 채널 (24h)                                                          │
│ ┌───────────────┬───────────────┬───────────────┬───────────────┐         │
│ │📧 이메일 폴링 │✋ 수동 등록   │📦 CSV 벌크    │🪝 Dam 웹훅    │         │
│ │  124건  ●ok   │   18건  ●ok   │  237건  ●ok   │   33건  ●ok   │         │
│ │  마지막 3분전 │  방금         │  6분전        │  12분전       │         │
│ └───────────────┴───────────────┴───────────────┴───────────────┘         │
├──────────────────────────────────────────────────────────────────────────┤
│ Stage 진행 (현재 대기 건수)                                              │
│                                                                          │
│  [S1]──[S2]   〚GATE-1〛   [S3]──[S4]   〚GATE-2〛   [S5]   〚GATE-3〛   │
│  intake norm   ▶12건🔒    LLM TMDB     ▶8건🤖      gap     ▶5건🔒      │
│   132   132              KOBIS Dam                                       │
│                                                                          │
│                                              [S6]   〚GATE-4〛           │
│                                            web-fill   ▶21건🤖            │
│                                                                          │
│  [S7] STAGING ─ 41건                                                      │
│   ─ 충돌 12 · 자동필 8 · 보강필 21                                       │
│                            〚GATE-5〛                                    │
│  [S8] REVIEW  ─ 23건  [▶일괄승인] [반려] [실패로]                         │
│                            〚GATE-6〛                                    │
│  [S9] PUBLISH ─ 게시대기 6건 · 게시됨 189건                                │
├──────────────────────────────────────────────────────────────────────────┤
│  ⚠ 실패큐 2건   ⛔ 반려보관 17건   ⏸ 보강대기 5건                          │
└──────────────────────────────────────────────────────────────────────────┘
```

**인터랙션**
- `〚GATE-N〛` 카드 클릭 → 우측 Drawer 열림 (= `GatePanel`)
- `🔒/🤖` 아이콘 우클릭 또는 long-press → 수동/자동 토글 confirm
- Stage 박스 클릭 → 해당 stage 콘텐츠 리스트 (필터 적용된 contents 페이지로 이동)

## View 2 — Content Timeline V2 (unified shell 좌측 카드 확장)

`/programming/contents/[id]?mode=view` 좌측 컬럼 하단에 추가.

```
┌─ #1234 외계+인 2부 (movie · 2024)                            상태: STAGING ┐
├──────────────────────────────────────────────────────────────────────────┤
│ ● S1 INTAKE          email-poll       14:02:11  3.2s     from: CGV       │
│ ● S2 NORMALIZE       title+year ok    14:02:14  0.1s                     │
│ ● S3 LLM-EXTRACT     ollama:3b        14:02:15  4.8s  ✓ genre, summary   │
│ ● S4 SOURCE-MATCH    ┬ TMDB ✓ 1185528    412ms                            │
│   │                  ├ KOBIS ✗ no-hit     201ms                           │
│   │                  └ Dam   ✓ asset#7712 (poster 1080x1600)              │
│ ● S5 GAP-DETECT      missing: synopsis_kr, cast(2/5)                      │
│ ● S6 WEBSEARCH-FILL  ┬ brave   ✗ no-hit                                   │
│   │                  └ serpapi ✓ (3 results, conf 0.81)                   │
│ ◐ S7 STAGING         diff: 3 fields · conflict: year(2024⇄2023)  ← 현재   │
│ ○ S8 REVIEW          대기                                                 │
│ ○ S9 PUBLISH         대기                                                 │
├──────────────────────────────────────────────────────────────────────────┤
│   [▶ S7→S8 진행]   [⏪ S6 재실행]   [⛔ 반려]   [⚠ 실패로 표시]            │
└──────────────────────────────────────────────────────────────────────────┘
```

**도트 의미**
- `●` 완료 · `◐` 진행 중 · `○` 대기 · `⚠` 실패 · `⛔` 반려 · `⏭` 스킵 · `↻` 재시도됨

**Sub-row**: source 가 2개 이상인 stage(S4·S6) 는 `┬├└` 트리 표기.

**클릭**: stage 행 클릭 → 아래 Accordion 에 raw payload(JSON), provider 응답, error trace.

## View 3 — Live Event Log (`/monitoring/pipeline/log`)

```
┌─ 실시간 이벤트 로그       필터: [stage▼ all] [source▼ all] [event▼ all]┐
├──────────────────────────────────────────────────────────────────────────┤
│ 14:03:01.221  #1234  S8.review.approved   user:parkseou       quality 87 │
│ 14:03:00.901  #1233  S6.websearch.hit     provider:brave      conf 0.92  │
│ 14:02:59.444  #1232  S6.websearch.miss    provider:gemini     quota left │
│ 14:02:58.012  #1231  S4.tmdb.hit          tmdb_id 1185528     latency 412│
│ 14:02:57.880  #1230  S4.kobis.miss        no-result                      │
│ 14:02:55.110  #1229  S3.llm.error         JSONDecodeError     retry 1/3  │
│ ...                                                                      │
├──────────────────────────────────────────────────────────────────────────┤
│ [▶일시정지]  [⬇ 1000행 CSV]   📈 stage별 throughput   ⏱ P95 latency      │
└──────────────────────────────────────────────────────────────────────────┘
```

**렌더**: `@tanstack/react-virtual` 가상 스크롤. WebSocket(`/ws/pipeline-events`) 또는 SSE 폴백.

## GatePanel (Drawer) — 6 게이트 공통 UX

```
┌─ GATE-3 · WebSearch 보강 진행                          [x]                │
├──────────────────────────────────────────────────────────────────────────┤
│ 대상: S5 GAP-DETECT 완료 콘텐츠 5건                                       │
│                                                                          │
│ ☑ #1234  외계+인 2부          missing: synopsis_kr, cast(3/5)             │
│ ☑ #1235  무뢰한                missing: poster                            │
│ ☐ #1236  악마들                missing: synopsis_kr, year                 │
│ ☑ #1237  파묘                  missing: cast(4/5)                         │
│ ☐ #1238  존 오브 인터레스트    missing: genre, runtime                    │
│                                                                          │
│  Provider 우선순위:  ●brave  ◐serpapi  ◐gemini  ◐ollama                  │
│  Quota:  brave 84/100 · serpapi 412/500 · gemini 1.2k/2k                  │
├──────────────────────────────────────────────────────────────────────────┤
│  모드: 🔒 수동  [자동으로 전환]                                            │
│  [시뮬레이션]  [선택 3건 진행 ▶]                       [전체 5건 진행 ▶▶]  │
└──────────────────────────────────────────────────────────────────────────┘
```

**공통 슬롯** (6 게이트가 동일 구조 공유):
1. 헤더: gate 이름 + 대상 stage 범위
2. 대상 리스트: 체크박스 + 핵심 진단 정보 (gap / conflict / quality)
3. Context 패널: provider 우선순위 / quota / 검수자 / quality 게이지 (게이트별 가변)
4. 모드 토글: 🔒 수동 ⇄ 🤖 자동
5. 액션: 시뮬레이션 / 선택 진행 / 전체 진행

게이트별 차이는 **3번 Context 패널** 슬롯만 swap.
