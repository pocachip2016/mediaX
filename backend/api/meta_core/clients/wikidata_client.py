"""
Wikidata API 클라이언트 — 구조화 fact 조회 (동기 httpx)

영화/시리즈의 사실형 메타(감독/출연/국가/장르/러닝타임/제작연도)를 구조화 claim에서 추출.
Wikidata 콘텐츠는 CC0(저작권 포기) — 사실 데이터라 저작권/추출 이슈 없음.

사용 예:
    client = WikidataClient()
    facts = client.fetch_facts("기생충", year=2019)
    # → {"directors": ["봉준호"], "country": "대한민국", "production_year": 2019,
    #    "runtime": 132, "genres": [...], "cast": [...],
    #    "_url": "https://www.wikidata.org/wiki/Q496243"}

키 불필요. 네트워크 실패 시 빈 dict 반환(호출부 skip).
"""
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_API = "https://www.wikidata.org/w/api.php"
_UA = "mediaX-metadata-bot/1.0 (VOD metadata enrichment)"

# entity-값 property → 표준 필드명
_ENTITY_PROPS: dict[str, str] = {
    "P57":  "directors",  # director
    "P161": "cast",       # cast member
    "P495": "country",    # country of origin
    "P136": "genres",     # genre
}
_P_RUNTIME = "P2047"  # duration (minutes)
_P_PUBDATE = "P577"   # publication date


class WikidataClient:
    def __init__(self, timeout: float = 10.0):
        self._timeout = timeout

    def _get(self, params: dict) -> dict:
        try:
            resp = httpx.get(
                _API,
                params={"format": "json", **params},
                headers={"User-Agent": _UA},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("[wikidata] HTTP error: %s", exc)
            return {}

    def search_entity(self, title: str) -> str | None:
        """제목으로 엔티티 검색 → 첫 Q-id 반환 (ko 우선, 실패 시 en)."""
        for lang in ("ko", "en"):
            data = self._get({
                "action": "wbsearchentities", "search": title,
                "language": lang, "type": "item", "limit": 5,
            })
            hits = data.get("search") or []
            if hits:
                return hits[0].get("id")
        return None

    def fetch_facts(self, title: str, year: int | None = None) -> dict[str, Any]:
        """제목(+연도)로 구조화 fact dict 반환. 미발견 시 {} 반환.

        반환 키: directors/cast/country/genres/runtime/production_year/_url
        """
        qid = self.search_entity(title)
        if not qid:
            return {}

        data = self._get({
            "action": "wbgetentities", "ids": qid,
            "props": "claims", "languages": "ko|en",
        })
        entity = (data.get("entities") or {}).get(qid)
        if not entity:
            return {}
        claims = entity.get("claims") or {}

        entity_field_map: dict[str, list[str]] = {}
        entity_ids_to_resolve: set[str] = set()

        for prop, field in _ENTITY_PROPS.items():
            qids = _entity_ids(claims.get(prop) or [])
            if qids:
                entity_field_map[field] = qids
                entity_ids_to_resolve.update(qids)

        facts: dict[str, Any] = {}

        runtime = _quantity_int(claims.get(_P_RUNTIME) or [])
        if runtime:
            facts["runtime"] = runtime

        pub_year = _time_year(claims.get(_P_PUBDATE) or [])
        if pub_year:
            facts["production_year"] = pub_year

        labels = self._resolve_labels(entity_ids_to_resolve)
        for field, qids in entity_field_map.items():
            names = [labels[q] for q in qids if q in labels]
            if not names:
                continue
            if field == "country":
                facts["country"] = names[0]
            elif field == "cast":
                facts["cast"] = names[:10]
            else:
                facts[field] = names  # directors, genres

        if facts:
            facts["_url"] = f"https://www.wikidata.org/wiki/{qid}"
        return facts

    def _resolve_labels(self, qids: set[str]) -> dict[str, str]:
        """Q-id 집합 → 라벨(ko 우선 en) 매핑. 50개 단위 batch."""
        labels: dict[str, str] = {}
        ids = list(qids)
        for i in range(0, len(ids), 50):
            batch = ids[i:i + 50]
            data = self._get({
                "action": "wbgetentities", "ids": "|".join(batch),
                "props": "labels", "languages": "ko|en",
            })
            for q, ent in (data.get("entities") or {}).items():
                lbls = ent.get("labels") or {}
                lab = (lbls.get("ko") or lbls.get("en") or {}).get("value")
                if lab:
                    labels[q] = lab
        return labels


# ── claim 파싱 헬퍼 ──────────────────────────────────────────────────────────

def _entity_ids(claim_list: list) -> list[str]:
    out: list[str] = []
    for c in claim_list:
        try:
            dv = c["mainsnak"]["datavalue"]["value"]
            if isinstance(dv, dict) and dv.get("id"):
                out.append(dv["id"])
        except (KeyError, TypeError):
            continue
    return out


def _quantity_int(claim_list: list) -> int | None:
    for c in claim_list:
        try:
            amount = c["mainsnak"]["datavalue"]["value"]["amount"]
            return int(float(amount))
        except (KeyError, TypeError, ValueError):
            continue
    return None


def _time_year(claim_list: list) -> int | None:
    for c in claim_list:
        try:
            t = c["mainsnak"]["datavalue"]["value"]["time"]  # "+2019-05-30T00:00:00Z"
            return int(t.lstrip("+")[:4])
        except (KeyError, TypeError, ValueError):
            continue
    return None
