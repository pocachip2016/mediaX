import logging
import httpx
from html.parser import HTMLParser

from shared.config import settings
from api.meta_core.web_search.base import WebSearchProvider, WebSearchResult
from api.meta_core.web_search.errors import ProviderUnavailableError

logger = logging.getLogger(__name__)


class OllamaDDGProvider(WebSearchProvider):
    """Ollama-backed DuckDuckGo provider — unlimited, local fallback."""

    def __init__(self, quota_manager=None):
        # Ollama has no quota, so quota_manager is unused but accepted for interface compatibility
        pass

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def daily_limit(self) -> int:
        return 999999  # Unlimited

    async def search(self, query: str, num: int = 8) -> list[WebSearchResult]:
        """
        Search using DuckDuckGo HTML scraping + local Ollama summarization.

        No quota limit — infinite fallback. Never raises QuotaExhaustedError.

        Raises:
            ProviderUnavailableError: Network error or Ollama unavailable
        """
        try:
            # Step 1: Fetch from DuckDuckGo (no API key needed)
            results = await self._fetch_from_ddg(query, num)

            # Step 2: Try to summarize using Ollama if available
            # (optional — if Ollama fails, still return raw DDG results)
            for result in results:
                summary = await self._summarize_with_ollama(result.snippet)
                if summary:
                    result.snippet = summary

            logger.info(f"[{self.provider_name}] {len(results)} results for query={query[:30]}")
            return results

        except Exception as e:
            logger.exception(f"[{self.provider_name}] search failed: {e}")
            raise ProviderUnavailableError(self.provider_name, str(e))

    async def _fetch_from_ddg(self, query: str, num: int) -> list[WebSearchResult]:
        """Fetch results from DuckDuckGo HTML."""
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                # DuckDuckGo HTML 검색 엔드포인트는 /html/ (루트는 302 리다이렉트됨).
                # POST form 방식이 봇 차단·리다이렉트에 더 안정적. kl=kr-ko = 한국 지역.
                resp = await client.post(
                    "https://html.duckduckgo.com/html/",
                    data={"q": query, "kl": "kr-ko"},
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )
                resp.raise_for_status()

            # Parse HTML results
            parser = DDGResultParser()
            parser.feed(resp.text)
            parser.close()
            parser.flush()  # 마지막 결과 flush
            results = parser.results[:num]

            return results

        except Exception as e:
            logger.warning(f"[{self.provider_name}] DuckDuckGo fetch failed: {e}")
            raise ProviderUnavailableError(self.provider_name, str(e))

    async def _summarize_with_ollama(self, text: str) -> str | None:
        """Try to summarize snippet using local Ollama (optional)."""
        if not text or len(text) < 10:
            return None

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{settings.OLLAMA_URL}/api/generate",
                    json={
                        "model": settings.OLLAMA_MODEL,
                        "prompt": f"한 문장으로 요약해줘:\n{text[:500]}",
                        "stream": False,
                    },
                )
                resp.raise_for_status()

            data = resp.json()
            summary = data.get("response", "").strip()
            return summary if summary else None

        except Exception as e:
            # Ollama failure is non-fatal for DDG fallback
            logger.debug(f"[{self.provider_name}] Ollama summarization failed: {e}")
            return None


class DDGResultParser(HTMLParser):
    """Parse DuckDuckGo /html/ results.

    구조: <a class="result__a" href="URL">TITLE</a> ... <a class="result__snippet">SNIPPET</a>
    각 result__a(제목 앵커)를 만나면 이전 누적 결과를 flush 후 새 결과 시작.
    """

    def __init__(self):
        super().__init__()
        self.results: list[WebSearchResult] = []
        self.in_title = False
        self.in_snippet = False
        self.current_url = ""
        self.current_title = ""
        self.current_snippet = ""

    def flush(self):
        """누적 중인 결과를 확정해 results에 추가."""
        url = _decode_ddg_url(self.current_url)
        if url and self.current_title:
            self.results.append(WebSearchResult(
                url=url,
                title=self.current_title.strip(),
                snippet=self.current_snippet.strip(),
                source_domain=_extract_domain(url),
                score=1.0,
            ))
        self.current_url = ""
        self.current_title = ""
        self.current_snippet = ""

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        cls = dict(attrs).get("class", "") or ""
        href = dict(attrs).get("href", "") or ""
        if "result__a" in cls:
            # 새 결과 제목 앵커 → 이전 결과 flush 후 시작
            self.flush()
            self.current_url = href
            self.in_title = True
        elif "result__snippet" in cls:
            self.in_snippet = True

    def handle_data(self, data):
        if self.in_title:
            self.current_title += data
        elif self.in_snippet:
            self.current_snippet += data

    def handle_endtag(self, tag):
        if tag == "a":
            self.in_title = False
            self.in_snippet = False


def _decode_ddg_url(href: str) -> str:
    """DDG 리다이렉트 링크(//duckduckgo.com/l/?uddg=...)면 실제 URL 디코드."""
    if not href:
        return ""
    import urllib.parse
    if "uddg=" in href:
        try:
            qs = urllib.parse.urlparse(href if "://" in href else "https:" + href).query
            uddg = urllib.parse.parse_qs(qs).get("uddg", [])
            if uddg:
                return urllib.parse.unquote(uddg[0])
        except Exception:
            pass
    if href.startswith("//"):
        return "https:" + href
    return href


def _extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        if "://" in url:
            url = url.split("://", 1)[1]
        domain = url.split("/")[0]
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""
