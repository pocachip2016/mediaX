#!/usr/bin/env python3
"""
Watcha 237건 포스터 → ContentImage 연결 (backfill)

입력: data/watcha_real/detail_real.csv + data/watcha_real/posters/<slug>.jpg
출력:
  - ContentImage rows in DB (source='cp', image_type='poster')
  - data/watcha_real/link_report.csv (matched/multi/unmatched/missing)

멱등: 동일 (content_id, image_type, url) 존재 시 skip (add_content_image 내부 처리)
"""

import csv
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from shared.database import SessionLocal
from api.programming.metadata.models import Content
from api.programming.metadata.service import add_content_image

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DETAIL_CSV = ROOT / "data" / "watcha_real" / "detail_real.csv"
POSTERS_DIR = ROOT / "data" / "watcha_real" / "posters"
REPORT_CSV = ROOT / "data" / "watcha_real" / "link_report.csv"


def main() -> None:
    logger.info("=== 05_link_posters: Watcha poster backfill ===")

    with open(DETAIL_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    logger.info(f"입력: {len(rows)}건 (detail_real.csv)")

    db = SessionLocal()
    report = []
    matched = multi = unmatched = missing = skipped = 0

    try:
        for row in rows:
            slug = row["slug"].strip()
            title = row["title"].strip()
            year_str = row.get("year", "").strip()
            production_year = int(year_str) if year_str.isdigit() else None

            poster_file = POSTERS_DIR / f"{slug}.jpg"
            if not poster_file.exists():
                report.append({"slug": slug, "title": title, "status": "missing", "content_id": ""})
                missing += 1
                continue

            # DB 매칭 — 연도 필터 우선, 결과 없으면 title-only fallback
            q = db.query(Content).filter(Content.cp_name == "Watcha", Content.title == title)
            if production_year:
                candidates = q.filter(Content.production_year == production_year).order_by(Content.id.desc()).all()
                if not candidates:
                    # omission 업로드로 DB에 year=None 저장된 경우
                    candidates = q.order_by(Content.id.desc()).all()
            else:
                candidates = q.order_by(Content.id.desc()).all()

            if not candidates:
                report.append({"slug": slug, "title": title, "status": "unmatched", "content_id": ""})
                unmatched += 1
                continue

            status = "matched" if len(candidates) == 1 else "multi"
            # 중복 시 가장 오래된(id 최소) row를 canonical로 사용
            content = candidates[0]

            url = f"/static/posters/{slug}.jpg"
            result = add_content_image(db, content.id, "poster", url, source="cp")
            if result is None:
                # content not found (shouldn't happen)
                report.append({"slug": slug, "title": title, "status": "unmatched", "content_id": str(content.id)})
                unmatched += 1
                continue

            report.append({"slug": slug, "title": title, "status": status, "content_id": str(content.id)})
            if status == "matched":
                matched += 1
            else:
                multi += 1

        db.commit()
    finally:
        db.close()

    with open(REPORT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["slug", "title", "status", "content_id"])
        writer.writeheader()
        writer.writerows(report)

    total_created = matched + multi
    logger.info(f"matched:   {matched}")
    logger.info(f"multi:     {multi}")
    logger.info(f"unmatched: {unmatched}")
    logger.info(f"missing:   {missing}")
    logger.info(f"ContentImage 생성/skip: {total_created}건 → {REPORT_CSV}")

    if total_created < 220:
        logger.warning(f"⚠ matched+multi={total_created} < 220 — link_report.csv 확인 필요")
        sys.exit(1)

    logger.info("=== Complete ===")


if __name__ == "__main__":
    main()
