# Step 4: gap-analyzer

> GitHub: 미생성 | Milestone: dev-meta-intelligence (Phase B — 골격, B 진입 시점에 상세화)

## 읽어야 할 파일
- `docs/dev/meta-intelligence.md` (§2 필드 5분류)
- `backend/api/meta_core/models/intelligence.py`
- `backend/api/programming/metadata/models/content.py` (Content + ContentMetadata 필드 풀)

## 목적
콘텐츠별로 "어떤 필드가 비어 있고 어떤 외부 소스를 시도해야 하는지" 산출하는 함수.
다음 step5 (enrich) 의 입력.

## 작업 (윤곽)
- `backend/api/meta_core/gap.py` 신설
- `analyze_gap(content_id) -> GapReport`
  - GapReport: missing_fields[Field], recommended_sources[ExternalSourceType], priority(int)
  - 내부 정책: poster 없음 → [tmdb, kmdb], cast 비음 → [tmdb, kmdb, kobis], synopsis 짧음(<50자) → [tmdb, kmdb, websearch]
- `analyze_gap_batch(filters) -> list[GapReport]` (대시보드용)
- 단위 테스트: 빈 컨텐츠 / 일부 채워진 컨텐츠 / 풀필드 컨텐츠 3 케이스

## Acceptance Criteria
```bash
python3 -c "from api.meta_core.gap import analyze_gap; print('OK')"
pytest backend/tests/meta_core/test_gap.py
bash .claude/verify.sh meta-intelligence-step4
```

## 금지사항
- **외부 API 호출 금지.** 본 step 은 내부 DB 만 보는 분석 모듈.
  이유: 호출은 step5 에서. 분석·실행 분리.
- **scoring.py 호출 금지.** Gap 은 "무엇이 비었나", scoring 은 "얼마나 같은가". 다른 책임.
