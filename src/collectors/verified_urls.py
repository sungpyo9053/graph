from __future__ import annotations

from src.collectors.public_web import PublicPageFetcher
from src.domain.models.discovery import PublicDocument, SearchQuery, SearchResult
from src.domain.models.url_input import VerifiedUrlInput


class VerifiedUrlCollector:
    """Free collector that always GETs operator/Codex-curated public originals."""

    is_fixture = False
    provider_name = "verified-url-input"

    def __init__(self, source: VerifiedUrlInput, fetcher: PublicPageFetcher) -> None:
        self.source = source
        self.fetcher = fetcher
        self._query_by_theme = {item.theme: item.query for item in source.query_plan()}

    async def search(
        self,
        queries: list[SearchQuery],
        *,
        count: int,
        country: str,
        search_lang: str,
        freshness: str,
        max_original_pages: int,
    ) -> tuple[list[SearchResult], list[PublicDocument]]:
        del count, country, search_lang, freshness
        market_call = any(
            item.discovery_intent.startswith("research existing alternatives")
            or item.discovery_intent.startswith("research why current alternatives")
            for item in queries
        )
        market_types = {"product", "company", "official", "market", "review"}
        original_queries = {
            self._query_by_theme[item.theme]
            for item in queries
            if item.theme in self._query_by_theme
        }
        entries = [
            item
            for item in self.source.urls
            if item.discovered_via_query in original_queries
            and (not market_call or item.source_type.lower() in market_types)
        ]
        results = [
            SearchResult(
                title=item.title,
                url=item.url,
                description="curated search lead; original GET is required before evidence use",
                provider=self.provider_name,
                query=(queries[0].query if market_call and queries else item.discovered_via_query),
                rank=index,
                published_at=item.published_at,
                result_type=item.source_type,
            )
            for index, item in enumerate(entries, start=1)
        ]
        documents = await self.fetcher.fetch_many(results[:max_original_pages])
        fetched = {str(item.search_result.url) for item in documents}
        documents.extend(
            PublicDocument(
                search_result=result,
                access_level="SEARCH_SNIPPET_ONLY",
                error_reason="original_fetch_budget_exceeded",
            )
            for result in results
            if str(result.url) not in fetched
        )
        return results, documents
