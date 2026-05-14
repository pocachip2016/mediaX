#!/usr/bin/env python3
"""
Step 1.0: Discover Watcha categories (2depth: 영화/시리즈 × 장르).

Output: backend/data/watcha/categories.json
  [
    {"depth1": "영화", "depth2": "SF", "url": "...", "slug": "..."},
    ...
  ]
"""

import json
import logging
import random
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "watcha"
MIN_INTERVAL = 3.0
MAX_INTERVAL = 4.0


def extract_categories_from_page(page, depth1: str, limit: int = 10) -> list[dict]:
    """Extract genre/category links from Watcha page via page.content()."""
    categories = []
    page.wait_for_load_state("domcontentloaded", timeout=20000)
    time.sleep(random.uniform(MIN_INTERVAL, MAX_INTERVAL))

    try:
        # Get all links on the page
        all_links = page.query_selector_all("a")
        logger.info(f"Found {len(all_links)} total links on {depth1} page")

        seen = set()
        genre_keywords = ["장르", "genre", "category", "tag", "필터", "filter"]

        for link in all_links:
            href = link.get_attribute("href")
            text = link.inner_text().strip()

            if not href or not text or len(text) > 50 or text in seen:
                continue

            # Filter for likely genre/category links
            href_lower = href.lower()
            text_lower = text.lower()
            is_genre = any(kw in href_lower for kw in ["genre", "tag", "filter"]) or len(text) < 20

            if not is_genre and not any(kw in text_lower for kw in genre_keywords):
                continue

            seen.add(text)

            # Normalize URL
            if not href.startswith("http"):
                href = "https://watcha.com" + (href if href.startswith("/") else "/" + href)

            slug = text.lower().replace(" ", "-").replace("&", "and").replace("/", "-")

            categories.append({
                "depth1": depth1,
                "depth2": text,
                "url": href,
                "slug": slug,
            })

            if len(categories) >= limit:
                break

        # If still not enough, use fallback list
        if len(categories) < limit:
            logger.warning(f"Only found {len(categories)} categories, using fallback")
            categories.extend(_get_fallback_categories(depth1, limit - len(categories)))

    except Exception as e:
        logger.warning(f"Error extracting categories: {e}")
        categories.extend(_get_fallback_categories(depth1, limit))

    return categories[:limit]


def _get_fallback_categories(depth1: str, limit: int = 10) -> list[dict]:
    """Fallback: known Watcha categories (update URL patterns as needed)."""
    fallback = {
        "영화": [
            {"depth2": "SF", "slug": "sf"},
            {"depth2": "액션", "slug": "action"},
            {"depth2": "드라마", "slug": "drama"},
            {"depth2": "코미디", "slug": "comedy"},
            {"depth2": "공포", "slug": "horror"},
            {"depth2": "로맨스", "slug": "romance"},
            {"depth2": "애니메이션", "slug": "animation"},
            {"depth2": "다큐멘터리", "slug": "documentary"},
            {"depth2": "스릴러", "slug": "thriller"},
            {"depth2": "가족", "slug": "family"},
        ],
        "시리즈": [
            {"depth2": "드라마", "slug": "drama"},
            {"depth2": "로맨스", "slug": "romance"},
            {"depth2": "코미디", "slug": "comedy"},
            {"depth2": "액션", "slug": "action"},
            {"depth2": "미스터리", "slug": "mystery"},
            {"depth2": "스릴러", "slug": "thriller"},
            {"depth2": "판타지", "slug": "fantasy"},
            {"depth2": "공포", "slug": "horror"},
            {"depth2": "애니메이션", "slug": "animation"},
            {"depth2": "다큐멘터리", "slug": "documentary"},
        ],
    }

    result = []
    for cat in fallback.get(depth1, [])[:limit]:
        result.append({
            "depth1": depth1,
            "depth2": cat["depth2"],
            "url": f"https://watcha.com/browse?genre={cat['slug']}&type={'movie' if depth1 == '영화' else 'series'}",
            "slug": cat["slug"],
        })
    return result


def discover_categories() -> list[dict]:
    """Main: discover all categories (영화/시리즈 × 10 genres each)."""
    all_categories = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)

        # Movie categories
        logger.info("Discovering movie categories...")
        page = context.new_page()
        try:
            page.goto("https://watcha.com/browse?type=movie", wait_until="load", timeout=30000)
            movie_cats = extract_categories_from_page(page, "영화", limit=10)
            logger.info(f"Found {len(movie_cats)} movie categories")
            all_categories.extend(movie_cats)
        except Exception as e:
            logger.error(f"Failed to fetch movie categories: {e}")
        finally:
            page.close()

        time.sleep(random.uniform(MIN_INTERVAL, MAX_INTERVAL))

        # Series categories
        logger.info("Discovering series categories...")
        page = context.new_page()
        try:
            page.goto("https://watcha.com/browse?type=series", wait_until="load", timeout=30000)
            series_cats = extract_categories_from_page(page, "시리즈", limit=10)
            logger.info(f"Found {len(series_cats)} series categories")
            all_categories.extend(series_cats)
        except Exception as e:
            logger.error(f"Failed to fetch series categories: {e}")
        finally:
            page.close()

        browser.close()

    return all_categories


def main():
    logger.info("=== Step 1.0: category-discovery ===")

    categories = discover_categories()

    if not categories:
        logger.error("No categories found!")
        return False

    logger.info(f"Discovered {len(categories)} total categories")

    # Save to JSON
    output_file = DATA_DIR / "categories.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(categories, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved {len(categories)} categories to {output_file}")

    # Print summary
    movie_count = sum(1 for c in categories if c["depth1"] == "영화")
    series_count = sum(1 for c in categories if c["depth1"] == "시리즈")
    print(f"\n✓ Categories discovered:")
    print(f"  영화: {movie_count}")
    print(f"  시리즈: {series_count}")
    print(f"  Total: {len(categories)}")

    return len(categories) >= 20


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
