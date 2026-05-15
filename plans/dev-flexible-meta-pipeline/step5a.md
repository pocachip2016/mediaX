# Step 5a: cleanup-baseline

## 목적
재업로드 전 clean baseline 확보. 더미 콘텐츠 + 기존 Watcha 콘텐츠 전체 삭제.

## 선행 조건
- Steps 1~4 completed.
- `backend/media_ax_dev.db` 존재.

## 삭제 대상
1. `contents.title LIKE '콘텐츠_%'` — 더미 (약 2,130건)
2. `contents.cp_name = 'Watcha'` — 기존 Watcha 콘텐츠

## 구현
`backend/scripts/watcha_real/00_cleanup_baseline.py`:
- SQLAlchemy SessionLocal 통한 삭제.
- ContentMetadata 먼저 bulk delete (cascade 미설정).
- Content.cascade="all, delete-orphan" → 하위 테이블 자동 삭제.
- 멱등성: 이미 없으면 "정리 완료" 메시지 후 종료.

## 검증
```bash
cd /home/ktalpha/Work/mediaX
bash .claude/verify.sh flexible-meta-step5a
```

## 주의
- DROP/TRUNCATE 사용 금지 — 다른 소스(TMDB/KOBIS) 데이터 보존 필요.
- 트랜잭션 단일 commit.
