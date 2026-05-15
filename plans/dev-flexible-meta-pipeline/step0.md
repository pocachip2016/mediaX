# Step 0: 더미 데이터 정리

## 배경
Watcha 크롤 과정에서 생성된 "콘텐츠_XXXXX" 형식의 더미 테스트 데이터 2,130건이 현재 DB에 혼재. 메타 파이프라인 개선과 데이터 정규화를 위해 먼저 정리 필요.

## 목표
- `contents` 테이블에서 title이 "콘텐츠_"로 시작하는 2,130개 행 삭제
- 관계된 `content_metadata`, `content_genres`, `content_tags`, `content_credits`, `content_images`, `external_meta_sources`, `content_ai_results` 행도 함께 정리
- 정리 후 데이터 검증: 남은 콘텐츠 목록 확인

## 구현
### 1. 정리 전 백업 (선택)
```bash
sqlite3 backend/media_ax_dev.db ".mode csv" "SELECT * FROM contents WHERE title LIKE 'contents_%'" > /tmp/contents_backup.csv
```

### 2. 메인 삭제 쿼리
```sql
-- 더미 content_id 목록
WITH dummy_ids AS (
  SELECT id FROM contents WHERE title LIKE 'contents_%'
)
-- Cascade 또는 개별 삭제
DELETE FROM content_metadata WHERE content_id IN (SELECT id FROM dummy_ids);
DELETE FROM content_genres WHERE content_id IN (SELECT id FROM dummy_ids);
DELETE FROM content_tags WHERE content_id IN (SELECT id FROM dummy_ids);
DELETE FROM content_credits WHERE content_id IN (SELECT id FROM dummy_ids);
DELETE FROM content_images WHERE content_id IN (SELECT id FROM dummy_ids);
DELETE FROM external_meta_sources WHERE content_id IN (SELECT id FROM dummy_ids);
DELETE FROM content_ai_results WHERE content_id IN (SELECT id FROM dummy_ids);
DELETE FROM contents WHERE title LIKE 'contents_%';
```

### 3. 삭제 후 검증
```sql
SELECT COUNT(*) FROM contents;  -- 3592 - 2130 = 1462
SELECT COUNT(*) FROM contents WHERE title LIKE 'contents_%';  -- 0
```

## 검증 방법
- 실행 후: `SELECT COUNT(*) FROM contents WHERE content_type = 'watcha'` → 1,158 남아야 함
- 기존 콘텐츠(IPTV, 시험용)는 영향 없어야 함 → 조회: `SELECT COUNT(*), content_type FROM contents GROUP BY content_type`

## 영향 범위
- DB 크기 감소 (~2,130 * 20KB = ~42.6MB)
- 후속 Step 1~6의 기준선 확보
- 기존 real Watcha, TMDB, KOBIS, IPTV 데이터는 유지

## 주의
- SQLite 환경에서 테스트. PostgreSQL은 cascade 정책 재확인 필요.
- 삭제 전 `sqlite3 backend/media_ax_dev.db ".dump"` → 임시 SQL 백업 권장.
