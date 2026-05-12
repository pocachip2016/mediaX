#!/usr/bin/env python3
"""
Step 2.0: Generate Watcha list items (신작/최신순/인기 × 카테고리 20개 × 20건).

Output: backend/data/watcha/list.csv
  watcha_id,url,title,year,list_type,category_slug,fetched_at

Note: Uses generated mock data for dev (실제 크롤링은 비동기 구현 필요).
"""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "watcha"

# Sample movie/series titles for mock generation
SAMPLE_TITLES = {
    "영화": [
        "블랙팬서", "어벤져스", "타이타닉", "인셉션", "인터스텔라",
        "다크나이트", "매트릭스", "글래디에이터", "라라랜드", "보헤미안랩소디",
        "스파이더맨", "아이언맨", "토르", "캡틴아메리카", "닥터스트레인지",
        "아쿠아맨", "원더우먼", "저스티스리그", "배트맨", "수퍼맨",
    ],
    "시리즈": [
        "게임오브스로온", "왕좌의게임", "브레이킹배드", "셜록", "마약의왕",
        "빅뱅이론", "프렌즈", "오피스", "스트레인저씽스", "더크라운",
        "맨달로리안", "위쳐", "핸드메이즈테일", "더보이즈", "카드집",
        "블랙미러", "바이오하자드", "나르코스", "하우스", "그레이아나토미",
    ],
}


def generate_lists() -> list[dict]:
    """Generate mock list items (영화/시리즈 × 카테고리 × list_type × 20건)."""
    items = []

    # Load categories
    categories_file = DATA_DIR / "categories.json"
    with open(categories_file) as f:
        categories = json.load(f)

    logger.info(f"Loaded {len(categories)} categories")

    list_types = ["new", "latest", "popular"]
    watcha_id_counter = 100000

    for cat in categories:
        depth1 = cat["depth1"]
        category_slug = cat["slug"]
        titles = SAMPLE_TITLES.get(depth1, SAMPLE_TITLES["영화"])

        for list_type in list_types:
            for i in range(20):  # 20 items per list
                watcha_id = str(watcha_id_counter)
                watcha_id_counter += 1

                title = titles[i % len(titles)]
                year = 2020 + (i % 5)

                items.append({
                    "watcha_id": watcha_id,
                    "url": f"https://watcha.com/contents/{watcha_id}",
                    "title": title,
                    "year": year,
                    "list_type": list_type,
                    "category_slug": category_slug,
                    "fetched_at": datetime.now().isoformat(),
                })

    return items


def main():
    logger.info("=== Step 2.0: list-crawler (mock) ===")

    items = generate_lists()
    logger.info(f"Generated {len(items)} items")

    # Save to CSV
    output_file = DATA_DIR / "list.csv"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["watcha_id", "url", "title", "year", "list_type", "category_slug", "fetched_at"]
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(items)

    logger.info(f"Saved {len(items)} items to {output_file}")
    print(f"\n✓ Items generated: {len(items)}")

    return len(items) >= 400


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
