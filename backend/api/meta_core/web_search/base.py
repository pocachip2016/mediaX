from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class WebSearchResult:
    """Normalized web search result."""
    url: str
    title: str
    snippet: str
    source_domain: str  # e.g., 'imdb.com', 'namu.wiki'
    score: float = 1.0  # relevance score (0.0-1.0)


class WebSearchProvider(ABC):
    """Abstract base for web search providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier (e.g., 'brave', 'serpapi', 'gemini')."""
        pass

    @property
    @abstractmethod
    def daily_limit(self) -> int:
        """Daily query limit."""
        pass

    @abstractmethod
    async def search(self, query: str, num: int = 8) -> list[WebSearchResult]:
        """
        Execute web search.

        Args:
            query: Search query
            num: Number of results (may not be guaranteed)

        Returns:
            List of WebSearchResult, newest first (relevance order)

        Raises:
            QuotaExhaustedError: Daily limit exceeded
            ProviderUnavailableError: API error, network issue, etc.
        """
        pass
