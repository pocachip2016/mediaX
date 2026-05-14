#!/usr/bin/env python3
"""
Step 1.4: Watcha 포스터 이미지 일괄 다운로드

입력: backend/data/watcha_real/detail_real.csv
출력:
  - backend/data/watcha_real/posters/<slug>.<ext>
  - backend/data/watcha_real/expired_posters.csv (JWT 만료 건)
"""

import csv
import logging
import mimetypes
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "watcha_real"
DETAIL_CSV = DATA_DIR / "detail_real.csv"
POSTERS_DIR = DATA_DIR / "posters"
EXPIRED_CSV = DATA_DIR / "expired_posters.csv"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
MAX_WORKERS = 4
RETRY_SLEEP = 2


def ext_from_content_type(ct: str) -> str:
    if "webp" in ct:
        return ".webp"
    if "jpeg" in ct or "jpg" in ct:
        return ".jpg"
    if "png" in ct:
        return ".png"
    return ".bin"


def download_poster(slug: str, poster_url: str, dest_dir: Path) -> tuple[str, Path | None, str | None]:
    """
    Returns: (slug, saved_path, error_reason)
    """
    try:
        r = requests.get(
            poster_url,
            headers={"User-Agent": UA},
            timeout=20,
            stream=True,
        )

        if r.status_code in (401, 403):
            return slug, None, f"jwt_expired_{r.status_code}"

        if r.status_code != 200:
            return slug, None, f"http_{r.status_code}"

        ct = r.headers.get("Content-Type", "image/webp")
        ext = ext_from_content_type(ct)
        dest = dest_dir / f"{slug}{ext}"

        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        return slug, dest, None

    except Exception as e:
        return slug, None, str(e)


def main():
    POSTERS_DIR.mkdir(parents=True, exist_ok=True)

    with open(DETAIL_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    logger.info(f"Total rows: {len(rows)}")

    # 이미 다운로드된 slug 확인
    existing_slugs = {p.stem for p in POSTERS_DIR.iterdir() if p.is_file()}
    logger.info(f"Already downloaded: {len(existing_slugs)}")

    pending = [r for r in rows if r["slug"] not in existing_slugs and r.get("poster_url")]
    logger.info(f"Pending: {len(pending)}")

    success_count = 0
    skip_count = len(rows) - len(pending)
    expired_rows = []
    fail_rows = []

    def task(row):
        return download_poster(row["slug"], row["poster_url"], POSTERS_DIR)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(task, row): row for row in pending}
        done_count = 0

        for future in as_completed(futures):
            slug, path, error = future.result()
            done_count += 1

            if path:
                success_count += 1
                if done_count % 50 == 0:
                    logger.info(f"Progress: {done_count}/{len(pending)} done, {success_count} saved, {len(expired_rows)} expired")
            elif error and "jwt_expired" in error:
                expired_rows.append({"slug": slug, "poster_url": futures[future]["poster_url"], "error": error})
            else:
                fail_rows.append({"slug": slug, "error": error or "unknown"})
                logger.warning(f"  ✗ {slug}: {error}")

            time.sleep(0.1)

    # expired_posters.csv 저장
    if expired_rows:
        with open(EXPIRED_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["slug", "poster_url", "error"])
            writer.writeheader()
            writer.writerows(expired_rows)

    logger.info("=== Complete ===")
    logger.info(f"Success: {success_count}, Skipped: {skip_count}, Expired JWT: {len(expired_rows)}, Other fail: {len(fail_rows)}")
    logger.info(f"Posters saved to: {POSTERS_DIR}")
    if expired_rows:
        logger.info(f"JWT expired list: {EXPIRED_CSV}")


if __name__ == "__main__":
    main()
