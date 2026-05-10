# Step C.10: wrap

> GitHub: 미생성 | Milestone: dev-meta-intelligence-phase-c

## 읽어야 할 파일
- C.0~C.9 모든 step summary (index.json)
- `TODO.md`
- `CHANGELOG.md` (있으면)
- `docs/dev/meta-intelligence-phase-c.md`

## 작업

### 1. TODO.md 갱신
- `## Now` 비우기
- `## Done` 에 추가:
  ```
  - [x] dev-meta-intelligence-phase-c — SEED 발굴 파이프라인 (TMDB/KOBIS/KMDB/OMDb), 검수 백엔드, Beat 스케줄 (날짜)
  ```
- `## Next` 에서 Phase C 항목 제거 → Phase D (WebSearch) 추가

### 2. CHANGELOG.md 갱신 (있을 때)
phase 단위 1행 추가:
```
## YYYY-MM-DD
- feat(meta-intelligence): Phase C — SEED 발굴 파이프라인 + 검수 백엔드
```

### 3. CLAUDE.md 동기화
`backend/api/meta_core/CLAUDE.md` 에 Phase C 모듈 인덱스 추가:
- `discovery/` (TmdbDiscoverySource, KobisDiscoverySource, KmdbDiscoverySource, runner, dedup, promote)
- `clients/omdb_client.py`
- `intelligence/seed_schemas.py`

### 4. 머지
- 브랜치(`feature/meta-intelligence-phase-c`) → main, `--no-ff`
- 머지 후 브랜치 삭제

### 5. 다음 phase 메모
`docs/dev/meta-intelligence-phase-c.md` 마지막에 §7 추가:
- "Phase D 가 시작될 때 알아야 할 것" — WebSearchCache 통합 지점, Wikidata 보강 후보,
  사용자 직접 입력(URL paste) 시드 경로

### 6. 검증
- 신규 코드 변경 0줄 (문서/체크박스만)
- /verify --skip "C.10 wrap — docs only"

## Acceptance Criteria
```bash
bash .claude/verify.sh --skip "C.10 wrap docs only"
```

- TODO.md 의 `## Now` 비어있음
- TODO.md 의 `## Done` 에 phase-c 1줄 추가
- main 에 phase-c 머지 commit 존재
- feature/meta-intelligence-phase-c 브랜치 삭제됨

## 금지사항
- 코드/마이그레이션 변경 금지 — wrap 단계
- 미완 step 이 있는 채로 wrap 금지 — index.json 모두 completed 인 것 확인 후 진입
- 머지 commit 메시지에 step 별 상세 요약 누락 금지 — 한 번에 보기 좋게
