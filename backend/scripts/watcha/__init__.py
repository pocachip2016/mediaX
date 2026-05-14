# Watcha sampling scripts — dev/validation only, not production code.
# Data collected here is for fakeDB seeding and will be deleted after verification.
#
# Usage order:
#   01_discover_categories.py  → data/watcha/categories.json
#   02_crawl_lists.py          → data/watcha/list.csv
#   03_crawl_details.py        → data/watcha/detail.csv
#   04_download_posters.py     → data/watcha/detail_final.csv + posters/
#   05_bulk_insert.py          → ExternalMetaSource + content_seeds DB rows
#   06_cross_verify.py         → data/watcha/verify_report.md
#   07_ai_fallback_test.py     → data/watcha/fallback_test_report.md

import os
import random
import time


def random_delay(min_sec: float = None, max_sec: float = None) -> None:
    """Sleep for a random interval to stay polite with Watcha servers."""
    lo = min_sec or float(os.getenv("WATCHA_MIN_INTERVAL", "3.0"))
    hi = max_sec or float(os.getenv("WATCHA_MAX_INTERVAL", "4.0"))
    time.sleep(random.uniform(lo, hi))


USER_AGENT = os.getenv(
    "WATCHA_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36",
)
