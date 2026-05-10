# backend/api/meta_core/ — 메타 인텔리전스 레이어

## 역할
- Dam public API (read-only export, changefeed, feedback)
- 메타 인텔리전스 파이프라인 (candidate → match → suggestion → resolution → seed → promote)

## 모듈 인덱스

### Phase B (완료)
| 경로 | 역할 |
|------|------|
| `public_api/` | Dam 연동 API (`/contents/since`, `/dam-events`) |
| `models/intelligence.py` | MetadataCandidate / MatchEdge / FieldSuggestion / FieldResolution |
| `scoring.py` | match_score 산식 (동일성 판정, 0~1) |
| `gap.py` | Gap Analyzer — 콘텐츠별 누락 필드 탐지 |
| `field_strategy.py` | 필드 5분류 카탈로그 (FIELD_STRATEGIES) |
| `aggregator.py` | Field Aggregator — Strategy 적용 → FieldResolution |
| `intelligence/router.py` | Resolution API + SEED promote 엔드포인트 |

### Phase C (완료)
| 경로 | 역할 |
|------|------|
| `models/seed.py` | ContentSeed / SeedDiscoveryLog ORM |
| `clients/kobis_client.py` | KOBIS API 클라이언트 |
| `clients/omdb_client.py` | OMDb API 클라이언트 |
| `discovery/` | DiscoverySource ABC + TMDB/KOBIS/KMDB/OMDb 구현체 |
| `discovery/dedup.py` | match_or_create_seed — 4단계 dedup |
| `discovery/promote.py` | promote_seed — SEED→Content 승격 |
| `intelligence/seed_router.py` | SEED 검수 API (GET /seeds*, POST lock/accept/reject/edit/bulk-promote) |
| `intelligence/seed_schemas.py` | SEED 검수 Pydantic 스키마 |

## Score Conventions

| 점수 | 정의 | 범위 | 위치 |
|------|------|------|------|
| `quality_score` | 콘텐츠 메타 완성도 | 0~100 | `ContentMetadata.quality_score` |
| `match_score` | candidate ↔ Content 동일성 | 0.0~1.0 | `MatchEdge.score` |

두 점수는 이름 충돌 금지. 로그 prefix: `[quality]` / `[match]`.

## 참조
- ADR: `docs/dev/phase-c/` (SEED 라이프사이클·소스 우선순위·승격가드)
- task plan: `plans/dev-meta-intelligence-phase-c/`
