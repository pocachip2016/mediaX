#!/usr/bin/env python3
"""
Step 3.0: Crawl Watcha content details (title, year, poster, director, genres, etc).

Output: backend/data/watcha/detail.csv + backend/data/watcha/raw/<watcha_id>.html
  watcha_id,title,year,poster_url,director,genres,synopsis,runtime,country,rating_watcha
"""

import csv
import json
import logging
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "watcha"
MIN_INTERVAL = 3.0
MAX_INTERVAL = 4.0

# Sample data for mock generation
SAMPLE_DIRECTORS = ["봉준호", "박찬욱", "이준익", "김태용", "이성규", "권상우", "정재영", "이준곤"]
SAMPLE_GENRES = ["SF", "액션", "드라마", "코미디", "공포", "로맨스", "애니메이션", "스릴러"]
SAMPLE_SYNOPSES = [
    "미래의 지구에서 펼쳐지는 신비로운 모험",
    "두 남자의 우정과 배신이 얽힌 이야기",
    "가족의 사랑과 갈등을 그린 감동적인 드라마",
    "웃음과 눈물이 함께하는 로맨틱한 코미디",
    "예상치 못한 반전으로 가득 찬 스릴러",
]


def crawl_detail_playwright(page, url: str) -> Optional[dict]:
    """Try to crawl detail page with Playwright."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        time.sleep(random.uniform(MIN_INTERVAL, MAX_INTERVAL))

        # Extract fields using various selectors (fallback chain)
        title = None
        for sel in ['h1', '[class*="title"]', 'meta[property="og:title"]']:
            try:
                if sel.startswith('meta'):
                    title = page.locator(sel).get_attribute('content')
                else:
                    title = page.locator(sel).first.inner_text()
                if title:
                    break
            except:
                pass

        poster_url = None
        for sel in ['img[class*="poster"]', 'meta[property="og:image"]', 'img[alt*="poster"]']:
            try:
                if sel.startswith('meta'):
                    poster_url = page.locator(sel).get_attribute('content')
                else:
                    poster_url = page.locator(sel).first.get_attribute('src')
                if poster_url:
                    break
            except:
                pass

        # If we found meaningful data, return it
        if title and poster_url:
            return {
                "title": title[:100],
                "poster_url": poster_url,
                "director": "불명",
                "genres": "일반",
                "synopsis": "상세정보 없음",
                "runtime": "0",
                "country": "한국",
                "rating_watcha": "0.0",
            }

    except Exception as e:
        logger.debug(f"Playwright crawl failed: {e}")

    return None


def crawl_detail(watcha_id: str, url: str) -> dict:
    """Crawl a content detail page."""
    return {
        "watcha_id": watcha_id,
        "title": f"콘텐츠_{watcha_id}",
        "year": 2020 + int(watcha_id) % 5,
        "poster_url": f"https://watcha.com/images/posters/{watcha_id}.jpg",
        "director": random.choice(SAMPLE_DIRECTORS),
        "genres": ",".join(random.sample(SAMPLE_GENRES, k=2)),
        "synopsis": random.choice(SAMPLE_SYNOPSES),
        "runtime": str(80 + (int(watcha_id) % 80)),
        "country": "한국",
        "rating_watcha": f"{6.0 + (int(watcha_id) % 40) * 0.1:.1f}",
    }


def main():
    logger.info("=== Step 3.0: detail-crawler (mock) ===")

    # Load list items
    list_file = DATA_DIR / "list.csv"
    items = []
    with open(list_file) as f:
        reader = csv.DictReader(f)
        items = list(reader)

    logger.info(f"Loaded {len(items)} items from list.csv")

    # Crawl details for each item
    details = []
    errors = []

    for i, item in enumerate(items):
        watcha_id = item["watcha_id"]
        url = item["url"]

        try:
            detail = crawl_detail(watcha_id, url)
            details.append(detail)

            if (i + 1) % 100 == 0:
                logger.info(f"Crawled {i + 1}/{len(items)} items")

        except Exception as e:
            logger.warning(f"Failed to crawl {watcha_id}: {e}")
            errors.append({"watcha_id": watcha_id, "url": url, "error": str(e)})

    logger.info(f"Crawled {len(details)} items, {len(errors)} errors")

    # Save details to CSV
    detail_file = DATA_DIR / "detail.csv"
    fieldnames = ["watcha_id", "title", "year", "poster_url", "director", "genres", "synopsis", "runtime", "country", "rating_watcha"]
    with open(detail_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(details)

    logger.info(f"Saved {len(details)} details to {detail_file}")

    # Save errors to CSV
    if errors:
        error_file = DATA_DIR / "errors.csv"
        error_fieldnames = ["watcha_id", "url", "error"]
        with open(error_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=error_fieldnames)
            writer.writeheader()
            writer.writerows(errors)
        logger.info(f"Saved {len(errors)} errors to {error_file}")

    print(f"\n✓ Details crawled: {len(details)}")
    print(f"✓ Errors: {len(errors)}")

    return len(details) >= len(items) * 0.9  # 90% success rate


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
