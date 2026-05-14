#!/usr/bin/env python3
"""
Step 4.2: Batch download Watcha posters.
(For mock data, creates placeholder files)

Output: backend/data/watcha/posters/ + detail_final.csv
"""

import csv
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "watcha"
POSTERS_DIR = DATA_DIR / "posters"


def main():
    logger.info("=== Step 4.2: batch-download-posters ===")

    # Load detail.csv
    detail_file = DATA_DIR / "detail.csv"
    rows = []
    with open(detail_file) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    logger.info(f"Loaded {len(rows)} items from detail.csv")

    # Create posters directory
    POSTERS_DIR.mkdir(parents=True, exist_ok=True)

    # Create placeholder files for each poster
    for i, row in enumerate(rows):
        watcha_id = row["watcha_id"]
        poster_path = POSTERS_DIR / f"{watcha_id}.jpg"
        # Create empty placeholder file (real download would go here)
        poster_path.write_bytes(b"")

        if (i + 1) % 300 == 0:
            logger.info(f"Created {i + 1}/{len(rows)} poster placeholders")

    # Add poster_local_path to rows
    for row in rows:
        watcha_id = row["watcha_id"]
        row["poster_local_path"] = str(POSTERS_DIR / f"{watcha_id}.jpg")

    # Save detail_final.csv
    detail_final_file = DATA_DIR / "detail_final.csv"
    fieldnames = list(rows[0].keys()) if rows else []
    if "poster_local_path" not in fieldnames:
        fieldnames.append("poster_local_path")

    with open(detail_final_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"Saved {len(rows)} rows to detail_final.csv")

    # Summary
    poster_count = len(list(POSTERS_DIR.glob("*.jpg")))
    logger.info(f"Created {poster_count} poster placeholders")
    print(f"\n✓ Posters: {poster_count}/{len(rows)}")
    print(f"✓ detail_final.csv: {len(rows)} rows")

    return poster_count >= len(rows) * 0.9


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
