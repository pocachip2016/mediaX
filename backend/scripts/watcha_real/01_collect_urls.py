#!/usr/bin/env python3
"""
Step 1.2: Watcha Pedia URL 수집 — Playwright로 동적 페이지 크롤

출력: backend/data/watcha_real/list_real.csv
  slug,url,title_preview,category,fetched_at
"""

import csv
import logging
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://pedia.watcha.com"
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "watcha_real"
OUTPUT_CSV = DATA_DIR / "list_real.csv"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

TARGET_COUNT = 250
MOVIE_RATIO = 0.8
MOVIE_TARGET = int(TARGET_COUNT * MOVIE_RATIO)  # ~200
TV_TARGET = TARGET_COUNT - MOVIE_TARGET  # ~50

def scrape_page_playwright(page, url: str, category: str) -> list[dict]:
    """
    Playwright로 페이지 로드 후 무한스크롤로 카드 URL 추출.
    """
    items = []
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        time.sleep(random.uniform(2, 3))

        # 무한스크롤 — 5회까지만 시도 (시간 제약)
        prev_count = 0
        for scroll_attempt in range(5):
            # 현재 카드 수
            links = page.query_selector_all('a[href^="/ko/contents/"]')
            curr_count = len(links)

            if curr_count == prev_count:
                logger.info(f"  no new content after scroll {scroll_attempt}. stopping.")
                break

            logger.info(f"  scroll {scroll_attempt}: {curr_count} links")
            prev_count = curr_count

            # 페이지 끝으로 스크롤
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(random.uniform(1, 2))

        # 최종 카드 추출
        links = page.query_selector_all('a[href^="/ko/contents/"]')
        logger.info(f"  final: {len(links)} links on {url.split('/')[-1]}")

        for link in links:
            href = link.get_attribute('href') or ''
            if href and href.startswith('/ko/contents/'):
                slug = href.split('/')[-1]
                title = link.text_content() or ''
                title = title.strip()[:100] if title else None
                items.append({
                    'slug': slug,
                    'url': urljoin(BASE_URL, href),
                    'title_preview': title,
                    'category': category,
                    'fetched_at': datetime.now().isoformat(),
                })

        return items
    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
        return []

def collect_urls() -> list[dict]:
    """
    영화 + 시리즈 URL 수집 — Playwright 브라우저 자동화.
    """
    logger.info(f"Target: {MOVIE_TARGET} movies + {TV_TARGET} tv = {TARGET_COUNT} total")

    all_items = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=UA)

        # 스크랩할 URL 목록 (우선순위: 영화 먼저, 그 다음 시리즈)
        urls = [
            ("https://pedia.watcha.com/ko?domain=movie", "movie"),
            ("https://pedia.watcha.com/ko/upcoming/movie", "movie"),
            ("https://pedia.watcha.com/ko?domain=tv", "series"),
            ("https://pedia.watcha.com/ko/upcoming/tv", "series"),
        ]

        for url, category in urls:
            logger.info(f"Scraping {url}...")
            page_items = scrape_page_playwright(page, url, category)
            all_items.extend(page_items)

            # 영화/시리즈별로 목표에 도달했나 확인
            movie_count = sum(1 for item in all_items if item['category'] == 'movie')
            tv_count = sum(1 for item in all_items if item['category'] == 'series')

            if movie_count >= MOVIE_TARGET and tv_count >= TV_TARGET:
                logger.info(f"Reached both targets (movies: {movie_count}, tv: {tv_count}). Stopping.")
                break

            time.sleep(random.uniform(2, 4))

        browser.close()

    # 중복 제거 (slug 기준)
    seen = set()
    unique_items = []
    for item in all_items:
        if item['slug'] not in seen:
            seen.add(item['slug'])
            unique_items.append(item)

    logger.info(f"Total unique URLs before sampling: {len(unique_items)}")

    # 목표 비율로 샘플링
    random.seed(42)
    movie_items = [item for item in unique_items if item['category'] == 'movie']
    tv_items = [item for item in unique_items if item['category'] == 'series']

    sampled_movies = random.sample(movie_items, min(MOVIE_TARGET, len(movie_items)))
    sampled_tv = random.sample(tv_items, min(TV_TARGET, len(tv_items)))

    final_items = sampled_movies + sampled_tv
    random.shuffle(final_items)

    logger.info(f"After sampling: {len(final_items)} URLs (movies: {len(sampled_movies)}, tv: {len(sampled_tv)})")
    return final_items

def main():
    """
    URL 수집 → CSV 저장.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("=== Step 1.2: URL Collector (Playwright) ===")

    items = collect_urls()

    if not items:
        logger.error("No items collected!")
        return

    # CSV 저장
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['slug', 'url', 'title_preview', 'category', 'fetched_at'])
        writer.writeheader()
        writer.writerows(items)

    logger.info(f"✓ Saved {len(items)} URLs to {OUTPUT_CSV}")

    # 통계
    movie_count = sum(1 for item in items if item['category'] == 'movie')
    tv_count = len(items) - movie_count
    logger.info(f"  movies: {movie_count}, tv: {tv_count}, ratio: {movie_count}/{len(items)}")

if __name__ == "__main__":
    main()
