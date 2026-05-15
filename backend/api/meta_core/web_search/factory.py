import logging
from sqlalchemy.orm import Session

from shared.config import settings
from shared.quota_manager import QuotaManager
from api.meta_core.web_search.base import WebSearchProvider, WebSearchResult
from api.meta_core.web_search.brave import BraveSearchProvider
from api.meta_core.web_search.serpapi import SerpApiProvider
from api.meta_core.web_search.gemini_grounding import GeminiGroundingProvider
from api.meta_core.web_search.ollama_ddg import OllamaDDGProvider
from api.meta_core.web_search.cache import cache_get, cache_put
from api.meta_core.web_search.errors import QuotaExhaustedError, ProviderUnavailableError

logger = logging.getLogger(__name__)

_PROVIDER_MAP = {
    "brave": BraveSearchProvider,
    "serpapi": SerpApiProvider,
    "gemini": GeminiGroundingProvider,
    "ollama": OllamaDDGProvider,
}


def get_provider_chain(
    quota_manager: QuotaManager | None = None,
    preference: list[str] | None = None,
) -> list[WebSearchProvider]:
    """
    Build provider chain based on WEBSEARCH_PROVIDERS env (default: brave,serpapi,gemini,ollama).

    Args:
        quota_manager: Optional QuotaManager instance
        preference: Override provider order (default: settings.WEBSEARCH_PROVIDERS CSV)

    Returns:
        List of WebSearchProvider instances in fallback order
    """
    if preference is None:
        # Parse CSV from settings
        providers_csv = getattr(settings, "WEBSEARCH_PROVIDERS", "brave,serpapi,gemini,ollama")
        preference = [p.strip() for p in providers_csv.split(",") if p.strip()]

    quota_manager = quota_manager or QuotaManager()

    chain = []
    for provider_name in preference:
        provider_class = _PROVIDER_MAP.get(provider_name.lower())
        if provider_class:
            try:
                provider = provider_class(quota_manager=quota_manager)
                chain.append(provider)
            except (ValueError, ImportError) as e:
                logger.warning(f"Provider {provider_name} skipped: {e}")
        else:
            logger.warning(f"Unknown provider: {provider_name}")

    return chain


async def search_with_fallback(
    query: str,
    db: Session,
    num: int = 8,
    quota_manager: QuotaManager | None = None,
) -> tuple[list[WebSearchResult], str]:
    """
    Search with provider fallback chain.

    Steps:
    1. Try cache hit (all providers)
    2. Try each provider in order
    3. On QuotaExhaustedError or ProviderUnavailableError, try next provider
    4. Last resort: Ollama-DDG (unlimited, always available)

    Returns:
        (results, provider_used) — provider_used is the first successful provider name
    """
    chain = get_provider_chain(quota_manager=quota_manager)

    if not chain:
        logger.error("No providers available in chain")
        return [], "none"

    # Step 1: Try cache hit (any provider in chain)
    for provider in chain:
        cached = cache_get(query, provider.provider_name, db)
        if cached:
            logger.info(f"Cache HIT: {provider.provider_name} - query={query[:30]}")
            return cached, provider.provider_name

    # Step 2: Try each provider (cache miss)
    for provider in chain:
        try:
            logger.info(f"Trying {provider.provider_name}... - query={query[:30]}")
            results = await provider.search(query, num=num)

            if results:
                # Cache on success
                cache_put(query, provider.provider_name, results, db)
                logger.info(
                    f"Success: {provider.provider_name} - {len(results)} results, cached"
                )
                return results, provider.provider_name
            else:
                logger.debug(f"{provider.provider_name} returned empty results")

        except QuotaExhaustedError as e:
            logger.warning(f"{e.provider} quota exhausted (remaining={e.remaining}), next...")
            continue

        except ProviderUnavailableError as e:
            logger.warning(f"{e.provider} unavailable ({e.detail}), next...")
            continue

        except Exception as e:
            logger.exception(f"Unexpected error from {provider.provider_name}: {e}")
            continue

    logger.error(f"All providers exhausted for query={query[:30]}")
    return [], "none"
