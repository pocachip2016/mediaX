#!/usr/bin/env python3
"""
Step 1.5: detail_real.csv → watcha_upload.csv 변환 + omission 적용

입력: backend/data/watcha_real/detail_real.csv
출력:
  - backend/data/watcha/upload/watcha_upload.csv  (5컬럼)
  - backend/data/watcha/upload/omission_log.csv   (누락 로그)
  - backend/data/watcha/upload/_mock_backup/       (기존 파일 백업)
"""

import csv
import logging
import random
import shutil
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

REAL_DIR = Path(__file__).parent.parent.parent / "data" / "watcha_real"
UPLOAD_DIR = Path(__file__).parent.parent.parent / "data" / "watcha" / "upload"
DETAIL_CSV = REAL_DIR / "detail_real.csv"
OUTPUT_CSV = UPLOAD_DIR / "watcha_upload.csv"
OMISSION_LOG = UPLOAD_DIR / "omission_log.csv"
BACKUP_DIR = UPLOAD_DIR / "_mock_backup"

# omission 대상 필드 (title은 필수 유지)
OMITTABLE = ["production_year", "synopsis", "cp_name"]
OMIT_RATIO = 0.20  # 전체 행의 20%

random.seed(42)


def backup_existing():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    for fname in ["watcha_upload.csv", "omission_log.csv"]:
        src = UPLOAD_DIR / fname
        if src.exists():
            dst = BACKUP_DIR / f"{ts}_{fname}"
            shutil.copy2(src, dst)
            logger.info(f"  백업: {src.name} → {dst.name}")


def main():
    logger.info("=== Step 1.5: csv-conversion ===")

    with open(DETAIL_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    logger.info(f"입력: {len(rows)}건 (detail_real.csv)")

    backup_existing()

    # omission 대상 선정: 20% 무작위 (seed=42)
    all_indices = list(range(len(rows)))
    omit_count = max(1, int(len(rows) * OMIT_RATIO))
    omit_indices = set(random.sample(all_indices, omit_count))

    upload_rows = []
    omission_rows = []

    for i, row in enumerate(rows):
        title = row.get("title", "").strip()
        production_year = row.get("year", "").strip()
        content_type = row.get("content_type", "movie").strip()
        cp_name = "Watcha"
        synopsis = row.get("synopsis", "").strip()
        slug = row.get("slug", "")

        upload_row = {
            "title": title,
            "production_year": production_year,
            "content_type": content_type,
            "cp_name": cp_name,
            "synopsis": synopsis,
        }

        if i in omit_indices:
            # 1~2개 필드 무작위 누락
            n_omit = random.randint(1, 2)
            fields_to_omit = random.sample(OMITTABLE, n_omit)
            for fld in fields_to_omit:
                upload_row[fld] = ""
            omission_rows.append({
                "slug": slug,
                "title": title,
                "omitted_fields": ",".join(fields_to_omit),
            })

        upload_rows.append(upload_row)

    # watcha_upload.csv 저장
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "production_year", "content_type", "cp_name", "synopsis"])
        writer.writeheader()
        writer.writerows(upload_rows)

    # omission_log.csv 저장
    with open(OMISSION_LOG, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["slug", "title", "omitted_fields"])
        writer.writeheader()
        writer.writerows(omission_rows)

    omit_pct = len(omission_rows) / len(rows) * 100
    logger.info(f"=== Complete ===")
    logger.info(f"총 {len(upload_rows)}건 → {OUTPUT_CSV}")
    logger.info(f"omission: {len(omission_rows)}건 ({omit_pct:.1f}%) → {OMISSION_LOG}")


if __name__ == "__main__":
    main()
