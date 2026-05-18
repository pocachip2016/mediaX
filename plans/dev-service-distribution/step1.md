# Step 1: service-bulk-import

> Milestone: dev-service-distribution | 실데이터: `영화_성인19+2026.csv` (7,993건, CP949)

## 목표
한국어 헤더 + SMPTE 런타임 + CP949 인코딩 CSV를 기존 `POST /api/programming/metadata/upload/batch`
엔드포인트로 import 가능하게 파서·별칭 확장. 신규 엔드포인트 불필요.

## 데이터 분석 (실측)
| CSV 컬럼 | 값 분포 | → 매핑 | 처리 |
|---------|--------|-------|------|
| 콘텐츠명 | 7,993 unique | `title` | 별칭 추가 |
| 시청등급 | 19세이상 2904 / 성인전용 3519 / 15세이상 22 / 빈값 1548 | `rating_age` → raw_json | 별칭 기존 ✓ (컬럼 아님) |
| 화질 | HD 7986 / FHD 4 / SD 2 / APP 1 | `video_resolution` | 별칭+와이어링 |
| 5.1CH | "2" 7992 / 빈값 1 | `audio_channels` | "1"→5.1CH, "2"→Stereo |
| CP명 | 다수 | `cp_name` | 별칭 추가 |
| 상용시간(RT) | "01:09:52:04" (HH:MM:SS:FF) | `runtime`(분) | SMPTE 파서 |
| 개봉일 | "2026-03-23" / 빈값 | `production_year` | YYYY 추출 |
| 제작국가 | 일본 등 | `country` | 별칭 기존 ✓ |
| 영상유형 | 본편 7964 / 부속 24 / 소장 4 | `content_type`=movie + extra_metadata | 원본 보존 |

## 정규화 결정 (사용자 합의)
- 저카디널리티 고정값은 ENUM이 정석이나, `rating_age`는 **컬럼이 아니라 raw_json 저장** 구조 → ENUM 전환 대상 아님
- `audio_channels`는 실컬럼이나 값이 단조(전부 Stereo) → 이번엔 String 유지
- `cp_name`/`country` 정규화는 별도 task(1.5 CP수급 / link backfill 선례)로 분리
- **결론: 문자열 import + 나중 링크. Step 1은 파서 확장만.**

## Sub-steps

### Step 1.1 — 파서 + 컬럼 별칭 확장 (backend)
**파일:** `router.py`, `service.py`
- `_extract_row` 별칭 확장:
  - title: `+ "콘텐츠명"`
  - cp_name: `+ "CP명"`
  - runtime: `+ "상용시간(RT)"` → SMPTE 파서 경유
  - audio_channels: `+ "5.1CH"` → 값 매핑 경유
  - content_type: `+ "영상유형"`
  - production_year: 개봉일에서 YYYY 추출
  - video_resolution: 신규 키 (화질)
- 신규 헬퍼 (router.py):
  - `_parse_smpte_runtime("01:09:52:04")` → 70 (분, 초→분 반올림, FF 무시)
  - `_parse_year("2026-03-23")` → 2026
  - `_map_audio_channels("2")` → "Stereo" / "1" → "5.1CH" / else passthrough
- `_normalize_content_type` 확장: "본편"→movie, "부속"/"소장"→movie
- `process_batch_rows` (service.py): `video_resolution` ContentMetadata 와이어링,
  영상유형 원본을 `extra_metadata`에 병합 보존
- pytest: 파서 3종 단위 테스트 + 한국어 컬럼 _extract_row 매핑 테스트

**검증 기준:** `verify.sh service-bulk-import-parsers` — pytest pass + 파서 경계값

### Step 1.2 — 실데이터 import + E2E 검증
- CSV를 컨테이너 복사 → 샘플 100건 우선 import → 전량 7,993건
- dedup·success/skipped/failed 카운트 확인
- DB 샘플 검증: audio_channels="Stereo", country="일본", runtime≈70, video_resolution="HD",
  extra_metadata에 영상유형 보존
- **검증 기준:** `verify.sh service-bulk-import` — import 카운트 + DB 샘플 무결성

## 범위 밖 (별도 task)
- cp_name → CpCompany 마스터 정규화 (1.5 CP수급)
- rating_age 값 표준화 ("19세이상" → "19세이상관람가")
- ContentDistribution 채널 연결 (이 CSV엔 채널 정보 없음)
