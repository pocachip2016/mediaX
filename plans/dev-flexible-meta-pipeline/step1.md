# Step 1: Resolution Service 구현

## 배경
현재 메타 데이터가 여러 소스(TMDB, KOBIS, Watcha, CP 이메일, 수동 입력)에서 분산 저장되어 있음.
`external_meta_sources` 테이블에는 raw_json으로 저장되지만, 이를 통합해서 final_* 값을 결정하는 로직이 없음.
부재하거나 충돌하는 필드를 해결할 유연한 병합 전략 필요.

## 목표
- `resolve_metadata()` 서비스 함수: external_meta_sources → Content + content_credits + content_genres + content_images + content_metadata 동기화
- 필드별 우선순위 적용: manual > tmdb > kobis > watcha > ai
- `ContentAIResult.confidence_score` 활용해 AI 제안값 채우기
- `content_metadata.score_breakdown` JSON에 각 필드의 source + confidence 기록

## 구현 상세

### 1. 스키마 확장 (existing tables)
#### content_metadata 추가 컬럼
```python
# models/content.py
class ContentMetadata(Base):
    ...
    # 기존: quality_score, cp_*
    score_breakdown = Column(JSON, nullable=True)  # {"field": {"source": "tmdb", "confidence": 0.95}}
    ai_filled = Column(Boolean, default=False)  # Step 6 플래그
```

### 2. resolve_metadata() 함수
```python
# service.py
from typing import Dict, Any

async def resolve_metadata(
    content_id: int,
    session: AsyncSession,
) -> Dict[str, Any]:
    """
    external_meta_sources에서 content_id의 모든 raw_json을 조회하고,
    필드별 우선순위에 따라 winner를 결정해 Content, Credits, Genres, Images 테이블에 분배.
    
    우선순위: manual > tmdb > kobis > watcha > ai
    """
    # 1. external_meta_sources 조회
    sources = await session.execute(
        select(ExternalMetaSource).where(ExternalMetaSource.content_id == content_id)
    )
    
    # 2. 필드 통합 (priority에 따라 winner 선택)
    metadata_dict = {
        "title": {"value": None, "source": None, "confidence": 0},
        "synopsis": {...},
        "genres": {...},  # List[str]
        "cast": {...},   # List[{"name": str, "character": str}]
        "directors": {...},  # List[str]
        "country": {...},
        "runtime": {...},
        "rating_age": {...},
        "poster_url": {...},
    }
    
    # 3. 각 source의 raw_json 파싱해서 metadata_dict 업데이트
    for source_rec in sources:
        source_name = source_rec.source  # "tmdb", "kobis", "watcha", "manual", etc.
        raw_json = source_rec.raw_json or {}
        confidence = 1.0 if source_name == "manual" else 0.8 if source_name == "tmdb" else 0.6
        
        # 필드 추출 (각 source별 파서)
        extracted = _parse_source(source_name, raw_json)
        
        for field, val in extracted.items():
            if val is not None and metadata_dict[field]["confidence"] < _priority(source_name):
                metadata_dict[field] = {
                    "value": val,
                    "source": source_name,
                    "confidence": confidence,
                }
    
    # 4. AI 제안값 (confidence > 0.7) 채우기
    ai_results = await session.execute(
        select(ContentAIResult)
        .where(ContentAIResult.content_id == content_id)
        .where(ContentAIResult.is_final == True)
    )
    for ai_rec in ai_results:
        result_json = ai_rec.result_json or {}
        for field in ["genres", "cast", "directors", "rating_age"]:
            if field in result_json and metadata_dict[field]["value"] is None:
                if result_json.get(f"{field}_confidence", 0) > 0.7:
                    metadata_dict[field] = {
                        "value": result_json[field],
                        "source": "ai",
                        "confidence": result_json.get(f"{field}_confidence", 0.7),
                    }
    
    # 5. 결과를 Content + related tables에 저장
    # - Content.title, .synopsis, .year 등 기본 필드
    # - content_credits (cast/directors 분산)
    # - content_genres (genres → genre_codes lookup)
    # - content_images (poster_url → ContentImage.url)
    # - content_metadata.score_breakdown = {field: {source, confidence}}
    
    return metadata_dict

def _parse_source(source_name: str, raw_json: dict) -> dict:
    """각 소스별 JSON 스키마에 맞춰 표준 필드 추출"""
    if source_name == "tmdb":
        return {
            "title": raw_json.get("title"),
            "synopsis": raw_json.get("overview"),
            "genres": [g["name"] for g in raw_json.get("genres", [])],
            "cast": [{"name": p["name"], "character": p.get("character")} for p in raw_json.get("cast", [])],
            "country": _extract_country(raw_json.get("production_countries", [])),
            "runtime": raw_json.get("runtime"),
            "poster_url": raw_json.get("poster_path"),
        }
    elif source_name == "kobis":
        return {
            "title": raw_json.get("movieNm"),
            "synopsis": raw_json.get("synopsis"),
            "directors": raw_json.get("directorNm", "").split(","),
            "cast": raw_json.get("actorNm", "").split(","),
            "country": raw_json.get("repNationCd"),
            "runtime": raw_json.get("showTm"),
        }
    # ... watcha, manual, etc.
    return {}

def _priority(source_name: str) -> float:
    """우선순위 숫자 (높을수록 우선)"""
    priorities = {
        "manual": 5,
        "tmdb": 4,
        "kobis": 3,
        "watcha": 2,
        "ai": 1,
    }
    return priorities.get(source_name, 0)
```

### 3. 호출 지점
- router.py `/contents/{id}/process` 엔드포인트에서 AI 처리 후 호출
- step 2 벌크 업로드에서 external_meta_sources 저장 후 호출
- step 5 Watcha 재크롤 후 호출

## 검증 방법
```python
# 테스트: TMDB + manual 혼합 content
content_id = 1
metadata = await resolve_metadata(content_id, session)
assert metadata["genres"]["source"] == "tmdb"
assert metadata["synopsis"]["source"] == "manual"  # manual이 있으면 우선
assert metadata["cast"]["confidence"] > 0.6
```

## 영향 범위
- DB: ContentMetadata에 score_breakdown, ai_filled 컬럼 추가 (마이그레이션 필요)
- 성능: external_meta_sources → credits/genres/images 동기화 시 N+1 쿼리 우려 → batch 최적화
- 후속: Step 2, 3, 5, 6에서 이 함수를 호출해서 데이터 동기화

## 주의
- raw_json 파싱 시 누락 필드 처리 철저 (KeyError 방지)
- confidence_score 기본값 설정 (manual=1.0, tmdb=0.8, ai=0.6 등)
- Async + transaction 안의 multi-insert 성능 고려
