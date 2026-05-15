#!/usr/bin/env python3
"""
Step 1.3: Watcha Pedia 상세 페이지 메타데이터 추출

입력: backend/data/watcha_real/list_real.csv
출력:
  - backend/data/watcha_real/detail_real.csv (성공 건)
  - backend/data/watcha_real/fail_log.csv (실패 건)

옵션:
  --patch     기존 detail_real.csv에서 cast/directors 미수집 행만 재크롤
  --limit N   처음 N건만 처리 (검증/개발용)
"""

import argparse
import csv
import json
import logging
import random
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

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

FIELDNAMES = [
    "slug", "url", "title", "year", "genres", "country", "runtime",
    "rating_age", "synopsis", "poster_url", "content_type", "fetched_at",
    "cast", "directors",
]

ROLE_LABELS = ["감독", "연출", "주연", "조연", "단역", "특별출연", "출연", "카메오"]
DIRECTOR_LABELS = {"감독", "연출"}


def extract_people(page) -> tuple[list[str], list[dict]]:
    """Watcha /people/ 링크에서 감독 목록, 출연진 목록 반환."""
    directors: list[str] = []
    cast: list[dict] = []
    try:
        links = page.query_selector_all("a")
        for link in links:
            href = link.get_attribute("href") or ""
            if "/people/" not in href:
                continue
            text = (link.text_content() or "").strip()
            if not text:
                continue
            for role in ROLE_LABELS:
                if role in text:
                    idx = text.index(role)
                    name = text[:idx].strip()
                    remainder = text[idx + len(role):].strip().lstrip("|").strip()
                    if not name:
                        break
                    if role in DIRECTOR_LABELS:
                        directors.append(name)
                    else:
                        cast.append({"name": name, "character": remainder})
                    break
    except Exception as e:
        logger.debug(f"extract_people error: {e}")
    return directors, cast[:15]


def extract_metadata(page, url: str) -> Optional[dict]:
    """
    Playwright 페이지에서 메타데이터 추출.
    필수 필드: title, year, synopsis, poster_url
    """
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        time.sleep(random.uniform(1, 2))

        # og:title (예: "도화년 (2024) - 왓챠피디아")
        og_title = None
        title = None
        year_from_title = None
        try:
            title_elem = page.query_selector('meta[property="og:title"]')
            if title_elem:
                og_title = title_elem.get_attribute("content")
        except Exception:
            pass

        if og_title:
            year_match = re.search(r"\((\d{4})\)", og_title)
            if year_match:
                year_from_title = year_match.group(1)
            t = re.sub(r"\s*-\s*왓챠피디아\s*$", "", og_title)
            t = re.sub(r"\s*\(\d{4}\)\s*$", "", t)
            title = t.strip()

        if not title:
            try:
                h1 = page.query_selector("h1")
                if h1:
                    title = h1.text_content().strip()
            except Exception:
                pass

        # og:image (포스터)
        poster_url = None
        try:
            poster_elem = page.query_selector('meta[property="og:image"]')
            if poster_elem:
                poster_url = poster_elem.get_attribute("content")
        except Exception:
            pass

        # og:description (시놉시스)
        synopsis = None
        try:
            desc_elem = page.query_selector('meta[name="description"]')
            if desc_elem:
                synopsis = desc_elem.get_attribute("content")
        except Exception:
            pass

        if not synopsis:
            try:
                p_elems = page.query_selector_all("p")
                for p in p_elems:
                    text = p.text_content().strip()
                    if len(text) > 100 and ("뉴욕" in text or "영화" in text or "드라마" in text):
                        synopsis = text[:500]
                        break
            except Exception:
                pass

        year = None
        genres = None
        country = None
        runtime = None
        rating_age = None

        try:
            info_text = page.locator("body").text_content()

            if year_from_title:
                year = year_from_title
            else:
                year_match = re.search(r"(19|20)\d{2}", info_text)
                if year_match:
                    year = year_match.group(0)

            genres_match = re.search(r"·\s*([가-힣/]+(?:/[가-힣]+)*)", info_text)
            if genres_match:
                genres = genres_match.group(1)

            country_match = re.search(
                r"·\s*(미국|한국|일본|중국|영국|프랑스|독일|스페인|이탈리아|캐나다|호주|인도|러시아|멕시코|브라질|태국|홍콩|대만)",
                info_text,
            )
            if country_match:
                country = country_match.group(1)

            runtime_match = re.search(r"(\d+시간\s*\d+분|\d+분)", info_text)
            if runtime_match:
                runtime = runtime_match.group(1)

            rating_match = re.search(
                r"(전체관람가|12세|15세|19세|청소년관람불가|R등급|PG-\d+)", info_text
            )
            if rating_match:
                rating_age = rating_match.group(1)
        except Exception:
            pass

        if not title or not year or not synopsis or not poster_url:
            logger.warning(
                f"Missing required fields: title={bool(title)}, year={bool(year)}, "
                f"synopsis={bool(synopsis)}, poster_url={bool(poster_url)}"
            )
            return None

        # 감독·출연 추출 (실패해도 다른 필드에 영향 없음)
        directors, cast = extract_people(page)

        return {
            "title": title[:200],
            "year": year,
            "genres": genres or "",
            "country": country or "",
            "runtime": runtime or "",
            "rating_age": rating_age or "",
            "synopsis": synopsis[:500],
            "poster_url": poster_url,
            "directors": json.dumps(directors, ensure_ascii=False) if directors else "",
            "cast": json.dumps(cast, ensure_ascii=False) if cast else "",
        }

    except Exception as e:
        logger.error(f"Error crawling {url}: {e}")
        return None


def crawl_details(limit: Optional[int] = None):
    """list_real.csv → detail_real.csv + fail_log.csv (전체 크롤)"""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    existing_slugs: set[str] = set()
    if OUTPUT_CSV.exists():
        with open(OUTPUT_CSV) as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_slugs.add(row["slug"])
        logger.info(f"Found {len(existing_slugs)} existing records. Will append new ones.")

    success_count = 0
    fail_count = 0
    fail_rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=UA)

        with open(INPUT_CSV) as f:
            rows = list(csv.DictReader(f))

        if limit:
            rows = rows[:limit]

        logger.info(f"Total URLs to crawl: {len(rows)}")

        for i, row in enumerate(rows):
            slug = row["slug"]
            url = row["url"]
            category = row["category"]

            if slug in existing_slugs:
                logger.info(f"[{i+1}/{len(rows)}] {slug} (skip: already exists)")
                continue

            logger.info(f"[{i+1}/{len(rows)}] Crawling {slug}...")

            meta = extract_metadata(page, url)

            if meta:
                meta["slug"] = slug
                meta["url"] = url
                meta["content_type"] = category
                meta["fetched_at"] = datetime.now().isoformat()

                mode = "a" if OUTPUT_CSV.exists() else "w"
                with open(OUTPUT_CSV, mode, newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
                    if mode == "w":
                        writer.writeheader()
                    writer.writerow(meta)

                success_count += 1
                logger.info(f"  ✓ {slug}")
            else:
                fail_rows.append({"slug": slug, "url": url, "error": "missing_required_fields"})
                fail_count += 1
                logger.warning(f"  ✗ {slug}: missing required fields")

            if (i + 1) % 50 == 0:
                logger.info("Pausing after 50 requests...")
                time.sleep(10)
            else:
                time.sleep(random.uniform(2, 4))

        browser.close()

    if fail_rows:
        with open(FAIL_LOG, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["slug", "url", "error"])
            writer.writeheader()
            writer.writerows(fail_rows)

    logger.info(f"=== Complete === Success: {success_count}, Failed: {fail_count}")


def patch_cast_directors(limit: Optional[int] = None):
    """기존 detail_real.csv에서 cast/directors 미수집 행만 재크롤하여 patch."""
    if not OUTPUT_CSV.exists():
        logger.error("detail_real.csv 없음 — 먼저 full crawl 실행")
        return

    # 백업
    bak = DATA_DIR / "detail_real.csv.v2bak"
    shutil.copy2(OUTPUT_CSV, bak)
    logger.info(f"백업: {bak}")

    with open(OUTPUT_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # cast/directors 없는 행 필터
    needs_patch = [
        r for r in rows
        if not r.get("cast") and not r.get("directors")
    ]
    if limit:
        needs_patch = needs_patch[:limit]

    logger.info(f"patch 대상: {len(needs_patch)}/{len(rows)}건")

    slug_to_row: dict[str, dict] = {r["slug"]: r for r in rows}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=UA)

        for i, row in enumerate(needs_patch):
            slug = row["slug"]
            url = row["url"]
            logger.info(f"[{i+1}/{len(needs_patch)}] patch {slug}...")

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(2000)
                directors, cast = extract_people(page)

                slug_to_row[slug]["directors"] = (
                    json.dumps(directors, ensure_ascii=False) if directors else ""
                )
                slug_to_row[slug]["cast"] = (
                    json.dumps(cast, ensure_ascii=False) if cast else ""
                )
                logger.info(f"  ✓ {slug} — directors: {len(directors)}, cast: {len(cast)}")
            except Exception as e:
                logger.warning(f"  ✗ {slug}: {e}")

            if (i + 1) % 50 == 0:
                time.sleep(10)
            else:
                time.sleep(random.uniform(2, 3))

        browser.close()

    # 전체 저장 (12열)
    all_rows = list(slug_to_row.values())
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)

    patched = sum(1 for r in all_rows if r.get("cast") or r.get("directors"))
    logger.info(f"=== patch 완료 === 총 {len(all_rows)}건 중 cast/directors 보유: {patched}건")


def main():
    parser = argparse.ArgumentParser(description="Watcha Pedia 상세 메타데이터 크롤러")
    parser.add_argument("--patch", action="store_true", help="cast/directors 미수집 행만 재크롤")
    parser.add_argument("--limit", type=int, default=None, help="처음 N건만 처리")
    args = parser.parse_args()

    if args.patch:
        logger.info("=== patch mode ===")
        patch_cast_directors(limit=args.limit)
    else:
        logger.info("=== Step 1.3: Detail Crawler ===")
        crawl_details(limit=args.limit)


if __name__ == "__main__":
    main()
