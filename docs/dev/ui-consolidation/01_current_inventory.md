# 01. 현재 화면 인벤토리 분석

> Step 0 산출물 — 현재 metadata 관련 11개 페이지 + 인접 영역 매핑.

## 1. 페이지 매트릭스

| # | 경로 | 헤더(h1) | 역할 | 백엔드 API | 진입 빈도 |
|---|------|---------|------|-----------|---------|
| 1 | `/programming/contents` | 콘텐츠 목록 | 전체 콘텐츠 (status 무관) 목록 | `GET /metadata/contents` | 높음 |
| 2 | `/programming/contents/[id]` | (콘텐츠 제목) | 단일 콘텐츠 상세 + 메타 편집 | `GET /metadata/contents/{id}` | 높음 |
| 3 | `/programming/metadata` | 메타데이터 대시보드 | status별 통계 + 목록 (contents 와 중복?) | `GET /metadata/dashboard` | 중간 |
| 4 | `/programming/metadata/create` | 실시간 메타 생성 | 단일 콘텐츠 수동 입력 (AI 보조) | `POST /metadata/generate` | 중간 |
| 5 | `/programming/metadata/upload` | 배치 업로드 | CSV/Excel 일괄 업로드 | `POST /metadata/upload/batch` | 낮음 |
| 6 | `/programming/metadata/staging` | 검토 대기풀 | 외부소스 매칭 완료 콘텐츠 검토 | `GET /metadata/staging` | 중간 |
| 7 | `/programming/metadata/queue` | 검수 큐 | 70~89점 콘텐츠 검수 | `GET /metadata/queue` | 중간 |
| 8 | `/programming/metadata/text` | 글자 메타 | 글자메타(synopsis/genre/tags) 목록 | `GET /metadata/text` | 중간 |
| 9 | `/programming/metadata/text/review` | (미확인, 검수?) | 글자메타 검수 화면 (text 와 분리) | `GET /metadata/text` + filter | 낮음 |
| 10 | `/programming/metadata/image` | 이미지 에셋 | 이미지 메타 목록 | `GET /metadata/image` | 중간 |
| 11 | `/programming/metadata/image/upload` | (미확인) | 이미지 업로드 전용 | `POST /metadata/image/{id}/upload` | 낮음 |
| 12 | `/programming/metadata/video` | 영상 파일 정보 | 영상 메타 목록 | `GET /metadata/video` | 중간 |
| 13 | `/programming/metadata/video/qc` | 영상 QC | 영상 QC 검수 화면 | `GET /metadata/video` + filter | 낮음 |
| 14 | `/monitoring/pipeline` | 파이프라인 모니터링 | 처리 통계/실패 큐/재시도 | `GET /metadata/pipeline/status` | 중간 |
| 15 | `/programming/sources` | 외부 소스 | TMDB/KOBIS/KMDB 동기화 상태 | (sources API) | 낮음 |
| 16 | `/programming/sources/{tmdb,kobis,kmdb}` | (소스명) | 개별 외부소스 캐시 조회 | (sources API) | 낮음 |

## 2. 영역별 분류

### 2.1 콘텐츠 입력 (3개 분산)
- **단일 수동 입력**: `/metadata/create`
- **CSV 배치**: `/metadata/upload`
- **외부 검색에서 가져오기**: ❌ **없음** (sources 페이지는 캐시 조회만)

**문제**: 콘텐츠 추가 진입점이 3개 영역에 흩어짐. 사용자가 "신규 콘텐츠 등록" 액션을 찾기 어려움.

### 2.2 콘텐츠 목록 (2개 중복)
- `/programming/contents` — 전체 목록
- `/programming/metadata` — 메타데이터 대시보드 + 목록

**문제**: 두 페이지의 역할 경계 모호. mock 데이터를 보면 같은 콘텐츠가 양쪽에 나옴. `metadata` 는 "AI 처리 상태에 집중" 한 차별점이 명확하지 않음.

### 2.3 검수/검토 (6개 분산)
- `/metadata/staging` — staging 상태 (외부 매칭 후 검토)
- `/metadata/queue` — review 상태 (70~89점)
- `/metadata/text/review` — 글자메타 검수
- `/metadata/video/qc` — 영상 QC
- `/metadata/image/upload` — 이미지 업로드
- (콘텐츠 상세에서도 검수 가능)

**문제**:
1. staging vs queue 의 의미 구분 모호 (둘 다 "검수 대기")
2. 한 콘텐츠의 글자/이미지/영상 메타가 **각각 다른 화면**에 있음 — 운영자가 한 콘텐츠 검수하려면 페이지 3개 이동
3. ContentStatus 흐름 (waiting→processing→staging→review→approved/rejected) 이 UI 에 일관적으로 매핑되지 않음

### 2.4 메타 유형별 관리 (3 × 2 = 6개)
- text: 목록(`/text`) + 검수(`/text/review`)
- image: 목록(`/image`) + 업로드(`/image/upload`)
- video: 목록(`/video`) + QC(`/video/qc`)

**문제**: 메타 유형별로 "목록 + 액션화면" 패턴이 반복됨. 콘텐츠 단위로 보면 한 콘텐츠의 3종 메타가 항상 함께 다뤄지는데, UI 는 메타 유형 단위로 잘려있음.

### 2.5 모니터링 (분리)
- `/monitoring/pipeline` — 다른 네비게이션 영역에 위치
- 콘텐츠 흐름의 일부인데도 `metadata/` 와 떨어져 있음

**문제**: 운영자는 "방금 업로드한 배치의 처리 현황" 을 보고 싶을 때 `/metadata/upload` → `/monitoring/pipeline` 으로 이동 필요. 컨텍스트 단절.

## 3. 중복/누락 요약

| 영역 | 현재 페이지 수 | 권장 페이지 수 | 비고 |
|------|------------|-------------|------|
| 콘텐츠 입력 | 2 (create, upload) + 외부검색 없음 | 1 통합 진입점 (모달 3탭) | 외부검색 추가 |
| 콘텐츠 목록 | 2 (contents, metadata) | 1 (contents — status 필터) | metadata 대시보드 흡수 |
| 콘텐츠 상세/검수 | 6 (staging, queue, text/review, video/qc, image/upload + contents/[id]) | 1 (contents/[id] — 메타 탭 5개) | 메타 탭 통합 |
| 메타 유형별 목록 | 3 (text, image, video) | 0 (콘텐츠 목록의 필터로 흡수) | 또는 부속 보고서 1개 |
| 모니터링 | 1 (monitoring/pipeline) | 1 (contents 영역으로 이동) | 위치만 변경 |
| 외부소스 캐시 | 4 (sources + 3 하위) | 4 (현재 유지) | 변경 불필요 |

**총합**: 16개 페이지 → **8개** (50% 감소)

## 4. 다음 step

→ `02_menu_lifecycle.md`: 위 통합안 기반 신규 메뉴 구조 + 콘텐츠 라이프사이클 상태 전이 다이어그램 작성.
