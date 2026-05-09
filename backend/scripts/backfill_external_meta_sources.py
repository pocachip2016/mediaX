"""
백필: ContentMetadata.kobis_movie_cd / tmdb_id → ExternalMetaSource

기존 레거시 컬럼에 값이 있으나 ExternalMetaSource 행이 없는 레코드를 찾아
ExternalMetaSource 행을 생성한다.

사용법:
  python3 scripts/backfill_external_meta_sources.py          # 실제 실행
  python3 scripts/backfill_external_meta_sources.py --dry-run  # 대상 통계만 출력
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from sqlalchemy.orm import Session

from shared.database import SessionLocal
from api.programming.metadata.models import (
    Content, ContentMetadata,
    ExternalMetaSource, ExternalSourceType,
)


def backfill(db: Session, dry_run: bool = False):
    rows = (
        db.query(ContentMetadata)
        .filter(
            (ContentMetadata.kobis_movie_cd.isnot(None)) |
            (ContentMetadata.tmdb_id.isnot(None))
        )
        .all()
    )

    kobis_created = kobis_skipped = tmdb_created = tmdb_skipped = 0

    for meta in rows:
        if meta.kobis_movie_cd:
            exists = db.query(ExternalMetaSource).filter(
                ExternalMetaSource.content_id == meta.content_id,
                ExternalMetaSource.source_type == ExternalSourceType.kobis,
            ).first()
            if exists:
                kobis_skipped += 1
            else:
                kobis_created += 1
                if not dry_run:
                    db.add(ExternalMetaSource(
                        content_id=meta.content_id,
                        source_type=ExternalSourceType.kobis,
                        external_id=meta.kobis_movie_cd,
                        raw_json=meta.kobis_data or {},
                        matched_at=meta.created_at or datetime.utcnow(),
                    ))

        if meta.tmdb_id:
            exists = db.query(ExternalMetaSource).filter(
                ExternalMetaSource.content_id == meta.content_id,
                ExternalMetaSource.source_type == ExternalSourceType.tmdb,
            ).first()
            if exists:
                tmdb_skipped += 1
            else:
                tmdb_created += 1
                if not dry_run:
                    db.add(ExternalMetaSource(
                        content_id=meta.content_id,
                        source_type=ExternalSourceType.tmdb,
                        external_id=str(meta.tmdb_id),
                        raw_json=meta.tmdb_data or {},
                        matched_at=meta.created_at or datetime.utcnow(),
                    ))

    if not dry_run:
        db.commit()

    prefix = "[DRY-RUN] " if dry_run else ""
    print(f"{prefix}KOBIS: {kobis_created} created, {kobis_skipped} already exist")
    print(f"{prefix}TMDB:  {tmdb_created} created, {tmdb_skipped} already exist")
    print(f"{prefix}Total new rows: {kobis_created + tmdb_created}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        backfill(db, dry_run=args.dry_run)
    finally:
        db.close()
