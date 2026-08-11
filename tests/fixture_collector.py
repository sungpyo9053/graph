from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from src.domain.models.discovery import PublicDocument, SearchQuery, SearchResult


class FixtureDiscoveryCollector:
    is_fixture = True
    provider_name = "test-fixture"

    def __init__(self) -> None:
        self.fixture = json.loads(
            (Path(__file__).parent / "fixtures" / "online_seller.json").read_text()
        )

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
        del count, country, search_lang, freshness, max_original_pages
        results: list[SearchResult] = []
        documents: list[PublicDocument] = []
        for query_index, query in enumerate(queries):
            market_query = (
                query.discovery_intent.startswith("research existing alternatives")
                or query.discovery_intent.startswith("research why current alternatives")
            )
            enabled = market_query or query_index == 0
            if not enabled:
                continue
            texts = (
                [
                    "This comparison software accepts files and reports exceptions. Manual spreadsheet checks may still be required for unsupported sources.",
                    "This operations tool tracks states but customers report manually checking source systems when data is delayed.",
                ]
                if market_query
                else self.fixture["originals"]
            )
            query_id = hashlib.sha256(query.query.encode()).hexdigest()[:10]
            for index, text in enumerate(texts, start=1):
                result = SearchResult(
                    title=f"TEST FIXTURE {query.theme} {index}",
                    url=f"https://fixture.invalid/{query.theme}/{query_id}/{index}",
                    description="TEST FIXTURE search summary",
                    provider=self.provider_name,
                    query=query.query,
                    rank=index,
                    published_at=datetime(2026, 1, index, tzinfo=UTC),
                    is_fixture=True,
                )
                results.append(result)
                documents.append(
                    PublicDocument(
                        search_result=result,
                        access_level="ORIGINAL_VERIFIED",
                        accessed_at=datetime(2026, 8, 1, tzinfo=UTC),
                        status_code=200,
                        content_type="text/html",
                        extracted_text=text,
                    )
                )
        return results, documents
