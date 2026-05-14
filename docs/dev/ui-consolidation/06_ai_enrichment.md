# 06. AI 자동 채움 + 검수 Flow

> Step 5 산출물 — CSV 누락 필드 → 외부 소스(TMDB/KOBIS/KMDB) 매칭 → AI fallback → 검수 UI 의 end-to-end 시퀀스. `03_content_add.md`(추가) + `04_content_detail.md`(검수) + `05_bulk_action.md`(일괄 승인)를 enrichment 관점에서 묶는 문서.

원래 의도: **운영자가 "title 만 있는 CSV" 를 업로드해도 시스템이 외부+AI 로 메타를 채우고, 운영자는 신뢰도 보고 승인만** 하는 흐름. watcha 샘플 데이터(241건 의도적 누락, `OMITTABLE_FIELDS=[production_year, synopsis, cp_name]`)가 검증 시드.

---

## 1. End-to-End 시퀀스 (운영자 관점)

```
[1] CSV 업로드
       콘텐츠 목록 [+ 콘텐츠 추가 ▾] → CSV 탭
       file: watcha_upload.csv  (483건, 그중 241건 필드 누락)
       parse_mode: ● llm  ◯ rule
       ▶ 미리보기 (dry-run) → 4분류 (정상 242 / 누락 241 / 에러 0 / 중복 0)
       ▶ 업로드 확정
                ↓
[2] 백엔드 비동기 처리 — ContentBatchJob 생성
       status: parsing → processing
       각 row → Content + ContentMetadata 생성 (status=waiting)
                ↓
[3] 자동 enrichment 파이프라인 — 워커가 각 콘텐츠 별로:
       (a) 누락 필드 식별 (gap analysis)
       (b) 외부 소스 매칭 (TMDB → KOBIS → KMDB 순)
       (c) AI fallback (gemini → groq → ollama 폴백 체인)
       (d) 품질 스코어 산출 → status 라우팅:
              score ≥ 90 + 외부 매칭 OK → staging
              70 ≤ score < 90              → review
              score < 70                  → review (재처리 권장 라벨)
                ↓
[4] 운영자 알림 — 콘텐츠 목록 "검수 필요" 필터에 새 행 등장
       상단 sticky: "✓ 배치 #bj_ab12 완료 — 482/483 성공 [결과 보기]"
                ↓
[5] 검수
       Option A: 빠른 일괄 승인 — 목록 [☑ 전체 선택] + [✓ 일괄 승인]
       Option B: 개별 상세 — 행 [상세] → 5개 탭 (글자/이미지/영상/외부/AI 이력)
                ↓
[6] 운영자 액션
       전체 신뢰 → 일괄 승인 (Bulk)
       특정 필드 의심 → 상세에서 [📋 필드별 가져오기] 로 소스 교체
       AI 결과 의심 → [AI 이력] 탭에서 대안 엔진 [채택]
       AI/외부 모두 부족 → [✏ 직접 작성]
                ↓
[7] 승인 → approved
       Bulk 토스트 [↶ 되돌리기] / 24h 회수 가능
```

이 시퀀스가 **검증 가능한 단일 가설** 이다: "242건 정상 row + 241건 누락 row 가 같은 파이프라인을 통과해, 누락 row 도 외부+AI 보완 후 같은 staging/review 큐로 들어와 검수자가 일괄 승인할 수 있어야 한다."

---

## 2. 백엔드 enrichment 파이프라인 (개념)

### 2.1 단계별 책임

```
┌──────────────┐  CSV row + Content 생성
│   parser     │  → ContentMetadata.cp_* 채움 (있는 필드만)
└──────┬───────┘  → status=waiting
       │
       ▼
┌──────────────┐  필드별 "비어 있음" 판정
│ gap analyzer │  → missing_fields: ["production_year", "synopsis"]
└──────┬───────┘  → api.meta_core.gap.analyze_gap (기존 모듈)
       │
       ▼
┌──────────────┐  TMDB/KOBIS/KMDB 검색 + 매칭
│  enricher    │  → ExternalMetaSource upsert (각 소스별)
└──────┬───────┘  → api.meta_core.enrich (기존 모듈)
       │           → match_confidence 산출
       │           → 필드별 후보 채집
       ▼
┌──────────────┐  필드별 final 결정
│ resolver     │  → 자동 채택 가능 = match≥0.90 단일 소스
└──────┬───────┘  → 충돌(여러 소스 불일치) = FieldResolution → review 큐
       │
       ▼
┌──────────────┐  외부로도 못 채운 필드 = AI 보완
│ ai fallback  │  → ContentAIResult upsert (engine, task, score)
└──────┬───────┘  → api.programming.metadata.ai_engine
       │
       ▼
┌──────────────┐  최종 status 결정
│ classifier   │  → ContentStatus.staging | review
└──────────────┘  → quality_score 산출
```

→ 모든 모듈은 **이미 존재** (`meta_core/gap.py`, `meta_core/enrich.py`, `meta_core/scoring.py`, `metadata/ai_engine.py`). 이 문서의 역할은 **UI 가 이 파이프라인의 결과를 어떻게 표현하는지**.

### 2.2 데이터 흐름 — 한 row 예시

CSV row: `title=기생충, production_year=, content_type=movie, cp_name=Watcha, synopsis=`

| 단계 | 결과 |
|------|------|
| parser | Content(title=기생충, content_type=movie), CM.cp_synopsis=NULL, CM.cp_genre=NULL |
| gap | missing: [production_year, synopsis, genres, cast, poster] |
| TMDB | match .94 → year=2019, synopsis="A poor family...", genres=[Drama, Thriller], poster_url |
| KOBIS | match .87 → year=2019, director=봉준호, rating=15세 |
| resolver | year: 자동(TMDB+KOBIS 일치). synopsis: 자동(TMDB 단일, 매칭≥.90). genres: 자동(TMDB) |
| ai (synopsis 한국어 보강) | gemini score 89 → 한국어 시놉시스 생성 |
| classifier | quality_score = 92 → staging |

→ 운영자 본 UI: 검수 필요 큐 → 행 클릭 → 상세 → 거의 모든 필드가 외부+AI 로 채워진 상태. "이상 없음" 만 확인.

### 2.3 의도된 어려운 케이스 — 매칭 실패

```
CSV row: title=듣보잡 컬트영화, production_year=, synopsis=
```

| 단계 | 결과 |
|------|------|
| TMDB | match .42 (제목 유사도 낮음) → 후보로만 보존 |
| KOBIS | no match |
| KMDB | match .61 (한국어 제목 정확) |
| resolver | year: KMDB 사용. synopsis: 어디서도 못 가져옴 |
| ai | gemini score 54 (정보 부족 → 추측 시놉시스, 신뢰도 낮음) |
| classifier | quality_score = 58 → review (재처리 권장 라벨) |

→ 운영자 UI: 검수 필요 큐 → 행에 **⚠ 노란 강조** + "외부 매칭 부족" hover. 상세 진입 시 외부 소스 탭에 "낮은 신뢰도" 카드 + AI 이력 탭에 score 54 강조. 운영자는 [✏ 직접 작성] 또는 [✗ 반려] 선택.

---

## 3. UI 표현 — 필드별 provenance trail

`04_content_detail.md` §2.3 의 "필드 × 3소스 카드" 를 enrichment 컨텍스트로 확장.

### 3.1 자동 채움된 필드 시각화 — "✨ AI 채움" 배지

콘텐츠 상세 글자 탭에서 **자동 채움된 필드**는 좌측에 ✨ 배지:

```
▸ 시놉시스                                              ✨ AI 채움 (자동)
  ┌─────────────────────────────────────────────────────────────┐
  │ [CP]  (없음)                                                │
  │ [AI gemini]  score 89                                       │
  │ "가난한 가족이 부유한 가족의 집에 침투…(310자)"            │
  │ [TMDB] match .94                                            │
  │ "A poor family schemes to become employed by a wealthy…"    │
  └─────────────────────────────────────────────────────────────┘
  현재 채택: ● AI gemini   대안: ◯ TMDB(영문)
  [✏ 직접 작성]  [↻ AI 재생성]
```

→ 배지 색:
- ✨ 초록 "AI 채움 (자동)" = 자동 채택 (match/score ≥ 임계)
- ✨ 노랑 "AI 채움 (검토 권장)" = 점수 70~89
- ✨ 빨강 "AI 채움 (저신뢰)" = 점수 <70 또는 매칭 불일치

### 3.2 외부 소스 출처 명시

자동 채움 시 출처를 **항상** 표시 — 운영자가 "어디서 왔는지" 즉시 파악:

```
production_year: 2019  ✨ 자동
  ↑ TMDB match .94 + KOBIS match .87 (일치)  [▾ 출처 보기]
```

[▾ 출처 보기] 펼침:

```
┌─────────────────────────────────────────────────────────────┐
│ 채택 사유: TMDB 와 KOBIS 모두 "2019" 로 일치                │
│                                                             │
│ 후보:                                                       │
│   [TMDB]   2019  match .94   ← 채택                         │
│   [KOBIS]  2019  match .87   ← 일치 (보강)                  │
│   [CP]     (없음)                                           │
│   [AI]     2019  score 92    ← 일치 (확인용)                │
└─────────────────────────────────────────────────────────────┘
```

→ 모든 소스가 일치하면 "✓ 일치 확인". 불일치면 다음 절(§3.3).

### 3.3 충돌 해결 UX — 소스 간 불일치

```
production_year: 2019 ⚠ 충돌                          [수정 필요]
  ┌─────────────────────────────────────────────────────────────┐
  │ 외부 소스 간 값이 다릅니다. 운영자가 결정해주세요.          │
  │                                                             │
  │ ◯ 2019  [TMDB] match .94  [KOBIS] match .87                │
  │ ● 2020  [Watcha] match .79                                  │
  │ ◯ 직접 입력: [_______]                                      │
  │                                                             │
  │ [💾 확정]  [↻ 재매칭]                                       │
  └─────────────────────────────────────────────────────────────┘
```

→ 충돌이 있으면 **자동 채택하지 않고** `FieldResolution` row 생성 → review 큐로 보냄. 운영자가 명시적으로 결정.

→ 백엔드: `api.meta_core.intelligence.FieldResolution` 테이블 활용 (기존 meta-intelligence step1 마이그레이션).

### 3.4 누락 필드 시각화 — review 모드

검수 모드(`04_content_detail.md` §2.5)에선 누락/저신뢰 필드만 표시:

```
┌────────────────────────────────────────────────────────────────┐
│  ⚠ 확인이 필요한 필드 3개                                       │
├────────────────────────────────────────────────────────────────┤
│ • synopsis: ✨ 저신뢰  AI score 54                              │
│ • production_year: ⚠ 충돌  TMDB=2019 / Watcha=2020              │
│ • cast: ❌ 미채움  외부 매칭 없음 + AI 호출 실패                │
│                                                                │
│ [모두 검토하기] [개별 진행]                                    │
└────────────────────────────────────────────────────────────────┘
```

→ 위 3개를 다 해결해야 [✓ 승인] 활성. 운영자가 [✏ 직접 작성] 으로 채우거나 [✗ 반려] 선택.

---

## 4. 콘텐츠 목록의 enrichment 표식

### 4.1 행 단위 배지

`02_menu_lifecycle.md` §3 의 status 칩에 enrichment 정보 추가:

```
┌──────────────────────────────────────────────────────────────────┐
│ ☐  기생충 (2019)        CJ ENM    🟧검수 ✨AI3 🔗TMDB  [상세][승인]│
│ ☐  부산행 (2016)        넥스트    🟧검수 ✨AI5         [상세]      │
│ ☐  미나리 (2020)        A24       🟨자동 🔗TMDB+KOBIS [상세][승인]│
│ ☐  듣보잡 (?)          Watcha    🟧검수⚠ ✨AI(저)    [상세]      │
└──────────────────────────────────────────────────────────────────┘
```

배지 의미:
- `✨ AI N` = AI 가 N개 필드 채움
- `🔗 TMDB+KOBIS` = 외부 매칭된 소스
- `⚠` = 충돌 또는 저신뢰 (정렬 우선순위 ↑)

### 4.2 필터 추가

```
검수 필요 ▾  세부:
  ☑ staging (자동 후보)
  ☑ review (검수)
  ──────
  ☐ AI 자동 채움 있음
  ☐ 외부 충돌 있음
  ☐ 저신뢰 필드 있음 (<70)
```

→ "✓ 자동 채움만 일괄 승인" 패턴 가능. 빠른 검수 사이클.

### 4.3 정렬 옵션

- 기본: 처리 시각 내림차순
- "quality_score 오름차순" = 가장 검수 필요한 것부터
- "충돌 우선" = ⚠ 표시된 것 먼저
- "CP 별로 묶기" = CP 단위 일괄 검토

---

## 5. CSV 미리보기에서의 enrichment 예고

`03_content_add.md` 의 CSV 탭에 enrichment 예고 추가 — **업로드 전에** 어떻게 처리될지 보여줌:

```
┌────────────────────────────────────────────────────────────────────┐
│ CSV 미리보기 (dry-run)                                              │
│ 정상 242 / 누락 241 / 에러 0 / 중복 0                                │
│                                                                    │
│ ✨ 예상 enrichment:                                                  │
│   • 누락 241건 중 약 70~80% 가 TMDB/KOBIS 로 채워질 것으로 예상       │
│   • 남은 약 20~30% 는 AI fallback (gemini)                          │
│   • 예상 비용: AI 호출 ~50건 × $0.001 = ~$0.05                       │
│   • 예상 소요: 2~3분 (rate limit 고려)                               │
│                                                                    │
│ ▸ 누락 필드 분포:                                                   │
│   production_year (157건) — TMDB 매칭률 95% 예상                    │
│   synopsis (132건)       — AI fallback 필요 가능성 높음             │
│   cp_name (89건)         — CSV 의 기본값 "Watcha" 적용              │
│                                                                    │
│ [< 다시 업로드]   [업로드 진행 → 비동기 처리]                      │
└────────────────────────────────────────────────────────────────────┘
```

→ 운영자 의사결정 도움: **비용 예고** + **품질 예고** 가 핵심. 100건 vs 10000건 의 의사결정이 다름.

→ 예측 정확도는 시간이 지나며 데이터 축적 → 통계 학습 (별도 task `dev-enrichment-stats`).

---

## 6. 비동기 작업 진행 표시 (enrichment 특화)

`05_bulk_action.md` §3.4 의 sticky 진행 패널을 enrichment 컨텍스트로:

```
┌────────────────────────────────────────────────────────────────────┐
│ ⏳ 배치 #bj_ab12 — CSV enrichment 진행 중                          │
│                                                                    │
│  parsing  ████████████████████  483/483 (완료)                      │
│  matching ███████████████░░░░░  342/483  TMDB/KOBIS 매칭 중         │
│  ai       ██░░░░░░░░░░░░░░░░░░   54/241  AI fallback (대기 187)    │
│                                                                    │
│ 현재 처리 중: "미나리" (TMDB 검색) · 2.3s/건 평균                   │
│ 남은 예상 시간: ~4분                                                │
│                                                                    │
│ [작업 상세]                                          [백그라운드]   │
└────────────────────────────────────────────────────────────────────┘
```

→ 3단계 진행률 동시 표시 (parse / external / ai). 운영자가 어디서 막혔는지 즉시 파악.

→ AI 단계가 길 때 — **부분 결과 노출**: "이미 정상 처리된 230건은 검수 가능합니다 [검수 시작]"

---

## 7. 배치 결과 페이지 — enrichment 통계

`05_bulk_action.md` §3.5 의 작업 상세 페이지에 enrichment 섹션 추가:

```
┌────────────────────────────────────────────────────────────────────┐
│ 배치 #bj_ab12 — CSV upload (watcha_upload.csv)                     │
│ 시작: 2026-05-13 14:00   완료: 14:08   소요: 8분                   │
│ ──────────────────────────────────────────────────                 │
│ ✓ 총 483건 처리                                                     │
│   • 정상 CSV: 242 → 모두 enrichment 완료                            │
│   • 누락 CSV: 241 → 외부+AI 보완                                    │
│                                                                    │
│ 자동 분류:                                                         │
│   🟨 staging (≥90): 312 (64.6%)  ← 자동 후보                       │
│   🟧 review  (70~89): 158 (32.7%)                                  │
│   🟧 review  (<70): 11 (2.3%)  ← 재처리 권장                       │
│   ❌ 실패: 2 (0.4%)                                                │
│                                                                    │
│ Enrichment 소스 별:                                                │
│   TMDB 매칭: 421 (87.2%)                                           │
│   KOBIS 매칭: 387 (80.1%) (한국 콘텐츠)                            │
│   AI fallback 사용: 54 (11.2%)                                     │
│                                                                    │
│ 충돌 발생: 23건 (운영자 결정 필요)                                  │
│                                                                    │
│ [▶ staging 312개 일괄 승인]  [▶ review 169개 검수 시작]            │
│ [↻ 실패 2개 재처리]  [📋 결과 CSV]                                  │
└────────────────────────────────────────────────────────────────────┘
```

→ 운영자가 결과 페이지에서 바로 다음 액션으로 도약:
- "staging 312개 일괄 승인" 클릭 → Bulk 승인 모달 (5초 Undo)
- "review 169개 검수 시작" 클릭 → 콘텐츠 목록(review 필터) 로 이동

---

## 8. AI 이력 탭의 enrichment 의미

`04_content_detail.md` §6 의 AI 이력 탭 — enrichment 관점에서 추가 표시:

```
┌────────────────────────────────────────────────────────────────────┐
│ AI 처리 이력 (8) + 외부 매칭 이력 (3)                              │
│ ─────────────────────────────────────────────────                  │
│                                                                    │
│ 📥 input received: title="기생충", year=null, synopsis=null         │
│                                                                    │
│ Step 1. Gap analysis (2026-05-13 14:02)                            │
│   missing fields: [year, synopsis, genres, cast, poster]           │
│                                                                    │
│ Step 2. External matching (14:02 ~ 14:03)                          │
│   [TMDB] search "기생충" → match .94 → applied: year, synopsis,    │
│          genres, cast, poster                                       │
│   [KOBIS] search "기생충" → match .87 → applied: rating, director, │
│          country (no conflict with TMDB)                            │
│   [KMDB] no match                                                  │
│                                                                    │
│ Step 3. AI tasks (14:03 ~ 14:04)                                   │
│   gemini synopsis ko: score 89 → ⭐ final                          │
│   gemini tagging:     score 84 → ⭐ final                          │
│   gemini quality:     score 92                                     │
│                                                                    │
│ Step 4. Classification                                             │
│   quality_score=92 → staging                                       │
└────────────────────────────────────────────────────────────────────┘
```

→ 운영자는 한 콘텐츠가 **어떻게 현재 상태에 도달했는지** 추적 가능. 디버깅/감사 가치 ↑.

---

## 9. Watcha 시드 데이터 검증 시나리오

`backend/data/watcha/upload/watcha_upload.csv` (Step 4~5 산출물) 으로 이 flow 검증:

| 검증 포인트 | 기준 |
|----------|------|
| CSV 업로드 dry-run | 483건 파싱 성공, 누락 241건 식별 |
| 백엔드 처리 완료 | 483건 모두 status `staging` 또는 `review` 도달 |
| TMDB 매칭률 | ≥ 85% (외국+한국 콘텐츠 혼재 가정) |
| KOBIS 매칭률 | 한국 콘텐츠의 ≥ 80% |
| AI fallback 사용률 | ≤ 15% (외부 매칭이 우선) |
| 검수 큐 분포 | staging ≥ 60%, review ≤ 40% |
| 일괄 승인 가능 | staging 큐 전체 선택 → Bulk 승인 → approved 변경 |
| 충돌 케이스 | ≥ 5건 (Watcha vs TMDB year 불일치 등) → FieldResolution 생성 |

→ 이 시나리오가 통과하면 **전체 enrichment + 검수 flow 가 운영 가능** 함을 증명. `plans/dev-watcha-sampling/` Step 7~8 의 검증 기준과 통합 가능.

---

## 10. 신규/기존 API 매핑

| 기존 모듈 / 엔드포인트 | enrichment flow 에서의 역할 |
|---------------------|-------------------------|
| `POST /metadata/upload/batch` | CSV 업로드 → `ContentBatchJob` 생성 |
| `GET /metadata/upload/batch/{job_id}` | 진행 상태 polling (§6 진행 패널) |
| `POST /metadata/contents/{id}/process` | 단건 AI 재처리 |
| `POST /metadata/contents/{id}/enrich` | 단건 외부 재매칭 |
| `api.meta_core.gap.analyze_gap` | gap analysis (§2.1) |
| `api.meta_core.enrich.enrich_content` | 외부 매칭 (§2.1) |
| `api.meta_core.intelligence.FieldResolution` | 충돌 해결 (§3.3) |

**신규 API (앞 step 합산 18개 + 추가)**:

| # | 메서드 | 경로 | 용도 |
|---|--------|------|------|
| 19 | `POST` | `/metadata/upload/batch?dry_run=true` | CSV dry-run + enrichment 예고 (§5) |
| 20 | `GET` | `/metadata/upload/batch/{job_id}/enrichment-stats` | 배치 결과 통계 (§7) |
| 21 | `GET` | `/metadata/contents/{id}/provenance` | 필드별 출처 trail (§3.2 출처 펼침) |
| 22 | `POST` | `/metadata/contents/{id}/field-resolution` body: `{field: "year", value: "2019", source: "tmdb"}` | 충돌 결정 (§3.3) |

---

## 11. 의문점

| # | 항목 | 제안 |
|---|------|------|
| 1 | 자동 채택 임계값 — match≥0.90 단일 소스 vs 매칭 일치 다중 소스 | 둘 다 자동 (단일이면 match≥.90, 다중이면 ≥2 소스 일치) — `api.meta_core.scoring.classify_match` 활용 |
| 2 | "예상 비용" 계산 — AI 호출 단가는 환경변수? | `AI_COST_PER_CALL` 환경변수 + 모델별 곱셈 |
| 3 | enrichment 통계 학습 (§5 예고 정확도) | 별도 task. 지금은 hard-coded 추정치 |
| 4 | 부분 결과 노출 (§6) — 비동기 작업 중간 검수 안전한가? | 안전. status 갱신은 row 단위 atomic |
| 5 | watcha 시드 검증 — 이 문서 기준 통과 확인 시점 | `dev-ui-consolidation` Step 6 프로토타입 + `dev-watcha-sampling` Step 7 통합 |

---

## 12. 통합 — 4개 산출물 간 관계

이 문서가 묶는 흐름:

```
03_content_add (입력)
    ↓ CSV 업로드 + dry-run + 비용 예고
06_ai_enrichment §5
    ↓ 백엔드 비동기 처리
06_ai_enrichment §2 (파이프라인) + §6 (진행 패널)
    ↓ status 라우팅 → 검수 큐
02_menu_lifecycle §3 (status 필터) + 06 §4 (행 배지)
    ↓ 검수
04_content_detail §2 (글자) + §5 (외부) + §6 (AI 이력) + 06 §3 (provenance)
    ↓ 일괄 승인 또는 개별 처리
05_bulk_action §3 (실행) + 06 §7 (결과 페이지)
    ↓
approved
```

→ 6개 문서 (01~06) 가 완성되면 **운영자 시나리오 전체** 가 설계 수준에서 검증 가능.

---

## 13. 다음 step

→ `prototype-list-detail` (Step 6): 콘텐츠 목록 + 상세 HTML 프로토타입을 `mediaX-CMS/apps/web/app/(prototypes)/list`, `/detail` 에 Tailwind 로 구현. 이 문서들의 wireframe 을 실제 화면으로 풀어냄.
