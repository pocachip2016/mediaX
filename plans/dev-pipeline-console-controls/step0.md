# Step 0 — ② AI처리 패널 제어판 재설계 (Design)

> 상태: **보류(deferred)** — 수동 단계 검증을 먼저 진행하며 개선점 수집 후 착수.
> branch: 미정 (`feature/pipeline-console-controls` 예상)

## 배경 — 근본 원인

CSV 대량 업로드 시 콘텐츠가 자동으로 `review`까지 진행되어 수동 단계 검증이 불가능했음.

호출 체인:
```
CSV 대량 업로드
 └─ _process_movie_row()            service_batch_import.py:123 → status=waiting 생성
      └─ process_content_metadata.delay(content.id)   ← 줄 155: 생성 즉시 자동 큐 등록 ❗
           └─ process_content_ai()   ai_engine.py:329
                ├─ status = processing                (줄 348)
                ├─ 품질 스코어 계산
                └─ score>=90 → approved / else → review  (줄 385~388) ❗  (staging 건너뜀)
```

→ 업로드 = 자동 AI 처리 = review 직행. 중간 수동 게이트 없음. Beat 스케줄과 무관(전부 일/6시간 cron).

## 전제 — BE 상태머신 분리 (핵심 결정사항)

현 `process_content_ai`는 단일 태스크에서 다단계 전이 + staging 건너뜀. 단일 전이로 분리:

| 카드 | 액션 | 전이 (정확히 1칸) |
|---|---|---|
| ② AI처리 | AI 메타 생성(시놉시스/장르/태그/점수) | `waiting → processing` 에서 **정지** |
| ③ Enrich | 외부 멀티소스 검색(TMDB/KOBIS) | `processing → staging` |
| ④ 검수 | 운영자 승인/반려 | `staging → review/approved/rejected` |

`process_content_ai(content_id, *, auto_chain: bool, score_threshold: int)`:
- `auto_chain=False` → processing 정지 (수동 모드)
- `auto_chain=True` → 점수 ≥ threshold 시 다음 단계 연쇄

**중요(사용자 요구)**: AI(LLM) 처리는 업로드·관찰 중 **자동 트리거 금지**. ②AI처리 단계에서 운영자가 직접 실행하고, 그 단계 패널에서 **LLM 처리 자체를 관찰**한다 — 사용 엔진/모델(현재 `ollama:qwen3:4b`), 폴백 체인 결과, 생성된 시놉시스/장르/태그, 품질점수 변화, 외부메타 매칭. LLM 처리 관찰 UI를 이 단계 패널 설계에 포함할 것.

## ASCII 와이어프레임

```
┌─ ② AI처리  (waiting → processing) ───────────────────────────┐
│ ⚙ 설정 ─────────────────────────────────────────────────────│
│  처리 모드   ◉ 수동(이 단계만 정지)  ○ 자동(조건충족 시 연쇄)   │
│  자동 진행조건  품질점수 ≥ [ 90 ]  → 다음 단계 자동 / 미만 정지 │
│  외부 메타     ☑ TMDB   ☑ KOBIS                              │
│─────────────────────────────────────────────────────────────│
│ 📋 대기 항목(waiting)                       [5건]   [↻]      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │☑ 영화 기생충      #1213  점수 —   waiting             │   │
│  │☑ 영화 부산행      #1214  점수 —   waiting             │   │
│  │☐ 영화 범죄도시    #1215  점수 —   waiting             │   │
│  └─────────────────────────────────────────────────────┘   │
│  [▶ 선택 처리(2)]   [▶ 전체 처리(5)]                         │
│─────────────────────────────────────────────────────────────│
│ 📡 진행 로그(실시간 폴링)                                     │
│  10:32:01 #1213 기생충  processing 시작                       │
│  10:32:04 #1213  TMDB✓(496243) · 품질82 · synopsis/genre 생성 │
│  10:32:04 #1213  → 수동모드: processing 정지                  │
│─────────────────────────────────────────────────────────────│
│ 📊 결과  처리 2 · 정지(processing) 2 · 연쇄 0 · 실패 0         │
└───────────────────────────────────────────────────────────┘
```

## 컴포넌트 트리 (`page.tsx` 내)
```
AiProcessPanel   (기존 BatchAiTrigger 대체)
├─ ProcessSettings   — mode(manual/auto) · scoreThreshold · sources{tmdb,kobis}
├─ WaitingItemList   — 체크박스 선택 + 점수/상태 컬럼 (listContents)
├─ ProcessActions    — 선택처리 / 전체처리
├─ ProgressLog       — 폴링 기반 이벤트 라인 (stage_event 또는 status diff)
└─ ResultSummary     — 처리/정지/연쇄/실패 집계
```

## 데이터 / API 요구사항
| 필요 | 현재 | 추가 |
|---|---|---|
| 대기 목록+점수 | `listContents({status:waiting, cp_name})` ✓ | — |
| 처리 트리거 | `bulkProcess({ids})` ✓ | `{auto_chain, score_threshold, sources}` 확장 |
| 진행 로그 | `stage_event` 테이블 / LiveEventLog SSE | content status 폴링 또는 stage_event 조회 엔드포인트 |
| 평가값(점수/외부메타) | `getContent(id)`→quality_score·score_breakdown·external_sources ✓ | 처리 후 폴링 재조회 |

## 상태 처리
- empty: "대기(waiting) 항목 없음 — ① 생성에서 업로드"
- loading: 목록 스피너 / 처리 버튼 disabled+스피너
- error: 빨강 배너 (기존 패턴)
- 폴링: 처리 후 2초 간격 summary+선택항목 status 재조회, 전부 전이 완료 시 중단

## 재사용 자산
- 탭/버튼/배너: 기존 콘솔 패턴
- 점수·외부소스: `StagingItem` / `MetadataDiffPanel` 참고
- 진행 로그: `components/contents/pipeline/LiveEventLog.tsx` 패턴

## 단계 (index.json steps)
1. BE: process_content_ai 파라미터화 + 수동 정지 + 라우터 전달
2. BE: /upload/batch auto_process 가드(A안)
3. FE: AiProcessPanel(설정+목록+액션) 1차
4. FE: ProgressLog(폴링) + ResultSummary + 평가값
5. verify: 단계별 수동 진행 E2E

## 미해결 결정사항
1. BE 상태머신 분리 동의 여부 (핵심)
2. 설정값 저장 범위 — 로컬(세션) vs 서버(전역)
3. 로그 소스 — 신규 엔드포인트 vs status 폴링
