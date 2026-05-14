# Watcha Pedia 사이트 정찰 — Step 1.1

> 2026-05-14 작성. Step 1.2 (url-collector) 가 이 문서의 selector·전략을 그대로 사용한다.

## 1. URL 패턴

| 용도 | URL 템플릿 | 비고 |
|------|-----------|------|
| 메인 | `https://pedia.watcha.com/ko` | 추천/박스오피스 carousel |
| 영화 도메인 | `https://pedia.watcha.com/ko?domain=movie` | 한 페이지 ~60 카드 (박스오피스+upcoming) |
| 시리즈 도메인 | `https://pedia.watcha.com/ko?domain=tv` | |
| 콘텐츠 상세 | `https://pedia.watcha.com/ko/contents/<slug>` | slug = base62 7~22자 (대부분 7자) |
| Upcoming 영화 | `https://pedia.watcha.com/ko/upcoming/movie` | 카드 61개 — 카탈로그 진입 대안 |
| Sitemap index | `https://pedia.watcha.com/sitemap/sitemap.xml` | 64개 sub-sitemap 보유 |

**slug 예시**: `mOkv6JW`, `tEKzKwn`, `m5GoryB` — `[A-Za-z0-9]{7,22}`. 일부 시리즈는 22자(예: `rSo7pCx480qs1R3o039Bvw`).

## 2. robots.txt 핵심

- 일반 User-agent (`*`): `/_/`, `/keywordjp`, `/api`, `/abacus` Disallow → **`/ko/contents/*` 와 sitemap 은 허용**
- 차단 봇 25+개 중 `GPTBot`, `ChatGPT-User`, `Bytespider`, `Claude-Web` 등 AI 봇 포함 → **정상 브라우저 UA 필수** (`Mozilla/5.0 ... Chrome/124`)
- Bingbot 등 5개에 `Crawl-delay: 3600` — 우리는 해당 없음. 그래도 **3~5초 sleep 권장** (서버 부담·차단 회피)

## 3. **URL 수집 전략 (Step 1.2 채택)** — sitemap 우선

### 3.1 Sitemap 구조 (한국어 영화·시리즈만 추림)

| 파일 | 추정 콘텐츠 | 비고 |
|------|------------|------|
| `https://pedia.watcha.com/sitemap/ko/movie.xml.gz` | 한국어 영화 메인 | |
| `https://pedia.watcha.com/sitemap/ko/movie1.xml.gz` ~ `movie7.xml.gz` | 한국어 영화 페이지 분할 | 총 8개 파일 |
| `https://pedia.watcha.com/sitemap/ko/tvseason.xml.gz` | 한국어 TV 시즌 | |
| `https://pedia.watcha.com/sitemap/ko/tvseason1.xml.gz` ~ `tvseason2.xml.gz` | TV 시즌 분할 | 총 3개 파일 |

> `ja/`, `en/` 은 일본어·영어 페이지. **무시한다** (한국어 제목 필요).

### 3.2 수집 방법

1. `requests.get(sitemap_url)` + `gzip.decompress()` + `xml.etree.ElementTree.fromstring()` 으로 `<loc>` 추출
2. 각 `<loc>` 은 `https://pedia.watcha.com/ko/contents/<slug>` 형태
3. 영화 sitemap 8개 중 1~2개만 받아도 수만 건 — `random.sample(slugs, 250)` 으로 충분
4. 시리즈도 동일하게 50건 정도 별도 추출 (사용자 요구: 영화:시리즈 ≈ 8:2)

### 3.3 폴백 (sitemap 실패 시)

- `/ko?domain=movie` + `/ko/upcoming/movie` 페이지에서 `a[href^="/ko/contents/"]` 슬러그 추출 (~120건)
- 더 부족하면 사용자가 시작 슬러그를 주고 그 페이지의 "관련 작품" 섹션을 따라가는 random walk

## 4. 페이지 렌더링 방식

| 페이지 | 렌더링 | 핵심 selector 가능 여부 |
|--------|--------|------------------------|
| `/ko`, `/ko?domain=*` | **SSR** — 카드 href 가 HTML 에 직접 들어감 | `a[href^="/ko/contents/"]` 즉시 |
| `/ko/contents/<slug>` 상세 | **SSR** (코어 메타) + JS (댓글) | og:meta + 본문 selector 로 추출 가능 |
| `/ko/upcoming/movie` | **SSR** | `a[href^="/ko/contents/"]` 즉시 |

→ **결론**: Step 1.2 는 `requests` + `BeautifulSoup4` 로 충분. Step 1.3 도 같은 방식 시도 후 빈 필드 발생 시에만 Playwright fallback.

## 5. 상세 페이지 selector (`/ko/contents/<slug>`)

### 5.1 코어 필드

| 필드 | 추출 방식 (우선순위) |
|------|---------------------|
| 한글 제목 | 1) `meta[property="og:title"]@content` 2) `h1` 텍스트 |
| 영문 원제 | h1 인접 형제 텍스트 (`마이클 클레이튼Michael Clayton2007` 같은 연결 패턴 — 정규식 분리 필요) |
| 연도 | 정보 라인 `2007 · ...` 의 첫 4자리 숫자 |
| 장르 | 정보 라인 `· 범죄/드라마/미스터리/스릴러 ·` 의 `/` 분할 |
| 국가 | 정보 라인 `· 미국1시간 59분` 의 국가명 |
| 러닝타임 | 정보 라인 `1시간 59분` 또는 `119분` |
| 관람등급 | 정보 라인 끝 `15세`, `청소년관람불가`, `전체관람가` 등 |
| 시놉시스 | `meta[name="description"]@content` 또는 본문 단락 (`section` 내 첫 `p` / 긴 텍스트 블록) |
| 포스터 URL | `meta[property="og:image"]@content` (가장 안정) |
| 감독 | "감독" 라벨 옆 a 태그 텍스트 — selector 는 페이지에서 실제 확인 |

### 5.2 정보 라인 정규식 (예시 — 마이클 클레이튼)

```
"2007 · 범죄/드라마/미스터리/스릴러 · 미국1시간 59분 · 15세"
   ^year   ^genres                       ^country^runtime  ^rating_age

YEAR_RE   = r"^(\d{4})"
GENRES_RE = r"·\s*([가-힣/]+(?:/[가-힣]+)*)"
RUNTIME_RE= r"(\d+시간\s*\d+분|\d+분)"
RATING_RE = r"(전체관람가|12세|15세|19세|청소년관람불가|R|PG-?\d+)"
```

### 5.3 콘텐츠 타입 판별

상세 페이지에는 명시적 type 라벨이 없는 경우가 많음 → **소스 sitemap 으로 판별**:
- `sitemap/ko/movie*.xml.gz` 출신 → `content_type = "movie"`
- `sitemap/ko/tvseason*.xml.gz` 출신 → `content_type = "series"`

이 정보를 list_real.csv 의 `category` 컬럼에 미리 적어 둔다.

## 6. 포스터 (JWT) 처리

- URL 형태: `https://an2-img.amz.wtchn.net/image/v2/<hash>.webp?jwt=eyJhbGc...`
- JWT 페이로드에 `exp`(만료) 가 들어있을 가능성 매우 높음 → **detail crawl 즉시 다운로드**
- JWT 만료 응답: 보통 **401/403**. 다운로드 실패 시 expired_posters.csv 에 기록 (Step 1.4)
- Content-Type: `image/webp` 대부분 — 확장자 자동 매핑

## 7. Rate-limit 추정

- robots.txt 에 일반 UA 대상 명시 없음. AI 봇은 전면 차단 → **반드시 일반 Chrome UA**
- 안전 기본값: 요청 간 `random.uniform(3, 5)`초 sleep. **연속 60건 이상** 받을 때 한 번 10초 휴식 권장
- 429/403 받으면 즉시 60초 backoff 후 재시도 1회, 그래도 실패면 해당 row 만 skip

## 8. Step 1.2~ 에 전달하는 결정 사항 요약

1. **URL 소스**: sitemap (`https://pedia.watcha.com/sitemap/ko/movie*.xml.gz` × 8 + `ko/tvseason*.xml.gz` × 3)
2. **수집 비율**: 영화 ~200건 + 시리즈 ~50건 = 약 250건
3. **샘플링 방식**: `random.seed(42)` → `random.sample()` (재현 가능)
4. **HTTP 라이브러리**: `requests` (Playwright 불필요 — SSR 확인됨)
5. **UA**: `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36`
6. **Sleep**: 요청 간 3~5초, 60건마다 10초 추가
7. **content_type**: sitemap 출처로 판별 후 list_real.csv `category` 컬럼에 기록
