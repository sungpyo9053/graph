from __future__ import annotations

from typing import Protocol

from src.domain.models.discovery import SearchResult


class SearchProviderError(RuntimeError):
    """Base search provider failure."""


class SearchAuthenticationError(SearchProviderError):
    """Missing or rejected provider credential."""


class SearchRateLimitError(SearchProviderError):
    """Provider rate limit or quota exhausted."""


class SearchTransientError(SearchProviderError):
    """Retryable provider/network failure."""


class SearchPermanentError(SearchProviderError):
    """Non-retryable request or response failure."""


SearchError = SearchProviderError


class SearchProvider(Protocol):
    name: str
    is_fixture: bool

    async def search(
        self,
        query: str,
        *,
        count: int,
        country: str,
        search_lang: str,
        freshness: str,
    ) -> list[SearchResult]: ...
