# Step 2: 벌크 업로드 API 확장 + PUT 엔드포인트

## 배경
현재 벌크 업로드 API가 CSV에서 5개 필드만 인식 (title, production_year, content_type, cp_name, synopsis).
나머지 메타(cast, directors, genres, country, runtime, rating_age, poster_url)는 무시됨.
수정/편집 기능도 없음.

## 목표
- CSV/Excel 필드 확대: 8열 표준화 (기존 5 + cast + directors + genres)
- 데이터 흐름: CSV → external_meta_sources(raw_json) → resolve_metadata() 호출 → credits/genres/images 분산
- PUT `/contents/{id}` 엔드포인트: 기존 콘텐츠 수정 (resolution 재실행)
- POST `/contents/search/external` 엔드포인트: TMDB/KOBIS 외부 검색 (select → bulk add 경험)

## 구현 상세

### 1. 스키마 확장 (CSV/Excel)
```python
# schemas.py
class BulkUploadRequest(BaseModel):
    title: str  # 필수
    production_year: Optional[int]
    content_type: Literal["movie", "series", "season", "episode"]  # 필수
    cp_name: str  # 필수
    synopsis: Optional[str]  # 글자메타
    cast: Optional[str]  # "배우1, 배우2, ..." → JSON parse
    directors: Optional[str]  # "감독1, 감독2, ..."
    genres: Optional[str]  # "드라마, 판타지, ..."
    country: Optional[str]
    runtime: Optional[int]  # 분 단위
    rating_age: Optional[str]  # "전체이용가", "12세이상", ...
    poster_url: Optional[str]
```

### 2. 벌크 업로드 API 개선
```python
# router.py

@router.post("/upload/batch", response_model=List[ContentOut])
async def batch_upload(
    file: UploadFile,
    session: AsyncSession,
):
    """CSV/Excel 대량 업로드 → external_meta_sources → resolution"""
    
    # 1. 파일 파싱 (기존 코드)
    df = pd.read_csv(file.file) or openpyxl...
    
    # 2. 각 행을 external_meta_sources로 저장
    created_contents = []
    for idx, row in df.iterrows():
        # Content 기본 정보만 먼저 생성
        content = Content(
            title=row["title"],
            content_type=row["content_type"],
            production_year=row.get("production_year"),
            cp_name=row.get("cp_name"),
        )
        session.add(content)
        await session.flush()  # ID 확보
        
        # 3. 입력 데이터를 external_meta_sources에 raw_json으로 저장
        # (source="manual" 또는 "bulk_upload")
        raw_json = {
            "title": row["title"],
            "synopsis": row.get("synopsis"),
            "cast": _parse_list(row.get("cast")),  # "A, B" → ["A", "B"]
            "directors": _parse_list(row.get("directors")),
            "genres": _parse_list(row.get("genres")),
            "country": row.get("country"),
            "runtime": row.get("runtime"),
            "rating_age": row.get("rating_age"),
            "poster_url": row.get("poster_url"),
        }
        
        external = ExternalMetaSource(
            content_id=content.id,
            source="bulk_upload",  # 또는 "manual"
            raw_json=raw_json,
            matched_at=datetime.utcnow(),
        )
        session.add(external)
        
        created_contents.append(content)
    
    await session.commit()
    
    # 4. resolve_metadata() 호출해서 credits/genres/images 분산
    for content in created_contents:
        await resolve_metadata(content.id, session)
    
    await session.commit()
    return created_contents

def _parse_list(val: Optional[str]) -> Optional[List[str]]:
    """'A, B, C' → ['A', 'B', 'C']"""
    if not val:
        return None
    return [x.strip() for x in str(val).split(",") if x.strip()]
```

### 3. PUT 엔드포인트 (기존 콘텐츠 수정)
```python
# schemas.py
class ContentUpdateRequest(BaseModel):
    title: Optional[str]
    synopsis: Optional[str]
    cast: Optional[str]
    directors: Optional[str]
    genres: Optional[str]
    country: Optional[str]
    runtime: Optional[int]
    rating_age: Optional[str]
    poster_url: Optional[str]
    # 기본 필드는 step 4 UI에서만 수정 (production_year, content_type은 고정)

# router.py
@router.put("/contents/{content_id}", response_model=ContentOut)
async def update_content(
    content_id: int,
    req: ContentUpdateRequest,
    session: AsyncSession,
):
    """기존 콘텐츠 수정 → external_meta_sources 추가 → resolve 재실행"""
    
    # 1. Content 조회
    content = await session.get(Content, content_id)
    if not content:
        raise HTTPException(status_code=404)
    
    # 2. 변경사항을 external_meta_sources에 "manual" source로 저장
    manual_json = {}
    for field in ["title", "synopsis", "cast", "directors", "genres", "country", "runtime", "rating_age", "poster_url"]:
        val = getattr(req, field)
        if val is not None:
            manual_json[field] = val
    
    if manual_json:
        external = ExternalMetaSource(
            content_id=content_id,
            source="manual",
            raw_json=manual_json,
            matched_at=datetime.utcnow(),
        )
        session.add(external)
        await session.flush()
    
    # 3. resolution 재실행 (manual source가 manual_override로 작동)
    await resolve_metadata(content_id, session)
    await session.commit()
    
    return await session.get(Content, content_id)
```

### 4. 외부 검색 API (선택, step 3에서 구현)
```python
@router.get("/search/external", response_model=List[Dict])
async def search_external(q: str, source: Literal["tmdb", "kobis"] = "tmdb"):
    """TMDB/KOBIS 검색 → 결과 리스트 → 선택 → 벌크 추가"""
    # 구현: ai_engine.py에서 existing search_tmdb() 활용
    # 결과: [{"title": "...", "external_id": "...", "raw_json": {...}}]
    pass
```

## 검증 방법
```bash
# 1. CSV 생성 (8열)
cat > /tmp/test_upload.csv << EOF
title,production_year,content_type,cp_name,synopsis,cast,directors,genres
영화제목,2020,movie,CP사,재미있는 이야기,배우1 배우2,감독1,드라마 판타지
EOF

# 2. API 테스트
curl -X POST http://localhost:8000/api/programming/metadata/upload/batch \
  -F "file=@/tmp/test_upload.csv"

# 3. DB 확인
sqlite3 media_ax_dev.db "SELECT COUNT(*) FROM external_meta_sources WHERE source='bulk_upload';"
sqlite3 media_ax_dev.db "SELECT COUNT(*) FROM content_credits WHERE content_id=<new_id>;"  # credits 저장됨
```

## 영향 범위
- CSV 스키마: 필드 8개로 확대
- API: batch_upload 개선, PUT 추가, search_external 스텁 추가
- DB: external_meta_sources 행 증가
- 후속: Step 3(UI 분해), Step 4(수동 입력 양식)

## 주의
- cast/directors를 쉼표 구분 문자열로 입력받는데, 각 외부 소스는 JSON 배열로 저장 → _parse_list()로 정규화
- external_meta_sources 중복 검사 (같은 source에서 2번 insert하면 안됨) → matched_at로 최신만 사용
- resolution()이 idempotent하도록 설계 (여러 번 호출 가능)
