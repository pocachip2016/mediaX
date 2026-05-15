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
            async with httpx.AsyncClient(timeout=10.0) as client:
                # DuckDuckGo HTML endpoint
                resp = await client.get(
                    "https://html.duckduckgo.com/",
                    params={"q": query, "dl": "ko"},  # Korean preference
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
                )
                resp.raise_for_status()

            # Parse HTML results
            parser = DDGResultParser()
            parser.feed(resp.text)
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
    """Parse DuckDuckGo HTML results."""

    def __init__(self):
        super().__init__()
        self.results: list[WebSearchResult] = []
        self.in_result = False
        self.current_url = ""
        self.current_title = ""
        self.current_snippet = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        # DuckDuckGo result container
        if tag == "div" and attrs_dict.get("class") == "result":
            self.in_result = True

        # Extract URL from result link
        if self.in_result and tag == "a" and "result__a" in attrs_dict.get("class", ""):
            self.current_url = attrs_dict.get("href", "")

        # Extract title
        if self.in_result and tag == "span" and "result__title" in attrs_dict.get("class", ""):
            self.in_title = True

        # Extract snippet
        if (
            self.in_result
            and tag == "a"
            and "result__snippet" in attrs_dict.get("class", "")
        ):
            self.in_snippet = True

    def handle_data(self, data):
        if self.in_result:
            if hasattr(self, "in_title") and self.in_title:
                self.current_title += data.strip()
            if hasattr(self, "in_snippet") and self.in_snippet:
                self.current_snippet += data.strip()

    def handle_endtag(self, tag):
        if tag == "div" and self.in_result:
            # End of result container
            if self.current_url and self.current_title:
                result = WebSearchResult(
                    url=self.current_url,
                    title=self.current_title,
                    snippet=self.current_snippet,
                    source_domain=_extract_domain(self.current_url),
                    score=1.0,
                )
                self.results.append(result)

            self.in_result = False
            self.current_url = ""
            self.current_title = ""
            self.current_snippet = ""
            self.in_title = False
            self.in_snippet = False

        elif tag == "span" and hasattr(self, "in_title"):
            self.in_title = False
        elif tag == "a" and hasattr(self, "in_snippet"):
            self.in_snippet = False


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
