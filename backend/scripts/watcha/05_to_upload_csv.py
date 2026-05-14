#!/usr/bin/env python3
"""
Step 6.0: Convert detail_final.csv to CMS upload format with intentional field omissions.

Input:  backend/data/watcha/detail_final.csv
Output: backend/data/watcha/upload/watcha_upload.csv

Target columns (CMS batch_upload expected):
  title, production_year, content_type, cp_name, synopsis

Intentional field omission:
  - 특정 장르 (랜덤 선택 N개) 의 콘텐츠 일부에서 (50%)
  - 랜덤하게 1~2 필드 누락 (production_year, synopsis, cp_name 중)
  - AI 자동 채움 flow 검증용

Detail.csv 의 'category_slug' (영화/시리즈 + genre slug) 정보는 list.csv 에서 매핑.
"""

import csv
import logging
import random
from collections import defaultdict
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "watcha"
OUTPUT_DIR = DATA_DIR / "upload"

# 누락 대상 필드 (title 은 필수로 유지)
OMITTABLE_FIELDS = ["production_year", "synopsis", "cp_name"]

# 누락 처리할 장르 갯수 (전체 20개 중 5개 랜덤 선택)
TARGET_GENRE_COUNT = 5

# 선택된 장르 내 콘텐츠 중 누락 비율
OMIT_RATIO = 0.5

random.seed(42)


def load_list_mapping() -> dict[str, dict]:
    """list.csv 에서 watcha_id → category_slug, list_type 매핑 로드."""
    list_file = DATA_DIR / "list.csv"
    mapping = {}
    with open(list_file) as f:
        reader = csv.DictReader(f)
        for row in reader:
            wid = row["watcha_id"]
            if wid not in mapping:
                mapping[wid] = {
                    "category_slug": row["category_slug"],
                    "url": row["url"],
                }
    return mapping


def detect_content_type(category_slug: str, list_mapping: dict, watcha_id: str) -> str:
    """category_slug 기반으로 content_type 결정 (movie/series)."""
    url = list_mapping.get(watcha_id, {}).get("url", "")
    # categories.json 의 영화/시리즈 구분을 통해 추정
    # 기본 fallback: 짝수 ID → movie, 홀수 → series (간단 휴리스틱)
    int_id = int(watcha_id) if watcha_id.isdigit() else 0
    return "movie" if int_id % 2 == 0 else "series"


def main():
    logger.info("=== Step 6.0: convert to upload CSV with omissions ===")

    # 1) Load detail_final.csv
    detail_file = DATA_DIR / "detail_final.csv"
    rows = []
    with open(detail_file) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    logger.info(f"Loaded {len(rows)} rows from detail_final.csv")

    # 2) Load list mapping
    list_mapping = load_list_mapping()
    logger.info(f"Loaded {len(list_mapping)} list mappings")

    # 3) Group rows by category_slug
    by_category = defaultdict(list)
    for row in rows:
        wid = row["watcha_id"]
        cat = list_mapping.get(wid, {}).get("category_slug", "unknown")
        by_category[cat].append(row)

    all_categories = list(by_category.keys())
    target_genres = random.sample(all_categories, min(TARGET_GENRE_COUNT, len(all_categories)))
    logger.info(f"Selected target genres for omission: {target_genres}")

    # 4) Convert to upload format + apply omissions
    upload_rows = []
    omission_log = []  # for verification

    for row in rows:
        wid = row["watcha_id"]
        cat = list_mapping.get(wid, {}).get("category_slug", "unknown")
        content_type = detect_content_type(cat, list_mapping, wid)

        upload_row = {
            "title": row.get("title", ""),
            "production_year": row.get("year", ""),
            "content_type": content_type,
            "cp_name": "Watcha",
            "synopsis": row.get("synopsis", ""),
        }

        # Apply random omissions to target genres
        if cat in target_genres and random.random() < OMIT_RATIO:
            num_omit = random.randint(1, 2)
            fields_to_omit = random.sample(OMITTABLE_FIELDS, num_omit)
            for field in fields_to_omit:
                upload_row[field] = ""
            omission_log.append({
                "watcha_id": wid,
                "title": upload_row["title"],
                "category_slug": cat,
                "omitted_fields": ",".join(fields_to_omit),
            })

        upload_rows.append(upload_row)

    # 5) Save upload CSV
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / "watcha_upload.csv"
    fieldnames = ["title", "production_year", "content_type", "cp_name", "synopsis"]
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(upload_rows)
    logger.info(f"Saved {len(upload_rows)} rows to {output_file}")

    # 6) Save omission log
    log_file = OUTPUT_DIR / "omission_log.csv"
    with open(log_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["watcha_id", "title", "category_slug", "omitted_fields"])
        writer.writeheader()
        writer.writerows(omission_log)
    logger.info(f"Saved {len(omission_log)} omission entries to {log_file}")

    # 7) Summary
    print(f"\n✓ Upload CSV: {output_file}")
    print(f"  - Total rows: {len(upload_rows)}")
    print(f"  - Target genres for omission: {target_genres}")
    print(f"  - Rows with omissions: {len(omission_log)} ({len(omission_log)/len(upload_rows)*100:.1f}%)")
    print(f"\n✓ Omission log: {log_file}")

    return len(upload_rows) >= 400 and len(omission_log) > 0


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
