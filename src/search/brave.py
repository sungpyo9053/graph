from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import ValidationError

from src.domain.models.discovery import SearchResult
from src.search.provider import (
    SearchAuthenticationError,
    SearchPermanentError,
    SearchRateLimitError,
    SearchTransientError,
)


class BraveSearchProvider:
    name = "brave"
    is_fixture = False
    endpoint = "https://api.search.brave.com/res/v1/web/search"

    def __init__(
        self,
        api_key: str,
        *,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 20,
    ) -> None:
        if not api_key.strip():
            raise SearchAuthenticationError("BRAVE_SEARCH_API_KEY is required")
        self.api_key = api_key
        self._external_client = client
        self.timeout_seconds = timeout_seconds

    async def search(
        self,
        query: str,
        *,
        count: int,
        country: str,
        search_lang: str,
        freshness: str,
    ) -> list[SearchResult]:
        if not query.strip() or len(query) > 400 or len(query.split()) > 50:
            raise SearchPermanentError("Brave query must be 1-400 characters and at most 50 words")
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key,
        }
        params: dict[str, str | int] = {
            "q": query,
            "count": min(max(count, 1), 20),
            "country": country.upper(),
            "search_lang": search_lang.lower(),
            "safesearch": "moderate",
            "freshness": freshness,
            "extra_snippets": "true",
            "result_filter": "web,discussions",
        }
        try:
            if self._external_client is not None:
                response = await self._external_client.get(
                    self.endpoint, headers=headers, params=params
                )
            else:
                async with httpx.AsyncClient(
                    timeout=self.timeout_seconds, follow_redirects=True
                ) as client:
                    response = await client.get(self.endpoint, headers=headers, params=params)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise SearchTransientError(str(exc)) from exc
        if response.status_code in {401, 403}:
            raise SearchAuthenticationError("Brave Search rejected BRAVE_SEARCH_API_KEY")
        if response.status_code == 429:
            raise SearchRateLimitError("Brave Search rate limit or quota reached")
        if response.status_code >= 500:
            raise SearchTransientError(f"Brave Search HTTP {response.status_code}")
        if response.status_code >= 400:
            raise SearchPermanentError(
                f"Brave Search HTTP {response.status_code}: {response.text[:300]}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise SearchPermanentError("Brave Search returned invalid JSON") from exc
        return self._parse_results(payload, query)

    def _parse_results(self, payload: dict[str, Any], query: str) -> list[SearchResult]:
        parsed: list[SearchResult] = []
        seen: set[str] = set()
        groups = (
            ("web", payload.get("web", {}).get("results", [])),
            ("discussion", payload.get("discussions", {}).get("results", [])),
        )
        for result_type, items in groups:
            for item in items:
                url = str(item.get("url", ""))
                description = str(
                    item.get("description", "") or " ".join(item.get("extra_snippets", []))
                )
                if not url or not description or url in seen:
                    continue
                seen.add(url)
                published_at = self._parse_date(item.get("page_age") or item.get("age"))
                author_key = self._author_key(item)
                try:
                    parsed.append(
                        SearchResult(
                            title=str(item.get("title") or url),
                            url=url,
                            description=description,
                            provider=self.name,
                            query=query,
                            rank=len(parsed) + 1,
                            published_at=published_at,
                            result_type=result_type,
                            author_key=author_key,
                        )
                    )
                except ValidationError:
                    continue
        return parsed

    @staticmethod
    def _author_key(item: dict[str, Any]) -> str | None:
        profile = item.get("profile")
        article = item.get("article")
        value = None
        if isinstance(profile, dict):
            value = profile.get("long_name") or profile.get("name")
        if value is None and isinstance(article, dict):
            value = article.get("author")
        normalized = str(value or "").strip().lower()
        return f"author:{normalized}" if normalized else None

    @staticmethod
    def _parse_date(value: Any) -> datetime | None:
        if not isinstance(value, str):
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return None
