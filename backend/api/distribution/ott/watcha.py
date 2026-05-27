import logging

import requests
from bs4 import BeautifulSoup

from .base import OttItem, OttSource

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class WatchaTopSource(OttSource):
    channel = "ott_watcha"
    URL = "https://pedia.watcha.com/ko?domain=movie"

    def fetch_top(self, limit: int = 20) -> list[OttItem]:
        """SSR HTML → a[href^="/ko/contents/"] 카드 → OttItem 리스트. 실패 시 []."""
        try:
            resp = requests.get(
                self.URL,
                headers={"User-Agent": _UA},
                timeout=10,
            )
            resp.raise_for_status()
        except Exception:
            logger.warning("WatchaTopSource: HTTP 실패")
            return []

        try:
            soup = BeautifulSoup(resp.text, "html.parser")
            anchors = soup.select('a[href^="/ko/contents/"]')
            seen: set[str] = set()
            items: list[OttItem] = []
            for anchor in anchors:
                href = anchor.get("href", "")
                slug = href.rstrip("/").split("/")[-1]
                if not slug or slug in seen:
                    continue
                seen.add(slug)
                rank = len(items) + 1
                items.append(
                    OttItem(
                        title=anchor.get_text(strip=True) or slug,
                        rank=rank,
                        production_year=None,
                        external_id=slug,
                        raw={"href": href, "slug": slug},
                    )
                )
                if len(items) >= limit:
                    break
        except Exception:
            logger.exception("WatchaTopSource: 파싱 실패")
            return []

        return items
