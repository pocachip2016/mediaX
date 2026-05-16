"""
WebSearch package — multi-provider search abstraction with quota management.

Phase D (dev-meta-intelligence) 5th content source.
"""

from api.meta_core.web_search.base import WebSearchProvider, WebSearchResult
from api.meta_core.web_search.brave import BraveSearchProvider
from api.meta_core.web_search.serpapi import SerpApiProvider
from api.meta_core.web_search.gemini_grounding import GeminiGroundingProvider
from api.meta_core.web_search.ollama_ddg import OllamaDDGProvider
from api.meta_core.web_search.cache import cache_get, cache_put
from api.meta_core.web_search.guard import check_bulk_allowed
from api.meta_core.web_search.factory import get_provider_chain, search_with_fallback
from api.meta_core.web_search.errors import (
    QuotaExhaustedError,
    ProviderUnavailableError,
    BulkQuotaError,
)

__all__ = [
    "WebSearchProvider",
    "WebSearchResult",
    "BraveSearchProvider",
    "SerpApiProvider",
    "GeminiGroundingProvider",
    "OllamaDDGProvider",
    "cache_get",
    "cache_put",
    "check_bulk_allowed",
    "get_provider_chain",
    "search_with_fallback",
    "QuotaExhaustedError",
    "ProviderUnavailableError",
    "BulkQuotaError",
]
