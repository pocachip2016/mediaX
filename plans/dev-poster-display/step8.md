# Step 8 — e2e-visual-verify

## 검증 결과 (2026-05-14)

### API 검증

| 항목 | 결과 |
|------|------|
| `GET /api/programming/metadata/contents?cp_name=Watcha&size=100` — `poster_url` non-null | 100/100 (100%) |
| `GET /static/posters/tEQkv41.jpg` | HTTP 200 OK, image/jpeg, 81343 bytes |
| `GET /api/programming/metadata/image/3356` | `has_poster: true`, 1 image (source=cp) |

### DB 상태

| 항목 | 값 |
|------|-----|
| ContentImage (source=cp, type=poster) | 237건 |
| ContentImage (source=tmdb, type=poster) | 미측정 |

### 백엔드 DB 타입

SQLite (media_ax_dev.db) — Docker volume 공유

### typecheck

`npm run typecheck` — 통과 (2 tasks successful)

### 확인된 데이터 흐름

1. `detail_real.csv` (237행) → `05_link_posters.py` → ContentImage (source=cp, url=/static/posters/{slug}.jpg)
2. `GET /api/programming/metadata/contents?cp_name=Watcha` → `poster_url: "/static/posters/{slug}.jpg"` 반환
3. `GET /static/posters/{slug}.jpg` → 200 OK (StaticFiles 마운트)
4. 프론트 리스트 페이지: `resolvePosterUrl` → `http://localhost:8000/static/posters/{slug}.jpg`
5. 프론트 상세 페이지 Image 탭: `imageMetaApi.get(id)` → 이미지 카드 렌더

### 비고

- Docker 컨테이너에서 backfill 재실행 필요 (최초 실행은 asc 정렬 → 최신 row와 mismatch). desc 정렬로 수정 후 재실행 완료.
- 스크린샷: Docker UI 환경 미구성으로 CLI 검증으로 대체.
