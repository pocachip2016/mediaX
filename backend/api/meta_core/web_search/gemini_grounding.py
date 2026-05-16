import logging

from shared.config import settings
from shared.quota_manager import QuotaManager
from api.meta_core.web_search.base import WebSearchProvider, WebSearchResult
from api.meta_core.web_search.errors import QuotaExhaustedError, ProviderUnavailableError

logger = logging.getLogger(__name__)


class GeminiGroundingProvider(WebSearchProvider):
    """Google Gemini with Grounding (web search enabled)."""

    def __init__(self, quota_manager: QuotaManager | None = None):
        self._api_key = settings.GOOGLE_API_KEY
        self._quota_manager = quota_manager or QuotaManager()
        self._client = None

    def _get_client(self):
        """Lazy init Gemini client."""
        if self._client is None:
            if not self._api_key:
                raise ProviderUnavailableError(self.provider_name, "API key not configured")
            try:
                from google import genai
                self._client = genai.Client(api_key=self._api_key)
            except ImportError:
                raise ImportError("google-genai not installed")
        return self._client

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def daily_limit(self) -> int:
        return settings.WEBSEARCH_GEMINI_DAILY

    async def search(self, query: str, num: int = 8) -> list[WebSearchResult]:
        """
        Search using Gemini Grounding (web search).

        Makes a request to Gemini with google_search tool enabled,
        which returns grounded search results.

        Raises:
            QuotaExhaustedError: Daily limit exceeded
            ProviderUnavailableError: API error
        """
        # Check quota before calling
        quota_key = f"websearch:{self.provider_name}"
        if not self._quota_manager.is_allowed(quota_key, self.daily_limit):
            remaining = self.daily_limit - self._quota_manager.current_count(quota_key)
            raise QuotaExhaustedError(self.provider_name, remaining)

        try:
            from google import genai
            from google.genai import types

            client = self._get_client()

            # Prepare tools for Gemini — google_search for web results
            tools = [
                types.Tool(
                    google_search=types.GoogleSearch(),
                )
            ]

            # Call Gemini with grounding enabled
            prompt = f"웹 검색을 통해 다음 쿼리에 대한 최신 정보를 찾아줘: {query}\n결과를 JSON 리스트로 반환해줘. 각 항목은 title, url, snippet을 포함해야 해."

            response = await client.aio.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
                tools=tools,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=2048,
                ),
            )

            # Parse Gemini response — look for search results in the response
            results = _parse_gemini_grounding_response(response, num)

            logger.info(f"[{self.provider_name}] {len(results)} results for query={query[:30]}")
            return results

        except Exception as e:
            logger.exception(f"[{self.provider_name}] search failed: {e}")
            raise ProviderUnavailableError(self.provider_name, str(e))


def _parse_gemini_grounding_response(response, num: int) -> list[WebSearchResult]:
    """
    Parse Gemini grounding response.

    Gemini returns search results in the response text or via tool use.
    This tries to extract search results from the text content.
    """
    results = []

    try:
        import json
        import re

        # Try to extract JSON array from response text
        text = response.text if hasattr(response, 'text') else str(response)

        # Look for JSON array pattern
        json_pattern = r'\[.*\]'
        matches = re.findall(json_pattern, text, re.DOTALL)

        if matches:
            try:
                data = json.loads(matches[0])
                if isinstance(data, list):
                    for item in data[:num]:
                        if isinstance(item, dict):
                            result = WebSearchResult(
                                url=item.get("url", "") or item.get("link", ""),
                                title=item.get("title", ""),
                                snippet=item.get("snippet", ""),
                                source_domain=_extract_domain(
                                    item.get("url", "") or item.get("link", "")
                                ),
                                score=1.0,
                            )
                            results.append(result)
            except json.JSONDecodeError:
                pass

    except Exception as e:
        logger.warning(f"Failed to parse Gemini grounding response: {e}")

    # If parsing failed or no results, return empty list (fallback to next provider)
    return results


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
