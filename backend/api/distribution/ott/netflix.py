import csv
import io
import logging

import requests

from .base import OttItem, OttSource

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class NetflixTudumSource(OttSource):
    channel = "ott_netflix"
    URL = "https://www.netflix.com/tudum/top10/data/all-weeks-countries.tsv"

    def fetch_top(self, limit: int = 20) -> list[OttItem]:
        """Netflix Tudum 공식 TSV → KR 최신 week Top N → OttItem 리스트. 실패 시 []."""
        try:
            resp = requests.get(
                self.URL,
                headers={"User-Agent": _UA},
                timeout=10,
            )
            resp.raise_for_status()
        except Exception:
            logger.warning("NetflixTudumSource: HTTP 실패")
            return []

        try:
            reader = csv.DictReader(io.StringIO(resp.text), delimiter="\t")
            rows = list(reader)
        except Exception:
            logger.exception("NetflixTudumSource: TSV 파싱 실패")
            return []

        # KR 필터 + 최신 week 선택
        kr_rows = [r for r in rows if r.get("country_iso2", "").strip().upper() == "KR"]
        if not kr_rows:
            return []

        latest_week = max(r.get("week", "") for r in kr_rows)
        week_rows = [r for r in kr_rows if r.get("week", "") == latest_week]

        items: list[OttItem] = []
        try:
            for row in sorted(week_rows, key=lambda r: int(r.get("rank", 9999))):
                rank = int(row.get("rank", len(items) + 1))
                title = row.get("show_title", "").strip()
                if not title:
                    continue
                category = row.get("category", "").strip()
                external_id = f"{latest_week}:{category}:{rank}"
                score = max(0.0, 1.0 - (rank - 1) * 0.1)
                items.append(
                    OttItem(
                        title=title,
                        rank=rank,
                        production_year=None,
                        external_id=external_id,
                        raw={
                            "week": latest_week,
                            "category": category,
                            "rank": rank,
                        },
                    )
                )
                if len(items) >= limit:
                    break
        except Exception:
            logger.exception("NetflixTudumSource: row 처리 실패")
            return []

        return items
