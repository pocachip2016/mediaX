# Step 8 — External Curation Backfill (BE)

> branch: `feature/curation-workbench`
> 재배치: 기존 step8(fe-wizard34)→9. 본 step은 사용자 아키텍처 피드백(2026-05-28)으로 신설.

## 배경 — 사용자 피드백

> "외부 메타 DB backfill처럼 큐레이션도 trend/seasonal/ott 동향 외부 데이터를 근거로 DB backfill을 하고, 내부 콘텐츠DB 항목 내에서 그룹화하고 큐레이션을 다시 DB화 해야 한다. 목록 저장은 콘텐츠 DB key값만 가지는 구조이므로 외부 큐레이션 모집할 때부터 content key를 고려해야 한다."

## 조사 결과 — 이미 존재하는 인프라 (재사용)

| 자산 | 위치 | 재사용 방식 |
|------|------|-------------|
| 외부 OTT 섹션 수집 | `api/distribution/ott/base.py::OttSource.fetch_sections()` | 그대로 호출 |
| title+year → content_id resolve | `api/distribution/ott/matcher.py::match_content` | 그대로 호출 |
| 외부→내부 upsert 패턴 | `api/distribution/ott/runner.py`, `writer.py` | 패턴 차용 |
| sync 감사 로그 | `external_sync_log` (alembic 0006/0021) | run 기록 재사용 |
| content_id key 저장 | `ServiceCategoryItem(content_id FK, rank, score)` | 변경 없음 — 이미 충족 |

## 갭

외부 큐레이션 **섹션 그룹화**가 영속화되지 않음:
- OTT popularity sync → content_id resolve O, 섹션 그룹 버림
- 큐레이션 external-references → 섹션 그룹 O, content_id resolve X (live·title만)

## 결정

### 1. 신규 테이블 (alembic 0026)

```python
class ExternalCuration(Base):
    __tablename__ = "external_curations"
    id, channel, section_id, section_name,          # section_name = 카피 후보
    category_type,                                   # ranking|genre|recommendation|mood
    trend_type = Column(String(20), default="ott"), # ott | trend | seasonal
    season_tag = Column(String(50), nullable=True), # nullable
    collected_at, matched_count, total_count
    # UNIQUE(channel, section_id) — 최신 스냅샷 upsert (일별 누적 아님, 단순화)

class ExternalCurationItem(Base):
    __tablename__ = "external_curation_items"
    id, external_curation_id FK,
    content_id = Column(ForeignKey("contents.id"), nullable=True),  # resolve 결과
    external_title, external_rank, production_year
    # UNIQUE(external_curation_id, external_rank)
```

> 일별 스냅샷 누적 대신 `(channel, section_id)` UNIQUE upsert로 단순화 (popularity sync와 동일 철학). 추후 이력 필요 시 collected_at 기반 스냅샷으로 확장.

### 2. Beat task `backfill_external_curations`

`workers/tasks/distribution.py`에 추가. 각 OttSource:
1. `fetch_sections()` → 섹션 목록
2. 섹션별 item마다 `match_content(db, item)` → content_id (미매칭 NULL)
3. `external_curations` upsert + `external_curation_items` 재구성
4. `external_sync_log`에 run 기록 (source=`curation_<channel>`)

Beat 스케줄: 매일 1회 (기존 OTT popularity sync와 동일 시간대 근처).

### 3. 엔드포인트 재배선

- `GET /curations/external-references` → **영속 테이블 읽기**. `OttSectionCardOut`에 `items[].content_id`(nullable) + `matched_count` 추가. 테이블 비었으면 live `fetch_sections()` 폴백.
- `POST /curations/match-contents` → `external_content_ids: list[int]` 필드 추가. `curation_matcher._external_score`를 content_id 정확 매칭으로 확장(기존 external_titles는 호환 유지).

### 4. 저장 경로 (Step 9·10에서 사용, 본 step은 스키마만)

- 외부 import: resolve된 content_id를 ServiceCategoryItem으로 복사 → live crawl 불필요.

## 산출물

| 항목 | 파일 |
|------|------|
| 모델 2개 | `api/distribution/models.py` |
| alembic | `alembic/versions/0026_external_curation_tables.py` |
| Beat task | `workers/tasks/distribution.py` |
| backfill 로직 | `api/distribution/ott/curation_runner.py` (신규) |
| 엔드포인트 재배선 | `api/distribution/router.py` |
| 스키마 확장 | `api/distribution/schemas.py` (OttItemOut.content_id, MatchContentsRequest.external_content_ids) |
| matcher 확장 | `api/distribution/curation_matcher.py` |
| pytest | `tests/distribution/test_curation_backfill.py` |

## 검증 (verify.sh: dev-curation-workbench-step8)

1. alembic upgrade head → external_curations/items 테이블 존재
2. pytest — backfill resolve(매칭/미매칭), external-references 영속 읽기, match-contents external_content_ids 보너스
3. Beat 등록 확인 (`backfill_external_curations` in beat_schedule)

## 영향 / 리스크

- **백워드 호환**: external-references 응답에 필드 추가만(FE Step 7은 content_id 무시 → 무영향). match-contents external_titles 유지.
- **resolve 비용**: match_content가 전체 Content 스캔(O(N)). 섹션 item 수 작아 허용. 추후 normalize_title 인덱스 캐시 고려.
- **미매칭 item**: content_id=NULL 보존 → 신규 콘텐츠 등록 후 재backfill 시 자동 링크.
