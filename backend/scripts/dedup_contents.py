"""Bulk upload로 생성된 중복 Content 정리 스크립트.

(title, production_year, cp_name) 그룹별로:
  - canonical = 가장 빠른 id (외부 소스 가장 많은 row 우선)
  - 자식 row(ExternalMetaSource·ContentMetadata·ContentCredit·ContentImage·
    ContentGenre·ContentTag·ContentAIResult)의 content_id를 canonical로 이전
  - 충돌(unique constraint 위반 가능)하는 자식 row는 skip
  - 중복 Content 삭제

기본 --dry-run 모드. --apply로 실제 실행.

사용 예:
    python scripts/dedup_contents.py --dry-run
    python scripts/dedup_contents.py --apply --min-group-size 2
"""
import argparse
import sys
from collections import defaultdict
from pathlib import Path

# backend/ 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.database import SessionLocal
from api.programming.metadata.models.content import Content, ContentMetadata
from api.programming.metadata.models.external import ExternalMetaSource, ContentAIResult
from api.programming.metadata.models.taxonomy import ContentGenre, ContentTag
from api.programming.metadata.models.person import ContentCredit
from api.programming.metadata.models.image import ContentImage


CHILD_MODELS = [
    ExternalMetaSource, ContentMetadata, ContentCredit, ContentImage,
    ContentGenre, ContentTag, ContentAIResult,
]


def find_duplicate_groups(db: Session, min_size: int = 2):
    """(title, year, cp_name, content_type) 그룹별 중복 콘텐츠 목록 반환."""
    rows = (
        db.query(
            Content.title, Content.production_year, Content.cp_name,
            Content.content_type,
            func.count(Content.id).label("cnt"),
        )
        .group_by(Content.title, Content.production_year, Content.cp_name, Content.content_type)
        .having(func.count(Content.id) >= min_size)
        .all()
    )
    groups = []
    for title, year, cp, ctype, cnt in rows:
        contents = (
            db.query(Content)
            .filter(
                Content.title == title,
                Content.production_year == year,
                Content.cp_name == cp,
                Content.content_type == ctype,
            )
            .order_by(Content.id)
            .all()
        )
        groups.append({"title": title, "year": year, "cp": cp, "content_type": ctype, "count": cnt, "contents": contents})
    return groups


def pick_canonical(contents: list[Content], db: Session) -> Content:
    """canonical 선정: 외부 소스 가장 많은 row, 동률이면 가장 빠른 id."""
    best = None
    best_score = -1
    for c in contents:
        ext_count = (
            db.query(func.count(ExternalMetaSource.id))
            .filter(ExternalMetaSource.content_id == c.id)
            .scalar()
            or 0
        )
        if ext_count > best_score:
            best = c
            best_score = ext_count
    return best or contents[0]


def reassign_children(db: Session, model, src_id: int, dst_id: int, dry_run: bool) -> tuple[int, int]:
    """model.content_id == src_id → dst_id. (moved, skipped) 반환.

    충돌(unique constraint, e.g. ContentMetadata.content_id 유니크) 시 row 삭제.
    """
    moved = 0
    skipped = 0
    rows = db.query(model).filter(model.content_id == src_id).all()
    for r in rows:
        if dry_run:
            moved += 1
            continue
        try:
            r.content_id = dst_id
            db.flush()
            moved += 1
        except IntegrityError:
            db.rollback()
            db.delete(r)
            db.flush()
            skipped += 1
    return moved, skipped


def reassign_content_children(db: Session, src_id: int, dst_id: int, dry_run: bool) -> int:
    """중복 Content의 계층 자식(Content.parent_id == src_id)을 canonical로 재지정."""
    children = db.query(Content).filter(Content.parent_id == src_id).all()
    if dry_run:
        return len(children)
    for child in children:
        child.parent_id = dst_id
    if children:
        db.flush()
    return len(children)


def dedup_group(db: Session, group: dict, dry_run: bool) -> dict:
    contents = group["contents"]
    canonical = pick_canonical(contents, db)
    duplicates = [c for c in contents if c.id != canonical.id]

    stats = {
        "canonical_id": canonical.id,
        "removed_ids": [c.id for c in duplicates],
        "moved": defaultdict(int),
        "skipped": defaultdict(int),
        "children_reassigned": 0,
    }

    for dup in duplicates:
        stats["children_reassigned"] += reassign_content_children(db, dup.id, canonical.id, dry_run)
        for model in CHILD_MODELS:
            moved, skipped = reassign_children(db, model, dup.id, canonical.id, dry_run)
            stats["moved"][model.__tablename__] += moved
            stats["skipped"][model.__tablename__] += skipped
        if not dry_run:
            db.delete(dup)
            db.flush()
    return stats


def main():
    parser = argparse.ArgumentParser(description="Bulk Content dedup")
    parser.add_argument("--apply", action="store_true", help="실제 실행 (기본은 dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="실행 안 함, 영향만 출력")
    parser.add_argument("--min-group-size", type=int, default=2, help="중복 그룹 최소 크기")
    parser.add_argument("--limit", type=int, default=None, help="상위 N 그룹만 처리")
    args = parser.parse_args()

    dry_run = not args.apply
    mode = "DRY-RUN" if dry_run else "APPLY"
    print(f"=== Content dedup [{mode}] (min_group_size={args.min_group_size}) ===\n")

    db = SessionLocal()
    try:
        groups = find_duplicate_groups(db, min_size=args.min_group_size)
        if args.limit:
            groups = groups[: args.limit]
        print(f"총 중복 그룹: {len(groups)}개\n")

        total_canonical = 0
        total_removed = 0
        total_moved = defaultdict(int)
        total_skipped = defaultdict(int)

        for g in groups:
            stats = dedup_group(db, g, dry_run)
            total_canonical += 1
            total_removed += len(stats["removed_ids"])
            for k, v in stats["moved"].items():
                total_moved[k] += v
            for k, v in stats["skipped"].items():
                total_skipped[k] += v

            if g["count"] >= 5 or args.limit:  # 큰 그룹만 상세 출력
                print(f"  [{g['count']}] {g['title']!r} ({g['year']}/{g['cp']}/{g['content_type']})")
                print(f"      canonical={stats['canonical_id']} removed={stats['removed_ids']}")
                if stats["children_reassigned"]:
                    print(f"      children_reassigned={stats['children_reassigned']}")

        if not dry_run:
            db.commit()
            print("\n=== COMMITTED ===")
        else:
            db.rollback()
            print("\n=== DRY-RUN (no changes saved) ===")

        print(f"\nCanonical: {total_canonical}")
        print(f"Removed contents: {total_removed}")
        print("Moved child rows:")
        for tbl, cnt in total_moved.items():
            print(f"  {tbl}: {cnt}")
        if any(total_skipped.values()):
            print("Skipped (conflict, deleted):")
            for tbl, cnt in total_skipped.items():
                if cnt:
                    print(f"  {tbl}: {cnt}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
