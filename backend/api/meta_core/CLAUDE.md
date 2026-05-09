# backend/api/meta_core/ — 메타 인텔리전스 레이어

## 역할
- Dam public API (read-only export, changefeed, feedback)
- 메타 인텔리전스 파이프라인 (candidate → match → suggestion → resolution → seed)

## 모듈 인덱스
| 경로 | 역할 | 상태 |
|------|------|------|
| `public_api/` | Dam 연동 API (`/contents/since`, `/dam-events`) | ✅ 완료 |
| `models/intelligence.py` | MetadataCandidate / MatchEdge / FieldSuggestion / FieldResolution / SeedCandidate | ✅ 완료 |
| `scoring.py` | match_score 산식 (동일성 판정, 0~1) | ✅ 완료 |
| `gap.py` | Gap Analyzer — 콘텐츠별 누락 필드 탐지 | 예정 (step4) |
| `field_strategy.py` | 필드 5분류 카탈로그 | 예정 (step6) |
| `aggregator.py` | Field Aggregator — Strategy 적용 → FieldResolution | 예정 (step7) |

## Score Conventions

| 점수 | 정의 | 범위 | 위치 |
|------|------|------|------|
| `quality_score` | 콘텐츠 메타 완성도 | 0~100 | `ContentMetadata.quality_score` |
| `match_score` | candidate ↔ Content 동일성 | 0.0~1.0 | `MatchEdge.score` |

두 점수는 이름 충돌 금지. 로그 prefix: `[quality]` / `[match]`.

## 참조
- 상세 설계: `docs/dev/meta-intelligence.md`
- task plan: `plans/dev-meta-intelligence/`
