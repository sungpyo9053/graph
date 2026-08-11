from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import httpx
import pytest

from src.collectors.public_web import PublicPageFetcher, PublicWebCollector
from src.domain.models.discovery import PublicDocument, SearchQuery, SearchResult
from src.search.brave import BraveSearchProvider
from src.search.provider import SearchAuthenticationError, SearchRateLimitError
from src.services.discovery.extraction import extract_observations


@pytest.mark.asyncio
async def test_brave_adapter_sends_official_contract_and_parses_results() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["token"] = request.headers.get("X-Subscription-Token")
        return httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {
                            "title": "Manual workflow",
                            "url": "https://public.example/post",
                            "description": "I manually use a spreadsheet every week.",
                            "page_age": "2026-01-02T00:00:00Z",
                        }
                    ]
                }
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await BraveSearchProvider("secret", client=client).search(
            "manual workflow",
            count=10,
            country="us",
            search_lang="en",
            freshness="2025-01-01to2026-01-01",
        )
    assert seen["token"] == "secret"
    assert str(seen["url"]).startswith("https://api.search.brave.com/res/v1/web/search?")
    assert "freshness=2025-01-01to2026-01-01" in str(seen["url"])
    assert results[0].published_at == datetime(2026, 1, 2, tzinfo=UTC)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "error"),
    [(401, SearchAuthenticationError), (429, SearchRateLimitError)],
)
async def test_brave_adapter_classifies_auth_and_quota(status, error) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(status))
    ) as client:
        with pytest.raises(error):
            await BraveSearchProvider("secret", client=client).search(
                "manual workflow", count=1, country="US", search_lang="en", freshness="pw"
            )


@pytest.mark.asyncio
async def test_original_and_snippet_are_distinct_and_only_original_becomes_evidence() -> None:
    result = SearchResult(
        title="Behavior",
        url="https://public.example/post",
        description="snippet manually spreadsheet",
        provider="brave",
        query="q",
        rank=1,
    )
    html = (
        "<html><body>Every week I manually check multiple systems and copy the result into a "
        "spreadsheet. It takes about 2 hours and I double-check the source every time."
        + " x" * 80
        + "</body></html>"
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, headers={"content-type": "text/html"}, text=html)
        )
    ) as client:
        fetcher = PublicPageFetcher(client=client)
        fetcher._unsafe_url_reason = AsyncMock(return_value=None)  # type: ignore[method-assign]
        original = await fetcher.fetch(result)
    snippet = PublicDocument(
        search_result=result,
        access_level="SEARCH_SNIPPET_ONLY",
        error_reason="robots_or_fetch_failure",
    )
    query = SearchQuery(
        query="q",
        theme="operations",
    )
    observations, exclusions = extract_observations([snippet, original], [query])
    assert len(observations) == 1
    assert observations[0].evidence.access_level == "ORIGINAL_VERIFIED"
    assert exclusions["snippet_only:robots_or_fetch_failure"] == 1


def test_live_collector_rejects_fixture_provider() -> None:
    class Provider:
        name = "fixture"
        is_fixture = True

    with pytest.raises(ValueError, match="cannot use a fixture"):
        PublicWebCollector(Provider(), PublicPageFetcher())  # type: ignore[arg-type]
