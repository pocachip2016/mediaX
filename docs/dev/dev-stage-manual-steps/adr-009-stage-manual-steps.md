# ADR-009 — 단계별 수동 테스트: 내부처리 ↔ 다음단계 분리 + 멀티스텝 STEP화

## 맥락
파이프라인 테스트 콘솔(`/programming/contents/pipeline`)에서 단계별 동작을 검증하려면,
각 단계의 "내부처리"와 "다음 단계로의 전이"를 따로 실행·관찰할 수 있어야 한다.
현재는 둘이 결합돼 있다 — enrich 실행 = 처리 + `enriched` 동시, AI 실행 = 처리 + `ai` 동시.
또한 내부처리가 여러 하위 작업으로 구성된 단계(S2 보완, S3 AI)는 하위 작업을 개별 검증할 수 없다.

## 결정
1. **내부처리(work) ↔ 다음단계(status bump) 분리**
   - `[내부처리 sub-step]`: stage work 실행, 결과만 기록, **status 불변**.
   - `[다음단계로 →]`: work 없이 status 1칸 진행 + StageEvent 기록.
2. **멀티스텝 내부처리 분해 (sub-step 단건 실행)**
   - **S2 보완**: TMDB 캐시 / KMDB 캐시 / WebSearch — 3개 소스 개별 실행.
   - **S3 AI처리**: `AI_TASK_REGISTRY` 5태스크(번역/짧은요약/장르/무드/키워드) 개별 실행 + 품질점수 재계산.
     monolithic `_generate_metadata_with_engine` → registry 기반으로 전환.
   - **S1 생성**: 내부처리 없음(레코드 생성=결정적). [다음단계로]만.
   - **S4 검수 / S5 승인 / S6 게시**: 단일 액션.
3. **AUTO(advance-out, ADR-009 stage-auto-policy)와 공존**: AUTO ON이면 자동 실행, OFF면 수동 버튼.

## 상태 모델
`raw → enriched → ai → review → approved → published` (ContentStatus).
[다음단계로]는 이 순서로 1칸 진행. 내부처리는 status를 바꾸지 않는다.

## 엔드포인트
- `POST /test/pipeline/advance` `{ids}` — status 1칸 진행(work 없음).
- `POST /test/pipeline/enrich-source` `{content_id, source: tmdb|kmdb|websearch}` — 단일 소스 회수.
- `POST /test/pipeline/run-ai-task` `{content_id, task_name}` — registry 단일 AiTask 실행.

## 비결정 / 후속
- WebSearch sub-step은 EnrichPolicy.use_websearch 게이트 준수.
- 게시(S6) 내부처리는 미구현(stub).
