#!/usr/bin/env python3
"""
Step 1.3: Watcha Pedia 상세 페이지 메타데이터 추출

입력: backend/data/watcha_real/list_real.csv
출력:
  - backend/data/watcha_real/detail_real.csv (성공 건)
  - backend/data/watcha_real/fail_log.csv (실패 건)
"""

import csv
import logging
import random
import re
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
INPUT_CSV = DATA_DIR / "list_real.csv"
OUTPUT_CSV = DATA_DIR / "detail_real.csv"
FAIL_LOG = DATA_DIR / "fail_log.csv"
RAW_DIR = DATA_DIR / "raw"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

def extract_metadata(page, url: str) -> Optional[dict]:
    """
    Playwright 페이지에서 메타데이터 추출.
    필수 필드: title, year, synopsis, poster_url
    """
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        time.sleep(random.uniform(1, 2))

        # og:title (예: "도화년 (2024) - 왓챠피디아" 또는 "성난 사람들 시즌 1 (2023) - 왓챠피디아")
        og_title = None
        title = None
        year_from_title = None
        try:
            title_elem = page.query_selector('meta[property="og:title"]')
            if title_elem:
                og_title = title_elem.get_attribute('content')
        except:
            pass

        if og_title:
            # 연도 추출 — "(YYYY)" 패턴
            year_match = re.search(r'\((\d{4})\)', og_title)
            if year_match:
                year_from_title = year_match.group(1)

            # title 정제 — "(YYYY) - 왓챠피디아" 등 꼬리 제거
            t = re.sub(r'\s*-\s*왓챠피디아\s*$', '', og_title)
            t = re.sub(r'\s*\(\d{4}\)\s*$', '', t)
            title = t.strip()

        if not title:
            try:
                h1 = page.query_selector('h1')
                if h1:
                    title = h1.text_content().strip()
            except:
                pass

        # og:image (포스터)
        poster_url = None
        try:
            poster_elem = page.query_selector('meta[property="og:image"]')
            if poster_elem:
                poster_url = poster_elem.get_attribute('content')
        except:
            pass

        # og:description (시놉시스)
        synopsis = None
        try:
            desc_elem = page.query_selector('meta[name="description"]')
            if desc_elem:
                synopsis = desc_elem.get_attribute('content')
        except:
            pass

        if not synopsis:
            try:
                # 본문 단락 찾기
                p_elems = page.query_selector_all('p')
                for p in p_elems:
                    text = p.text_content().strip()
                    if len(text) > 100 and '뉴욕' in text or '영화' in text or '드라마' in text:
                        synopsis = text[:500]
                        break
            except:
                pass

        # 정보 라인 (연도, 장르, 국가, 러닝타임, 등급)
        year = None
        genres = None
        country = None
        runtime = None
        rating_age = None

        try:
            # 정보 라인: "2007 · 범죄/드라마/... · 미국 1시간 59분 · 15세"
            info_text = page.locator('body').text_content()

            # 연도 우선순위: og:title > body 본문
            if year_from_title:
                year = year_from_title
            else:
                year_match = re.search(r'(19|20)\d{2}', info_text)
                if year_match:
                    year = year_match.group(0)

            # 장르 추출 (한글 단어 / 로 분리)
            genres_match = re.search(r'·\s*([가-힣/]+(?:/[가-힣]+)*)', info_text)
            if genres_match:
                genres = genres_match.group(1)

            # 국가 추출
            country_match = re.search(r'·\s*(미국|한국|일본|중국|영국|프랑스|독일|스페인|이탈리아|캐나다|호주|인도|러시아|멕시코|브라질|태국|홍콩|대만)', info_text)
            if country_match:
                country = country_match.group(1)

            # 러닝타임 추출
            runtime_match = re.search(r'(\d+시간\s*\d+분|\d+분)', info_text)
            if runtime_match:
                runtime = runtime_match.group(1)

            # 등급 추출
            rating_match = re.search(r'(전체관람가|12세|15세|19세|청소년관람불가|R등급|PG-\d+)', info_text)
            if rating_match:
                rating_age = rating_match.group(1)
        except:
            pass

        # content_type 은 category 에서 결정 (caller가 전달)
        # 필수 필드 체크
        if not title or not year or not synopsis or not poster_url:
            logger.warning(f"Missing required fields: title={bool(title)}, year={bool(year)}, synopsis={bool(synopsis)}, poster_url={bool(poster_url)}")
            return None

        return {
            'title': title[:200],
            'year': year,
            'genres': genres or '',
            'country': country or '',
            'runtime': runtime or '',
            'rating_age': rating_age or '',
            'synopsis': synopsis[:500],
            'poster_url': poster_url,
        }

    except Exception as e:
        logger.error(f"Error crawling {url}: {e}")
        return None

def crawl_details():
    """
    list_real.csv → detail_real.csv + fail_log.csv
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 기존 detail_real.csv 체크 (append 모드)
    existing_slugs = set()
    if OUTPUT_CSV.exists():
        with open(OUTPUT_CSV) as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_slugs.add(row['slug'])
        logger.info(f"Found {len(existing_slugs)} existing records. Will append new ones.")

    success_count = 0
    fail_count = 0
    fail_rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=UA)

        with open(INPUT_CSV) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        logger.info(f"Total URLs to crawl: {len(rows)}")

        for i, row in enumerate(rows):
            slug = row['slug']
            url = row['url']
            category = row['category']

            if slug in existing_slugs:
                logger.info(f"[{i+1}/{len(rows)}] {slug} (skip: already exists)")
                continue

            logger.info(f"[{i+1}/{len(rows)}] Crawling {slug}...")

            meta = extract_metadata(page, url)

            if meta:
                meta['slug'] = slug
                meta['url'] = url
                meta['content_type'] = category
                meta['fetched_at'] = datetime.now().isoformat()

                # detail_real.csv 에 append
                mode = 'a' if OUTPUT_CSV.exists() else 'w'
                with open(OUTPUT_CSV, mode, newline='', encoding='utf-8') as f:
                    fieldnames = ['slug', 'url', 'title', 'year', 'genres', 'country', 'runtime', 'rating_age', 'synopsis', 'poster_url', 'content_type', 'fetched_at']
                    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                    if mode == 'w':
                        writer.writeheader()
                    writer.writerow(meta)

                success_count += 1
                logger.info(f"  ✓ {slug}")
            else:
                fail_rows.append({'slug': slug, 'url': url, 'error': 'missing_required_fields'})
                fail_count += 1
                logger.warning(f"  ✗ {slug}: missing required fields")

            # rate limit
            if (i + 1) % 50 == 0:
                logger.info(f"Pausing after 50 requests...")
                time.sleep(10)
            else:
                time.sleep(random.uniform(2, 4))

        browser.close()

    # fail_log.csv 저장
    if fail_rows:
        with open(FAIL_LOG, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['slug', 'url', 'error'])
            writer.writeheader()
            writer.writerows(fail_rows)

    logger.info(f"=== Complete ===")
    logger.info(f"Success: {success_count}, Failed: {fail_count}")
    logger.info(f"detail_real.csv: {OUTPUT_CSV}")
    if fail_rows:
        logger.info(f"fail_log.csv: {FAIL_LOG}")

def main():
    logger.info("=== Step 1.3: Detail Crawler ===")
    crawl_details()

if __name__ == "__main__":
    main()
