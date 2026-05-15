#!/usr/bin/env python3
"""
00_cleanup_baseline: 더미 + 기존 Watcha 콘텐츠 삭제 → 재업로드 baseline 확보

삭제 대상:
  1. contents.title LIKE '콘텐츠_%' (더미)
  2. contents.cp_name = 'Watcha'

ContentMetadata 는 cascade 미설정 → bulk delete 선행.
나머지 하위 테이블(genres/tags/credits/images/external_sources/ai_results)은
Content.cascade="all, delete-orphan" 으로 자동 삭제.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sqlalchemy import delete
from api.programming.metadata.models.content import Content, ContentMetadata
from shared.database import SessionLocal


def main():
    db = SessionLocal()
    try:
        ids = [
            r.id
            for r in db.query(Content.id)
            .filter((Content.title.like("콘텐츠_%")) | (Content.cp_name == "Watcha"))
            .all()
        ]
        print(f"삭제 대상: {len(ids)}건")

        if not ids:
            print("삭제할 데이터 없음 — 이미 정리 완료")
            return

        meta_del = db.execute(
            delete(ContentMetadata).where(ContentMetadata.content_id.in_(ids))
        )
        print(f"  ContentMetadata 삭제: {meta_del.rowcount}건")

        # cascade="all, delete-orphan" 으로 하위 테이블 자동 삭제
        for c in db.query(Content).filter(Content.id.in_(ids)).all():
            db.delete(c)

        db.commit()

        watcha_left = db.query(Content).filter(Content.cp_name == "Watcha").count()
        dummy_left = db.query(Content).filter(Content.title.like("콘텐츠_%")).count()
        print(f"삭제 완료 — 남은 Watcha: {watcha_left}건, 더미: {dummy_left}건")

    except Exception as e:
        db.rollback()
        print(f"오류 발생, rollback: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
