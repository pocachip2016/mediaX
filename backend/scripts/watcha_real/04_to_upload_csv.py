#!/usr/bin/env python3
"""
Step 1.5: detail_real.csv → watcha_upload.csv 변환 (12열)

입력: backend/data/watcha_real/detail_real.csv
출력:
  - backend/data/watcha/upload/watcha_upload.csv  (12컬럼)
  - backend/data/watcha/upload/omission_log.csv   (누락 로그)
  - backend/data/watcha/upload/_mock_backup/       (기존 파일 백업)

변환 규칙:
  - genres: "드라마/, 판타지/" → "드라마, 판타지"
  - runtime: "1시간 30분" / "90분" → 90 (int 분)
  - cast: JSON list[dict] → "배우A, 배우B"
  - directors: JSON list[str] → "감독1, 감독2"
  - omission 시뮬레이션: production_year/synopsis/cp_name 에만 적용
    (cast/directors 는 credits 검증 목적으로 누락 제외)
"""

import csv
import json
import logging
import random
import re
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

OMITTABLE = ["production_year", "synopsis", "cp_name"]
OMIT_RATIO = 0.20

random.seed(42)

OUTPUT_FIELDS = [
    "title", "production_year", "content_type", "cp_name", "synopsis",
    "cast", "directors", "genres", "country", "runtime", "rating_age", "poster_url",
]


def backup_existing():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    for fname in ["watcha_upload.csv", "omission_log.csv"]:
        src = UPLOAD_DIR / fname
        if src.exists():
            dst = BACKUP_DIR / f"{ts}_{fname}"
            shutil.copy2(src, dst)
            logger.info(f"  백업: {src.name} → {dst.name}")


def clean_genres(genre_str: str) -> str:
    if not genre_str:
        return ""
    return ", ".join(g.strip().rstrip("/") for g in genre_str.split(",") if g.strip())


def parse_runtime(runtime_str: str) -> str:
    if not runtime_str:
        return ""
    m = re.match(r"(?:(\d+)시간\s*)?(\d+)분", runtime_str.strip())
    if m:
        hours = int(m.group(1) or 0)
        mins = int(m.group(2))
        return str(hours * 60 + mins)
    m2 = re.match(r"(\d+)", runtime_str)
    if m2:
        return m2.group(1)
    return ""


def cast_to_str(cast_raw: str) -> str:
    if not cast_raw:
        return ""
    try:
        items = json.loads(cast_raw)
        if isinstance(items, list):
            return ", ".join(item.get("name", "") for item in items if item.get("name"))
    except Exception:
        pass
    return cast_raw


def directors_to_str(directors_raw: str) -> str:
    if not directors_raw:
        return ""
    try:
        items = json.loads(directors_raw)
        if isinstance(items, list):
            return ", ".join(str(d) for d in items if d)
    except Exception:
        pass
    return directors_raw


def main():
    logger.info("=== Step 1.5: csv-conversion (12열) ===")

    with open(DETAIL_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    logger.info(f"입력: {len(rows)}건 (detail_real.csv)")

    backup_existing()

    all_indices = list(range(len(rows)))
    omit_count = max(1, int(len(rows) * OMIT_RATIO))
    omit_indices = set(random.sample(all_indices, omit_count))

    upload_rows = []
    omission_rows = []

    for i, row in enumerate(rows):
        title = row.get("title", "").strip()
        production_year = row.get("year", "").strip()
        content_type = row.get("content_type", "movie").strip() or "movie"
        cp_name = "Watcha"
        synopsis = row.get("synopsis", "").strip()
        cast = cast_to_str(row.get("cast", ""))
        directors = directors_to_str(row.get("directors", ""))
        genres = clean_genres(row.get("genres", ""))
        country = row.get("country", "").strip()
        runtime = parse_runtime(row.get("runtime", ""))
        rating_age = row.get("rating_age", "").strip()
        poster_url = row.get("poster_url", "").strip()
        slug = row.get("slug", "")

        upload_row = {
            "title": title,
            "production_year": production_year,
            "content_type": content_type,
            "cp_name": cp_name,
            "synopsis": synopsis,
            "cast": cast,
            "directors": directors,
            "genres": genres,
            "country": country,
            "runtime": runtime,
            "rating_age": rating_age,
            "poster_url": poster_url,
        }

        if i in omit_indices:
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

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(upload_rows)

    with open(OMISSION_LOG, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["slug", "title", "omitted_fields"])
        writer.writeheader()
        writer.writerows(omission_rows)

    omit_pct = len(omission_rows) / len(rows) * 100 if rows else 0
    logger.info(f"=== Complete ===")
    logger.info(f"총 {len(upload_rows)}건 → {OUTPUT_CSV}")
    logger.info(f"omission: {len(omission_rows)}건 ({omit_pct:.1f}%)")

    cast_filled = sum(1 for r in upload_rows if r.get("cast"))
    dir_filled = sum(1 for r in upload_rows if r.get("directors"))
    logger.info(f"cast 보유: {cast_filled}건, directors 보유: {dir_filled}건")


if __name__ == "__main__":
    main()
