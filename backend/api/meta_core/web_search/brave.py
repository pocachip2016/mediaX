import logging
import httpx

from shared.config import settings
from shared.quota_manager import QuotaManager
from api.meta_core.web_search.base import WebSearchProvider, WebSearchResult
from api.meta_core.web_search.errors import QuotaExhaustedError, ProviderUnavailableError

logger = logging.getLogger(__name__)


class BraveSearchProvider(WebSearchProvider):
    """Brave Search API provider."""

    def __init__(self, quota_manager: QuotaManager | None = None):
        self._api_key = settings.BRAVE_SEARCH_API_KEY
        self._quota_manager = quota_manager or QuotaManager()

    @property
    def provider_name(self) -> str:
        return "brave"

    @property
    def daily_limit(self) -> int:
        return settings.WEBSEARCH_BRAVE_DAILY

    async def search(self, query: str, num: int = 8) -> list[WebSearchResult]:
        """
        Search using Brave Search API.

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
                    "https://api.search.brave.com/res/v1/web/search",
                    headers={
                        "Accept": "application/json",
                        "X-Subscription-Token": self._api_key,
                    },
                    params={
                        "q": query,
                        "count": num,
                        "country": "kr",  # Korea preferred
                    },
                )
                resp.raise_for_status()

            data = resp.json()
            results_raw = data.get("web", {}).get("results", [])

            results = []
            for r in results_raw:
                # Map Brave response to WebSearchResult
                result = WebSearchResult(
                    url=r.get("url", ""),
                    title=r.get("title", ""),
                    snippet=r.get("description", ""),
                    source_domain=_extract_domain(r.get("url", "")),
                    score=1.0,  # Brave doesn't provide relevance score
                )
                results.append(result)

            logger.info(f"[{self.provider_name}] {len(results)} results for query={query[:30]}")
            return results

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Rate limited — mark as exhausted
                remaining = self.daily_limit - self._quota_manager.current_count(quota_key)
                raise QuotaExhaustedError(self.provider_name, remaining)
            raise ProviderUnavailableError(self.provider_name, f"HTTP {e.response.status_code}")
        except Exception as e:
            logger.exception(f"[{self.provider_name}] search failed: {e}")
            raise ProviderUnavailableError(self.provider_name, str(e))


def _extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        # Remove protocol
        if "://" in url:
            url = url.split("://", 1)[1]
        # Take first part (subdomain.domain.tld → just domain part)
        domain = url.split("/")[0]
        # Remove www. prefix
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""
