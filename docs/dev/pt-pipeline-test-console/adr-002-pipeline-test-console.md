# ADR-002 — Pipeline Test Console & Content Timeline

- **Status**: Accepted (2026-05-20)
- **Phase**: pt-pipeline-test-console / Step 0
- **Related**: ADR-001 (content_kind routing), `/programming/contents/pipeline` page

## Context

mediaX 콘텐츠 등록은 *bulk CSV → AI process → external enrich → 검수 → 승인* 다단계 비동기 파이프라인이지만, 운영자가 단계별 동작을 격리 검증할 방법이 없다. 신규 콘텐츠가 어느 단계에서 멈췄는지, AI 추천이 어떤 외부소스에서 왔는지 추적이 불투명하다. TEST_PIPELINE 격리 데이터셋과 단계별 트리거/타임라인 UI 가 필요하다.

## D1 — 6-Stage Pipeline SSOT

| # | Stage | DB status | Trigger (auto/manual) | Exit condition |
|---|---|---|---|---|
| 1 | 생성 | `waiting` | bulk upload / 단건 등록 / IMAP poll | row inserted |
| 2 | AI처리 | `processing` | `POST /contents/{id}/process` (자동 큐) | Ollama 응답 + quality_score 계산 |
| 3 | Enrich | `processing` | `POST /contents/{id}/enrich` | TMDB+KOBIS+KMDB 응답 저장 |
| 4 | 검수 | `staging` | enrich 완료 시 자동 전이 | 운영자 액션 |
| 5 | 승인 | `approved` / `rejected` | `POST /staging/bulk-approve` 등 | 최종 상태 확정 |
| 6 | 게시 | `published` | (별도) Distribution 연동 | 외부 노출 |

**SSOT**: `Content.status` enum. 전이는 `content_audit_logs` 로 영구 기록.

## D2 — TEST_PIPELINE Seed Catalog (총 15건)

식별: `cp_name='TEST_PIPELINE'`, `tags @> '["pipeline-test"]'`.

| 카테고리 | 건수 | 키 필드 | 의도 |
|---|---|---|---|
| 영화-완전 | 3 | title/year/synopsis/genre/runtime/director/cast/poster/tmdb_id | enrich no-op 검증 |
| 영화-불완전 | 5 | title/year 만 | enrich 후보(synopsis/genre/cast/poster/runtime) 발생 |
| 시리즈-완전 | 2 | 시리즈+시즌2+에피4 풀세트 | hierarchy 검증 |
| 시리즈-불완전 | 3 | 시리즈 title만 + 시즌1 셸 | season/episode 상속 + enrich |
| 충돌 | 2 | year/genre 의도적 오류 | MetadataDiffPanel conflict 케이스 |

## D3 — API Surface

### 신규 (Step 2~3)

```
POST   /test/pipeline/seed            → {created: 15, ids: [...]}
POST   /test/pipeline/cleanup         → {deleted: N}  (cp_name + tag AND 가드)
GET    /test/pipeline/summary         → {by_stage: {waiting: n, ...}, last_seeded_at}
GET    /contents/{id}/timeline        → {content_id, stages: [
                                          {stage: "생성", at, source, payload},
                                          {stage: "AI처리", at, task_id, quality, fields_filled},
                                          ...
                                        ]}
```

### 재사용 (변경 없음)

- `POST /contents` 단건, `POST /upload/batch` 벌크
- `POST /contents/{id}/process | /enrich`
- `GET /staging`, `POST /staging/bulk-approve|bulk-reject`
- `GET /pipeline/status` (cp_filter 쿼리 추가 검토)

## D4 — UI Component Tree

```
<PipelineTestConsole>          (확장된 /programming/contents/pipeline/page.tsx)
├── <PipelineHeader/>          (재사용, [↻ 새로고침]·[클린업] 추가)
├── <PipelineStageStrip>       (신규, 6 stage 카드 가로 배치, 클릭 시 active)
│   └── <PipelineStageCard×6>
├── <ActiveStagePanel>         (신규, 선택된 stage 의 상세 화면 라우터)
│   ├── S0: <SampleSeedPanel/>          (신규)
│   ├── S1: <AddContentModal inline/>   (재사용 + prop)
│   ├── S2: <BulkUploadEmbed/>          (신규 wrapper, /upload 로직 재사용)
│   ├── S3: <BatchAiTrigger/>           (신규, 일괄 process)
│   ├── S4: <BatchEnrichTrigger/>       (신규, 일괄 enrich)
│   └── S5: <BulkReviewQueue filter=TEST_PIPELINE/> (재사용 + prop)
├── <TestContentList/>         (신규, 시드 데이터 행 목록, 클릭→timeline)
├── <ContentPipelineTimeline/> (신규, 우측 사이드 또는 모달)
└── <PipelineStatus/> + <BeatSchedule/>  (재사용, 사이드)
```

### Wireframe — 메인 레이아웃

```
┌─ 파이프라인 검증 콘솔                    [↻] [클린업] ─┐
│ ┌S0─┐ ┌S1─┐ ┌S2─┐ ┌S3─┐ ┌S4─┐ ┌S5─┐                │
│ │ 15│→│ 0 │→│ 0 │→│ 0 │→│ 0 │→│ 0 │                │
│ └───┘ └───┘ └───┘ └───┘ └───┘ └───┘                  │
├────────────────────────────────────────────────────────┤
│  ▸ ActiveStagePanel (선택 stage 상세)                 │
│  ─────────────────────                                │
│  좌측 60%: stage 작업 영역                            │
│  우측 40%: TestContentList → 행 클릭 시               │
│           <ContentPipelineTimeline> 표시              │
├────────────────────────────────────────────────────────┤
│  사이드: PipelineStatus(전체) + BeatSchedule          │
└────────────────────────────────────────────────────────┘
```

### Wireframe — ContentPipelineTimeline

```
"기생충 (2019)" #1234
 ●━━━━━●━━━━━●━━━━━●━━━━━○━━━━━○
 ①생성 ②AI  ③Enr ④검수 ⑤승인 ⑥게시
 14:30 14:31 14:33 14:35  -    -
─────────────────────────────────────
① bulk_csv, batch=42
② task=ab12cd, quality=78
③ TMDB hit / KOBIS hit, 4 fields filled
④ staging — conflict 1 (year)
⑤ [지금 승인 →]
```

## D5 — Reuse Matrix

| 자산 | 위치 | 재사용 / 신규 |
|---|---|---|
| `/pipeline/status` API | router.py | 재사용 (선택: cp_filter) |
| `PipelineStatus`, `BeatSchedule` | pipeline/page.tsx | 재사용 |
| `ContentBatchJob` 모델 | models/content.py:337 | 재사용 |
| `AddContentModal` | components/contents/ | 재사용 (inline prop) |
| `MetadataEnrichPanel` | components/contents/ | 재사용 (timeline 내) |
| `BulkReviewQueue` | components/contents/ | 재사용 (cp_filter prop) |
| `/upload` 페이지 로직 | upload/page.tsx | 재사용 (Embed wrapper) |
| `seed_sample_data.py` 헬퍼 | scripts/ | 재사용 (factory 함수) |
| **신규**: PipelineStageStrip/Card | - | 6 stage 가로 strip |
| **신규**: SampleSeedPanel | - | S0 패널 |
| **신규**: ContentPipelineTimeline | - | 6단계 horizontal timeline |
| **신규**: BatchAiTrigger / BatchEnrichTrigger | - | S3/S4 일괄 트리거 |
| **신규**: `/test/pipeline/*` 3 API | - | 시드/클린업/요약 |
| **신규**: `/contents/{id}/timeline` API | - | 단계별 정규화 |

## D6 — Guard Rails

1. **API 가드 (AND)**:
   - `Depends(require_admin)` — 401/403
   - `if not settings.ENABLE_PIPELINE_TEST: raise 404` — 운영 빌드는 라우터 자체 미등록
2. **Cleanup 안전조건 (AND)**:
   - `cp_name='TEST_PIPELINE'`
   - `tags @> '["pipeline-test"]'`
   - `created_at >= seed_runs.started_at` (이번 세션 데이터만)
3. **운영 DB 보호**:
   - seed 트랜잭션 내 `SAVEPOINT`. 검증 실패 시 rollback.
   - cleanup 은 DELETE 전 affected_count 표시 + dry-run 옵션.
4. **FE 노출**:
   - `pipeline/page.tsx` 의 Test Console 섹션은 `role==='admin' && env.ENABLE_PIPELINE_TEST` 일 때만 렌더.

## D7 — Model Switch Policy

| Step | 모델 | 사유 |
|---|---|---|
| 0 (ADR) | Opus 4.7 | 설계 결정 다수 |
| 1 (seed script) | Opus → Sonnet 전환 | 명확한 구현, 패턴 기존 |
| 2~8 (구현) | Sonnet 4.6 | 구현 위주 |
| 9 (wrap+verify) | Haiku 4.5 | 단순 검증/문서 |
| /verify 호출 | Haiku 4.5 | 매 step 동일 |

각 step 끝에서 STOP + 모델 전환 안내 (CLAUDE.md Model Switch Protocol).

## D8 — Out of Scope (이번 phase)

- 게시(S6) 자동화 — Distribution 모듈 연동은 별도 phase.
- IMAP/CP 이메일 입력 경로 — 기존 흐름 변경 없음. 시드는 bulk_csv source 만.
- 다국어/접근성 — 후속 phase.
- Permission system 신규 도입 — 기존 admin role 가정. 없으면 Step 2 에서 follow-up 발행.

## 참고

- 진단 데이터: 2026-05-20 외부소스 배치 보고(이 대화 상단). `link_*_to_contents` 신규 0건 — contents 테이블 비어 있어 link 동작 부재 확인됨. 본 phase 의 시드로 link 동작도 검증된다.
- 기존 ADR-001 (content_kind routing) 의 상속/라우팅 규칙을 시리즈-불완전 케이스로 회귀 검증한다.
