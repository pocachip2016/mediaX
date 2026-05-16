# Step 6: AI 추천 fill (선택 최적화)

## 배경
Step 1~5를 거친 후에도, 일부 콘텐츠는 여전히 cast/genres 같은 필드가 비어 있을 수 있음.
- TMDB/KOBIS에 없는 콘텐츠
- 크롤 누락 또는 추출 실패
- 사용자 수동 입력 시 일부 필드 생략

이들을 AI(Gemini/Groq)에게 캐시 데이터를 기반으로 추천받아 자동 채우기.

## 목표
- `missing_fields_task`: celery 비동기 작업
- 각 콘텐츠별 missing 필드 검사 (title은 있는데 cast/genres 없음?)
- `ContentAIResult` 조회 + confidence_score > threshold 값만 사용
- web_search_cache, tmdb_*_cache 활용 컨텍스트 생성
- ContentMetadata.ai_filled 플래그 토글
- 대량 작업 시 배치 처리 (예: 1000건 / 1시간)

## 구현 상세

### 1. ContentMetadata 확장
```python
# models/content.py
class ContentMetadata(Base):
    ...
    ai_filled = Column(Boolean, default=False)  # AI로 채워진 필드 유무
    ai_filled_fields = Column(JSON, nullable=True)  # {"cast": true, "genres": true}
    ai_filled_at = Column(DateTime, nullable=True)
```

### 2. Celery Task
```python
# workers/tasks/metadata_tasks.py

from celery import shared_task
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
import json
from datetime import datetime

@shared_task(queue="metadata")
def fill_missing_metadata(content_id: int, force: bool = False):
    """
    단일 콘텐츠의 missing 필드를 AI로 채우기.
    
    Args:
        content_id: 처리할 content_id
        force: True면 ai_filled=True여도 재처리
    """
    session = get_session()
    
    try:
        content = session.query(Content).get(content_id)
        if not content:
            return {"status": "error", "message": f"Content {content_id} not found"}
        
        metadata = session.query(ContentMetadata).filter_by(content_id=content_id).first()
        if not metadata:
            return {"status": "skip", "message": "No metadata"}
        
        # 이미 채워졌으면 스킵
        if metadata.ai_filled and not force:
            return {"status": "skip", "message": "Already filled"}
        
        # 1. Missing 필드 검사
        missing_fields = check_missing_fields(content, metadata)
        if not missing_fields:
            return {"status": "skip", "message": "No missing fields"}
        
        # 2. AI 결과 조회 (existing ContentAIResult)
        ai_results = session.query(ContentAIResult).filter(
            ContentAIResult.content_id == content_id,
            ContentAIResult.is_final == True,
        ).all()
        
        filled_data = {}
        
        for field in missing_fields:
            # 3. ContentAIResult에서 이 필드의 값과 confidence 조회
            best_result = None
            best_confidence = 0
            
            for ai_rec in ai_results:
                result_json = ai_rec.result_json or {}
                if field in result_json:
                    confidence = result_json.get(f"{field}_confidence", 0.5)
                    if confidence > best_confidence and confidence > 0.7:
                        best_result = result_json[field]
                        best_confidence = confidence
            
            # 4. confidence > 0.7이면 채우기
            if best_result and best_confidence > 0.7:
                filled_data[field] = {
                    "value": best_result,
                    "confidence": best_confidence,
                }
        
        # 5. 채워진 데이터를 content_metadata와 관계 테이블에 저장
        if filled_data:
            # 예: cast → content_credits
            if "cast" in filled_data:
                cast_list = filled_data["cast"]["value"]
                if isinstance(cast_list, list):
                    for name in cast_list:
                        credit = ContentCredit(
                            content_id=content_id,
                            name=name,
                            role="cast",
                            source="ai",  # AI로 추가됨
                        )
                        session.add(credit)
            
            # 예: genres → content_genres
            if "genres" in filled_data:
                genres_list = filled_data["genres"]["value"]
                if isinstance(genres_list, list):
                    for genre_name in genres_list:
                        # genre_codes에서 lookup
                        genre_code = session.query(GenreCode).filter_by(name=genre_name).first()
                        if genre_code:
                            genre_rel = ContentGenre(
                                content_id=content_id,
                                genre_code_id=genre_code.id,
                                source="ai",
                                is_primary=False,
                            )
                            session.add(genre_rel)
            
            # metadata 플래그 업데이트
            metadata.ai_filled = True
            metadata.ai_filled_fields = {k: True for k in filled_data.keys()}
            metadata.ai_filled_at = datetime.utcnow()
        
        session.commit()
        return {
            "status": "success",
            "content_id": content_id,
            "filled_fields": list(filled_data.keys()),
            "count": len(filled_data),
        }
    
    except Exception as e:
        session.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        session.close()


@shared_task(queue="metadata")
def batch_fill_missing_metadata(content_ids: Optional[List[int]] = None, limit: int = 100):
    """
    대량 콘텐츠의 missing 필드 채우기.
    
    Args:
        content_ids: 처리할 content_id 목록 (None이면 자동 감지)
        limit: 배치당 처리 건수
    """
    session = get_session()
    
    try:
        # 1. Processing 대상 콘텐츠 조회
        if content_ids:
            query = session.query(Content.id).filter(Content.id.in_(content_ids))
        else:
            # ai_filled=False인 콘텐츠만 자동 감지
            query = session.query(Content.id).join(
                ContentMetadata
            ).filter(
                ContentMetadata.ai_filled == False,
            ).limit(limit)
        
        to_process = [row[0] for row in query.all()]
        
        if not to_process:
            return {"status": "skip", "message": "No content to process"}
        
        # 2. 각 콘텐츠를 task로 enqueue
        from celery import group
        
        job = group([
            fill_missing_metadata.s(cid) for cid in to_process
        ])
        
        result = job.apply_async()
        
        return {
            "status": "queued",
            "count": len(to_process),
            "task_id": result.id,
        }
    
    finally:
        session.close()


def check_missing_fields(content: Content, metadata: ContentMetadata) -> List[str]:
    """
    콘텐츠의 누락 필드 검사.
    반환: ['cast', 'genres', ...]
    """
    missing = []
    
    # 이 값들이 비어 있으면 missing으로 표시
    if not content.synopsis or metadata.synopsis_completeness < 0.5:
        missing.append("synopsis")
    
    # content_credits에서 cast가 0개?
    # session.query(ContentCredit).filter(...).count() == 0
    # → 'cast' missing
    
    # content_genres에서 genre가 0개?
    # → 'genres' missing
    
    # 이건 service 함수에서 구현 (session 필요)
    
    return missing
```

### 3. 라우터 엔드포인트 (선택)
```python
# router.py

@router.post("/metadata/ai-fill")
async def trigger_ai_fill(
    content_id: Optional[int] = None,
    batch: bool = False,
):
    """
    AI fill 작업 수동 트리거.
    
    ?content_id=1 → 단일 콘텐츠
    ?batch=true → 대량 (limit=100)
    """
    from workers.tasks.metadata_tasks import fill_missing_metadata, batch_fill_missing_metadata
    
    if content_id:
        task = fill_missing_metadata.delay(content_id)
        return {"status": "queued", "task_id": task.id}
    elif batch:
        task = batch_fill_missing_metadata.delay(limit=100)
        return {"status": "queued", "task_id": task.id}
    else:
        return {"error": "content_id or batch required"}
```

### 4. Beat 스케줄 (선택)
```python
# shared/celery_config.py

from celery.schedules import crontab

app.conf.beat_schedule = {
    ...
    "fill-missing-metadata-daily": {
        "task": "workers.tasks.metadata_tasks.batch_fill_missing_metadata",
        "schedule": crontab(hour=2, minute=0),  # 매일 2시
        "args": (None, 200),  # limit=200
    },
}
```

## 검증 방법
```bash
# 1. Task 실행 (직접)
curl -X POST http://localhost:8000/api/programming/metadata/ai-fill?content_id=1

# 2. Task 상태 확인
curl http://localhost:8000/api/programming/metadata/task-status/{task_id}

# 3. DB 검증
sqlite3 media_ax_dev.db << EOF
SELECT COUNT(*) FROM content_metadata WHERE ai_filled = true;
SELECT ai_filled_fields FROM content_metadata WHERE ai_filled = true LIMIT 1;

SELECT COUNT(*) FROM content_credits WHERE source = 'ai';
SELECT COUNT(*) FROM content_genres WHERE source = 'ai';
EOF

# 4. 통계 조회
curl http://localhost:8000/api/programming/metadata/dashboard | grep ai_filled
```

## 영향 범위
- 백엔드: Celery task 1개, 라우터 엔드포인트 1개
- DB: ContentMetadata에 3개 컬럼 추가 (ai_filled, ai_filled_fields, ai_filled_at)
- 성능: 비동기 처리이므로 동기 엔드포인트 영향 없음
- 캐시: web_search_cache, tmdb_*_cache 활용 (기존 가정)

## 주의
- confidence_score 임계값 설정 (0.7은 예시, 실제 데이터로 조정)
- ContentAIResult.is_final=True만 사용 (draft 제외)
- Celery worker 실행 전제 (production은 필수)
- cast/genres가 배열 vs 문자열 타입 혼재 → 정규화 필요
- 대량 작업 시 배치 크기 조정 (메모리 고려)

## 선택 사항
- Step 6은 Step 1~5 완료 후 "나머지 최적화"로 분류
- 초기 버전은 UI 없이 API 호출(또는 수동 task trigger)로만 진행 가능
- 향후 대시보드에 "AI fill 현황" 카드 추가 가능
