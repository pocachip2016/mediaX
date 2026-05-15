import logging
import httpx

from shared.config import settings
from shared.quota_manager import QuotaManager
from api.meta_core.web_search.base import WebSearchProvider, WebSearchResult
from api.meta_core.web_search.errors import QuotaExhaustedError, ProviderUnavailableError

logger = logging.getLogger(__name__)


class SerpApiProvider(WebSearchProvider):
    """SerpAPI (Serper) search provider."""

    def __init__(self, quota_manager: QuotaManager | None = None):
        self._api_key = settings.SERPAPI_KEY
        self._quota_manager = quota_manager or QuotaManager()

    @property
    def provider_name(self) -> str:
        return "serpapi"

    @property
    def daily_limit(self) -> int:
        return settings.WEBSEARCH_SERPAPI_DAILY

    async def search(self, query: str, num: int = 8) -> list[WebSearchResult]:
        """
        Search using SerpAPI (Serper).

        Raises:
            QuotaExhaustedError: Daily limit exceeded
            ProviderUnavailableError: API error
        """
        if not self._api_key:
            raise ProviderUnavailableError(self.provider_name, "API key not configured")

        # Check quota before calling
        quota_key = f"websearch:{self.provider_name}"
        if not self._quota_manager.is_allowed(quota_key, self.daily_limit):
            remaining = self.daily_limit - self._quota_manager.current_count(quota_key)
            raise QuotaExhaustedError(self.provider_name, remaining)

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://google.serper.dev/search",
                    headers={
                        "X-API-KEY": self._api_key,
                        "Content-Type": "application/json",
                    },
                    params={
                        "q": query,
                        "gl": "kr",  # Korea
                        "hl": "ko",  # Korean language
                        "num": num,
                    },
                )
                resp.raise_for_status()

            data = resp.json()
            results_raw = data.get("organic", [])

            results = []
            for r in results_raw[:num]:
                # Map Serper response to WebSearchResult
                result = WebSearchResult(
                    url=r.get("link", ""),
                    title=r.get("title", ""),
                    snippet=r.get("snippet", ""),
                    source_domain=_extract_domain(r.get("link", "")),
                    score=1.0,
                )
                results.append(result)

            logger.info(f"[{self.provider_name}] {len(results)} results for query={query[:30]}")
            return results

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                remaining = self.daily_limit - self._quota_manager.current_count(quota_key)
                raise QuotaExhaustedError(self.provider_name, remaining)
            raise ProviderUnavailableError(self.provider_name, f"HTTP {e.response.status_code}")
        except Exception as e:
            logger.exception(f"[{self.provider_name}] search failed: {e}")
            raise ProviderUnavailableError(self.provider_name, str(e))


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
