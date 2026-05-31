"""
Wikipedia MediaWiki API 클라이언트 — 동기 httpx

공식 API(action=query) 사용 → ToS 적합. CC BY-SA 라이선스.
줄거리는 원문 복사 금지 → 텍스트를 반환만 하고,
호출부(reference_extract)에서 LLM 요약 후 저장.

사용 예:
    client = WikipediaClient()
    result = client.fetch("기생충 영화")
    # → {"text": "기생충(Parasite)는 ...", "url": "https://ko.wikipedia.org/wiki/기생충_(영화)"}

키 불필요. 실패 시 None 반환.
"""
import logging

import httpx

logger = logging.getLogger(__name__)

_UA = "mediaX-metadata-bot/1.0 (VOD metadata enrichment)"
_LANGS = ["ko", "en"]


class WikipediaClient:
    def __init__(self, timeout: float = 10.0):
        self._timeout = timeout

    def _api(self, lang: str) -> str:
        return f"https://{lang}.wikipedia.org/w/api.php"

    def _get(self, lang: str, params: dict) -> dict:
        try:
            resp = httpx.get(
                self._api(lang),
                params={"format": "json", **params},
                headers={"User-Agent": _UA},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("[wikipedia] HTTP error lang=%s: %s", lang, exc)
            return {}

    def fetch(self, query: str, max_chars: int = 3000) -> dict | None:
        """제목 검색 → intro 텍스트 + 페이지 URL 반환. 미발견 시 None.

        max_chars: LLM 토큰 절약을 위해 intro를 제한 (기본 3000자).
        """
        for lang in _LANGS:
            result = self._fetch_lang(lang, query, max_chars)
            if result:
                return result
        return None

    def _fetch_lang(self, lang: str, query: str, max_chars: int) -> dict | None:
        # 1. 제목 검색
        search_data = self._get(lang, {
            "action": "query", "list": "search",
            "srsearch": query, "srlimit": 3,
        })
        hits = (search_data.get("query") or {}).get("search") or []
        if not hits:
            return None

        page_title = hits[0]["title"]

        # 2. intro 텍스트 추출 (extracts prop — HTML 아닌 plaintext)
        extract_data = self._get(lang, {
            "action": "query", "prop": "extracts|info",
            "exintro": True, "explaintext": True, "inprop": "url",
            "titles": page_title, "redirects": True,
        })
        pages = (extract_data.get("query") or {}).get("pages") or {}
        page = next(iter(pages.values()), {})
        text = (page.get("extract") or "").strip()
        url = page.get("fullurl") or f"https://{lang}.wikipedia.org/wiki/{page_title.replace(' ', '_')}"

        if not text:
            return None

        return {"text": text[:max_chars], "url": url, "lang": lang}
