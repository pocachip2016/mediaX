# Step 0 — distribution-schema

> **목표**: ContentDistribution / ServiceCategory / DeviceVariant 3개 테이블 + SQLAlchemy 모델 + alembic 마이그레이션

## 배경
- `contents` 테이블은 메타 권위(타이틀·장르·인물) SSOT
- OTT/IPTV는 **유통채널** — ExternalMetaSource와 분리 원칙 (plan decisions 참조)
- 마이그레이션 번호: `0014` (0013은 Phase D WebSearch — fix/scheduled-tasks-and-poster-aspect에서 사용, 머지 후 번호 충돌 주의)

## 신규 테이블 설계

### 1. `content_distributions` (ContentDistribution)
```sql
id             INTEGER PK
content_id     INTEGER FK contents.id NOT NULL
channel        VARCHAR(50) NOT NULL   -- "iptv_genie" | "ott_watcha" | "ott_netflix" | "ott_wave" | "ott_tving"
channel_type   VARCHAR(20) NOT NULL   -- "iptv" | "ott"
external_id    VARCHAR(200)           -- 채널 내부 ID (IPTV VOD_ID, OTT 콘텐츠 ID)
available_from DATE
available_until DATE
is_exclusive   BOOLEAN DEFAULT false
popularity_rank INTEGER               -- OTT 인기 순위 (Top10 등)
popularity_score FLOAT                -- 정규화 점수 0.0~1.0
raw_data       JSON                   -- 채널별 원본 응답 보존
synced_at      DATETIME DEFAULT now()
created_at     DATETIME DEFAULT now()

UNIQUE(content_id, channel)           -- 채널당 1개 유통 항목
INDEX(channel, channel_type)
INDEX(content_id)
```

### 2. `service_categories` (ServiceCategory)
```sql
id             INTEGER PK
name           VARCHAR(200) NOT NULL   -- "지니TV 오늘의 추천" | "주간 TOP10"
category_type  VARCHAR(50) NOT NULL    -- "recommendation" | "ranking" | "editorial" | "seasonal"
platform       VARCHAR(50) NOT NULL    -- "iptv_genie" | "ott_watcha" | ...
position       INTEGER DEFAULT 0       -- 카테고리 내 순서
is_active      BOOLEAN DEFAULT true
created_at     DATETIME DEFAULT now()
updated_at     DATETIME DEFAULT now()
```

### 3. `service_category_items` (ServiceCategoryItem)
```sql
id             INTEGER PK
category_id    INTEGER FK service_categories.id NOT NULL
content_id     INTEGER FK contents.id NOT NULL
rank           INTEGER NOT NULL        -- 카테고리 내 순위
score          FLOAT                   -- 큐레이션 점수
added_at       DATETIME DEFAULT now()

UNIQUE(category_id, content_id)
INDEX(category_id, rank)
```

### 4. `device_variants` (DeviceVariant)
```sql
id             INTEGER PK
content_id     INTEGER FK contents.id NOT NULL
device_type    VARCHAR(20) NOT NULL   -- "mobile" | "tv" | "pc" | "tablet"
resolution     VARCHAR(20)            -- "4K" | "1080p" | "720p" | "480p"
format         VARCHAR(20)            -- "MP4" | "HLS" | "DASH" | "TS"
bitrate_kbps   INTEGER
drm_type       VARCHAR(50)            -- "widevine" | "fairplay" | "playready"
is_available   BOOLEAN DEFAULT true
created_at     DATETIME DEFAULT now()

UNIQUE(content_id, device_type, resolution)
INDEX(content_id)
```

## 구현 파일
```
backend/api/distribution/
├── __init__.py
├── models.py          # 4개 SQLAlchemy 모델
├── schemas.py         # Pydantic I/O 스키마
├── router.py          # GET /api/distribution/... (읽기 전용, Step 0)
└── service.py         # 기본 CRUD

backend/alembic/versions/
└── 0014_distribution_tables.py

main.py                # distribution_router 마운트
alembic/env.py         # 모델 import 추가
```

## 검증 기준
- [ ] `alembic upgrade head` 오류 없음
- [ ] `GET /api/distribution/contents/{id}/channels` → 200 (빈 목록 허용)
- [ ] `GET /api/distribution/categories` → 200
- [ ] `GET /api/distribution/contents/{id}/devices` → 200
- [ ] `python -m pytest tests/test_distribution_step0.py` → 최소 6 케이스 pass
