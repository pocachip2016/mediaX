"""콘텐츠당 manual ExternalMetaSource를 1개로 정리.
raw_json은 matched_at ASC 순서로 머지(최신이 동일 키 덮어씀)하여 가장 최신 source에 저장.
"""
from sqlalchemy import func
from shared.database import SessionLocal
from api.programming.metadata.models.external import ExternalMetaSource, ExternalSourceType


def main() -> None:
    db = SessionLocal()
    try:
        dup_content_ids = [
            cid for (cid,) in db.query(ExternalMetaSource.content_id)
            .filter(ExternalMetaSource.source_type == ExternalSourceType.manual)
            .group_by(ExternalMetaSource.content_id)
            .having(func.count(ExternalMetaSource.id) > 1)
            .all()
        ]

        if not dup_content_ids:
            print("No duplicate manual sources found.")
            return

        total_deleted = 0
        for cid in dup_content_ids:
            sources = (
                db.query(ExternalMetaSource)
                .filter(
                    ExternalMetaSource.content_id == cid,
                    ExternalMetaSource.source_type == ExternalSourceType.manual,
                )
                .order_by(
                    ExternalMetaSource.matched_at.asc().nullsfirst(),
                    ExternalMetaSource.id.asc(),
                )
                .all()
            )

            merged: dict = {}
            for s in sources:
                if s.raw_json:
                    merged.update(s.raw_json)

            latest = sources[-1]
            latest.raw_json = merged

            for s in sources[:-1]:
                db.delete(s)
            total_deleted += len(sources) - 1

            print(f"content {cid}: kept source {latest.id}, deleted {len(sources)-1} (merged keys: {sorted(merged.keys())})")

        db.commit()
        print(f"\nDone: cleaned {len(dup_content_ids)} contents, deleted {total_deleted} duplicate manual sources.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
