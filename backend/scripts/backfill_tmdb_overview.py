"""
백필: tmdb_movie_cache 행 중 release_date IS NULL 또는 overview 없는 535k 건
     → TMDB detail API(ko-KR 우선, 없으면 en-US 폴백) 로 보강.

사용법:
  cd backend
  python scripts/backfill_tmdb_overview.py              # 전체 실행
  python scripts/backfill_tmdb_overview.py --dry-run    # 대상 건수만 출력
  python scripts/backfill_tmdb_overview.py --limit 100  # 최대 100건만
  python scripts/backfill_tmdb_overview.py --batch 50   # 배치 크기 조정
  python scripts/backfill_tmdb_overview.py --skip-recent-days 3  # 3일 내 fetch 제외

rate limit: Semaphore(20) — TMDB 40 req/s 제한 대비 여유
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import or_, text

from api.programming.metadata.tmdb_client import TmdbClient
from shared.config import settings
from shared.database import SessionLocal
from workers.tasks.tmdb_cache import _upsert_movie

_SEM = asyncio.Semaphore(20)


async def _fetch_and_merge(client: TmdbClient, tmdb_id: int) -> dict | None:
    """ko-KR detail 요청 → overview 없으면 en-US 재요청 → 병합 dict 반환."""
    async with _SEM:
        try:
            detail = await client.detail_movie(tmdb_id, language="ko-KR")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
        if not detail.get("overview"):
            try:
                detail_en = await client.detail_movie(tmdb_id, language="en-US")
                detail["overview"] = detail_en.get("overview") or ""
            except Exception:
                pass
    return detail


async def _run(
    tmdb_ids: list[int],
    api_key: str,
    batch_size: int,
    dry_run: bool,
) -> dict:
    inserted = updated = unchanged = skipped = errors = 0
    total = len(tmdb_ids)
    error_ids: list[int] = []

    db = SessionLocal()
    try:
        async with TmdbClient(api_key=api_key) as client:
            for batch_start in range(0, total, batch_size):
                batch = tmdb_ids[batch_start : batch_start + batch_size]

                tasks = [_fetch_and_merge(client, tid) for tid in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for tmdb_id, result in zip(batch, results):
                    if isinstance(result, BaseException):
                        errors += 1
                        error_ids.append(tmdb_id)
                        print(f"  [ERR] id={tmdb_id}: {result}")
                        continue
                    if result is None:
                        skipped += 1
                        continue
                    if not dry_run:
                        try:
                            action = _upsert_movie(db, result)
                            if action == "inserted":
                                inserted += 1
                            elif action == "updated":
                                updated += 1
                            else:
                                unchanged += 1
                        except Exception as e:
                            errors += 1
                            error_ids.append(tmdb_id)
                            print(f"  [DB ERR] id={tmdb_id}: {e}")

                if not dry_run:
                    db.commit()

                done = min(batch_start + batch_size, total)
                pct = done / total * 100
                print(
                    f"  [{done}/{total} {pct:.1f}%]"
                    f" ins={inserted} upd={updated} unch={unchanged}"
                    f" skip={skipped} err={errors}"
                )
    finally:
        db.close()

    return {
        "total": total,
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "skipped": skipped,
        "errors": errors,
        "error_ids_sample": error_ids[:20],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="TMDB overview/release_date 백필")
    parser.add_argument("--dry-run", action="store_true", help="DB 저장 없이 대상 건수만 확인")
    parser.add_argument("--limit", type=int, default=0, help="최대 처리 건수 (0=무제한)")
    parser.add_argument("--batch", type=int, default=200, help="배치 크기 (default 200)")
    parser.add_argument(
        "--skip-recent-days",
        type=int,
        default=0,
        help="N일 이내 last_fetched_at 인 행 제외 (0=전체 포함)",
    )
    args = parser.parse_args()

    api_key = getattr(settings, "TMDB_API_KEY", "")
    if not api_key:
        print("ERROR: TMDB_API_KEY 미설정")
        sys.exit(1)

    db = SessionLocal()
    try:
        from api.programming.metadata.models.tmdb_cache import TmdbMovieCache

        q = db.query(TmdbMovieCache.id).filter(
            or_(
                TmdbMovieCache.release_date.is_(None),
                TmdbMovieCache.overview.is_(None),
                TmdbMovieCache.overview == "",
            )
        )

        if args.skip_recent_days > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=args.skip_recent_days)
            q = q.filter(
                or_(
                    TmdbMovieCache.last_fetched_at.is_(None),
                    TmdbMovieCache.last_fetched_at < cutoff,
                )
            )

        q = q.order_by(TmdbMovieCache.id)
        rows = q.all()
        tmdb_ids = [r.id for r in rows]
    finally:
        db.close()

    if args.limit > 0:
        tmdb_ids = tmdb_ids[: args.limit]

    print(f"대상: {len(tmdb_ids)}건  dry_run={args.dry_run}  batch={args.batch}")
    if args.dry_run:
        print("(dry-run 모드: API 호출 및 DB 저장 없음)")
        return

    result = asyncio.run(_run(tmdb_ids, api_key, args.batch, dry_run=False))
    print("\n=== 완료 ===")
    for k, v in result.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
