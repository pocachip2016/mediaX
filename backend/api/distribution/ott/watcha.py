import logging
import re

import requests
from bs4 import BeautifulSoup, Tag

from .base import OttItem, OttSection, OttSource

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_CATEGORY_TYPE_MAP = {
    "top": "ranking",
    "rank": "ranking",
    "신작": "recommendation",
    "new": "recommendation",
    "추천": "recommendation",
    "genre": "genre",
    "장르": "genre",
}


def _infer_category_type(section_name: str) -> str:
    name_lower = section_name.lower()
    for keyword, ctype in _CATEGORY_TYPE_MAP.items():
        if keyword in name_lower:
            return ctype
    return "recommendation"


def _extract_items_from_anchor_group(anchors: list[Tag], limit: int) -> list[OttItem]:
    seen: set[str] = set()
    items: list[OttItem] = []
    for anchor in anchors:
        href = anchor.get("href", "")
        if "/contents/" not in href:
            continue
        slug = href.rstrip("/").split("/")[-1]
        if not slug or slug in seen:
            continue
        seen.add(slug)
        year_match = re.search(r"\b(19|20)\d{2}\b", anchor.get_text())
        year = int(year_match.group()) if year_match else None
        items.append(OttItem(
            title=anchor.get_text(strip=True) or slug,
            rank=len(items) + 1,
            production_year=year,
            external_id=slug,
            raw={"href": href, "slug": slug},
        ))
        if len(items) >= limit:
            break
    return items


class WatchaTopSource(OttSource):
    channel = "ott_watcha"
    URL = "https://pedia.watcha.com/ko?domain=movie"

    def _get_soup(self) -> BeautifulSoup | None:
        try:
            resp = requests.get(self.URL, headers={"User-Agent": _UA}, timeout=10)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except Exception:
            logger.warning("WatchaTopSource: HTTP 실패")
            return None

    def fetch_top(self, limit: int = 20) -> list[OttItem]:
        """SSR HTML → a[href^="/ko/contents/"] 카드 → OttItem 리스트. 실패 시 []."""
        soup = self._get_soup()
        if soup is None:
            return []
        try:
            anchors = soup.select('a[href^="/ko/contents/"]')
            return _extract_items_from_anchor_group(anchors, limit)
        except Exception:
            logger.exception("WatchaTopSource: 파싱 실패")
            return []

    def fetch_sections(self) -> list[OttSection]:
        """Watcha 홈의 섹션 헤딩 + 콘텐츠 카드를 파싱해 multi-section 반환.
        섹션 헤딩을 찾지 못하면 단일 TOP 섹션으로 폴백."""
        soup = self._get_soup()
        if soup is None:
            return []
        try:
            return self._parse_sections(soup)
        except Exception:
            logger.exception("WatchaTopSource.fetch_sections: 파싱 실패 — 단일 TOP 폴백")
            return super().fetch_sections()

    def _parse_sections(self, soup: BeautifulSoup) -> list[OttSection]:
        """섹션 컨테이너(section, article, div[data-section])를 순회해 OttSection 리스트 반환."""
        sections: list[OttSection] = []

        # 헤딩(h2/h3) + 그 아래 콘텐츠 앵커 패턴으로 섹션 분리 시도
        headings = soup.find_all(["h2", "h3"])
        for heading in headings:
            name = heading.get_text(strip=True)
            if not name or len(name) < 2:
                continue

            # 헤딩 이후 첫 번째 콘텐츠 그룹 수집 (형제 또는 부모 컨테이너)
            container = heading.find_parent(["section", "article", "div"])
            if container is None:
                continue
            anchors = container.select('a[href*="/contents/"]')
            items = _extract_items_from_anchor_group(anchors, limit=20)
            if not items:
                continue

            section_id = f"{self.channel}:{re.sub(r'\\W+', '_', name.lower())[:40]}"
            sections.append(OttSection(
                section_id=section_id,
                name=name,
                category_type=_infer_category_type(name),
                items=items,
            ))

        if not sections:
            # 헤딩 없는 경우 전체 앵커를 단일 TOP 섹션으로
            anchors = soup.select('a[href^="/ko/contents/"]')
            items = _extract_items_from_anchor_group(anchors, limit=20)
            if items:
                sections.append(OttSection(
                    section_id=f"{self.channel}:top",
                    name="TOP",
                    category_type="ranking",
                    items=items,
                ))

        return sections
