# Step 1 — kmdb-live-search

## 검증 결과: PASS

- API 키: `ID24...` (설정 확인)
- `search_movie('기생충')` → 5건 반환, `DOCID=A07654`

## 발견된 결함 (follow-up)

**버그**: `kmdb_client.py:search_movie(title, year)` 에서 `releaseDts = str(year)` ("2019") 로 전달하는데, KMDB API 는 `YYYYMMDD` 형식 (`"20190101"`) 을 요구함.
- year 파라미터를 넘기면 항상 빈 결과 반환 (`Data[0].Result = []`)
- 예: `search_movie('기생충', 2019)` → `[]`
- 예: `releaseDts='20190101', releaseDte='20191231'` → 4건 반환 (정상)

follow-up: `search_movie` 의 year 파라미터를 `f"{year}0101"` / `f"{year}1231"` 로 수정

## 기타 관찰

- Redis 연결 불가 (로컬 개발 환경) → QuotaManager fail-open 처리 → quota check 패스
- API 서버 응답 정상, 인증 통과
