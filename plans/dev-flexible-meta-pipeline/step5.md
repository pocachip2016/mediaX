# Step 5: Watcha 데이터 재크롤

## 배경
기존 Watcha 크롤(679건)에서 감독, 출연진이 수집되지 않음.
CSV 변환 단계(04_to_upload_csv.py)에서 genres, country, runtime도 버려짐.
이번 재크롤에서 모든 메타를 수집해서 Step 2 벌크 API로 재업로드.

## 목표
- 기존 더미 2,130건 삭제 후 real Watcha 1,158건만 유지
- 크롤러 04_to_upload_csv.py 확대: 5열 → 8열 (+ cast, directors, genres)
- 크롤러에서 cast/director 추출 추가
- 재처리 후 벌크 업로드 + resolution 트리거
- content_credits 테이블 채워지는 것 검증

## 구현 상세

### 1. 크롤러 수정 (02_crawl_details.py)
```python
# backend/scripts/watcha_real/02_crawl_details.py
# 기존: genres, country, runtime, rating_age, synopsis, poster_url 수집

# 추가: cast, directors 추출

async def extract_cast_and_directors(session, soup):
    """
    Watcha 상세 페이지에서 출연진, 감독 추출
    예: <div class="cast-item"> <span>배우명</span> <span>역명</span> </div>
    """
    cast = []
    directors = []
    
    # Watcha 페이지 DOM 구조에 맞춰 파싱
    # (실제 페이지 구조 확인 필요)
    cast_section = soup.select(".cast-list .cast-item")
    for item in cast_section:
        name_el = item.select_one(".cast-name")
        char_el = item.select_one(".character-name")
        if name_el:
            cast.append({
                "name": name_el.get_text(strip=True),
                "character": char_el.get_text(strip=True) if char_el else "",
            })
    
    director_section = soup.select_one(".director-info")
    if director_section:
        dir_text = director_section.get_text(strip=True)
        # "감독: 감독1, 감독2" → ["감독1", "감독2"]
        directors = [d.strip() for d in dir_text.split(":")[1].split(",")]
    
    return cast, directors
```

### 2. CSV 변환 확대 (04_to_upload_csv.py)
```python
# backend/scripts/watcha_real/04_to_upload_csv.py

import pandas as pd
import json

def convert_to_upload_csv():
    """detail_real.csv → watcha_upload.csv (8열)"""
    
    df = pd.read_csv("detail_real.csv")
    
    # 필드명 확인 (기존: slug, url, title, year, genres, country, runtime, rating_age, synopsis, poster_url, content_type)
    
    # 새로운 8열 지정
    upload_df = pd.DataFrame({
        "title": df["title"],
        "production_year": df["year"],
        "content_type": df["content_type"] or "movie",
        "cp_name": "watcha",  # 고정
        "synopsis": df["synopsis"],
        "cast": df["cast"].apply(lambda x: ", ".join([c["name"] for c in json.loads(x)]) if x else ""),
        "directors": df["directors"].apply(lambda x: ", ".join(x) if x else ""),
        "genres": df["genres"],  # "드라마/, 판타지/" → "드라마, 판타지"
        "country": df["country"],
        "runtime": df["runtime"],  # int 그대로 또는 문자열
        "rating_age": df["rating_age"],
        "poster_url": df["poster_url"],
    })
    
    # 기존 watcha_upload.csv 제거 (또는 backup)
    upload_df.to_csv("watcha_upload.csv", index=False, encoding="utf-8")
    print(f"변환 완료: {len(upload_df)} 행")

if __name__ == "__main__":
    convert_to_upload_csv()
```

### 3. 재업로드 스크립트
```bash
# backend/scripts/watcha_real/05_bulk_upload.sh

#!/bin/bash

# Watcha 정제 CSV를 벌크 업로드 API로 전송
# 전제: Step 0 더미 삭제 완료, Step 2 벌크 API 구현 완료

CSV_FILE="watcha_upload.csv"
API_URL="http://localhost:8000/api/programming/metadata/upload/batch"

if [ ! -f "$CSV_FILE" ]; then
    echo "ERROR: $CSV_FILE not found"
    exit 1
fi

echo "업로드 시작: $CSV_FILE"
curl -X POST \
    -F "file=@$CSV_FILE" \
    "$API_URL"

echo "업로드 완료"
```

### 4. 데이터 정규화 (선택)
Watcha 크롤 데이터 정제:
```python
# genres: "드라마/, 판타지/" → "드라마, 판타지"
def clean_genres(genre_str):
    if not genre_str:
        return ""
    return ", ".join(g.strip().rstrip("/") for g in genre_str.split(",") if g.strip())
```

## 검증 방법
```bash
# 1. 재크롤 실행 (선택, 이미 데이터 있으면 스킵)
# python 02_crawl_details.py  # cast, directors 추출 추가 확인

# 2. CSV 변환 재실행
python 04_to_upload_csv.py
# 확인: watcha_upload.csv의 헤더 = [title, production_year, content_type, cp_name, synopsis, cast, directors, genres, country, runtime, rating_age, poster_url]
# 확인: cast, directors 컬럼 채워짐

# 3. 벌크 업로드 실행
bash 05_bulk_upload.sh

# 4. DB 검증
sqlite3 media_ax_dev.db << EOF
SELECT COUNT(*) FROM external_meta_sources WHERE source = 'bulk_upload' AND raw_json LIKE '%cast%';
-- 결과: ~1,158 (Watcha 콘텐츠 수)

SELECT COUNT(*) FROM content_credits WHERE role = 'cast' AND content_id IN (SELECT id FROM contents WHERE cp_name = 'watcha');
-- 결과: > 0 (resolution 완료 후 credits 저장)

SELECT content_id, GROUP_CONCAT(name) FROM content_credits WHERE role = 'director' GROUP BY content_id LIMIT 5;
-- 감독명이 정규화되어 저장됨
EOF

# 5. API 검증
curl "http://localhost:8000/api/programming/metadata/contents?cp_name=watcha&limit=1" | jq '.data[0]' | grep -E "directors|cast|genres"
```

## 영향 범위
- 크롤러: cast/directors 추출 로직 추가 (2 파일 수정)
- CSV: 필드 8개로 확대, 데이터 정제
- DB: external_meta_sources 재저장, content_credits 대량 채우기
- 후속: Step 6에서 AI fill 필요한 필드만 자동 채우기

## 주의
- Step 0 (더미 삭제)가 선행되어야 재크롤 데이터가 clean함
- Watcha 크롤 페이지 구조 변경 시 셀렉터 재확인 필요
- 기존 크롤 결과(detail_real.csv)가 남아 있어야 함
- cast/directors 추출 실패해도 다른 필드는 영향 없음 (선택 필드)
- Step 2 벌크 API가 먼저 구현되어야 업로드 가능
