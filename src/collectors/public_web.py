from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

from src.domain.models.discovery import PublicDocument, SearchQuery, SearchResult
from src.search.provider import SearchProvider

ACCESS_BARRIER_MARKERS = (
    'name="js_challenge"',
    "cf-chl-challenge",
    "g-recaptcha",
    "hcaptcha-response",
    "verify you are human",
    "enable javascript and cookies to continue",
    "log in to continue",
    "sign in to continue",
)


def access_barrier_reason(html: str) -> str | None:
    lowered = html.lower()
    for marker in ACCESS_BARRIER_MARKERS:
        if marker in lowered:
            return "access_barrier_or_bot_challenge"
    return None


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth and data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.parts)).strip()


def html_to_text(html: str, *, maximum_chars: int = 30_000) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return parser.text()[:maximum_chars]


class PublicPageFetcher:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 15,
        maximum_bytes: int = 1_500_000,
        concurrency: int = 8,
    ) -> None:
        self._external_client = client
        self.timeout_seconds = timeout_seconds
        self.maximum_bytes = maximum_bytes
        self._semaphore = asyncio.Semaphore(concurrency)

    async def fetch_many(self, results: list[SearchResult]) -> list[PublicDocument]:
        return list(await asyncio.gather(*(self.fetch(result) for result in results)))

    async def fetch(self, result: SearchResult) -> PublicDocument:
        async with self._semaphore:
            unsafe_reason = await self._unsafe_url_reason(str(result.url))
            if unsafe_reason:
                return self._snippet_only(result, unsafe_reason)
            headers = {
                "User-Agent": "EvidenceThesisGraph/0.1 (+public-research; contact=operator-configured)",
                "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.1",
            }
            try:
                if self._external_client is not None:
                    response = await self._external_client.get(str(result.url), headers=headers)
                else:
                    async with httpx.AsyncClient(
                        timeout=self.timeout_seconds,
                        follow_redirects=True,
                        max_redirects=5,
                    ) as client:
                        response = await client.get(str(result.url), headers=headers)
            except (httpx.HTTPError, OSError) as exc:
                return self._snippet_only(result, f"fetch_error:{type(exc).__name__}")
            redirect_reason = await self._unsafe_url_reason(str(response.url))
            if redirect_reason:
                return self._snippet_only(result, f"unsafe_redirect:{redirect_reason}")
            content_type = response.headers.get("content-type", "").lower()
            if response.status_code != 200:
                return self._snippet_only(
                    result, f"http_status:{response.status_code}", response.status_code
                )
            if not any(
                kind in content_type
                for kind in ("text/html", "application/xhtml+xml", "text/plain")
            ):
                return self._snippet_only(
                    result, "unsupported_content_type", response.status_code, content_type
                )
            if len(response.content) > self.maximum_bytes:
                return self._snippet_only(
                    result, "content_too_large", response.status_code, content_type
                )
            if "text/html" in content_type or "application/xhtml+xml" in content_type:
                barrier = access_barrier_reason(response.text)
                if barrier:
                    return self._snippet_only(
                        result, barrier, response.status_code, content_type
                    )
            text = response.text if "text/plain" in content_type else html_to_text(response.text)
            if len(text) < 120:
                return self._snippet_only(
                    result, "insufficient_original_text", response.status_code, content_type
                )
            from src.domain.models.discovery import discovery_now

            return PublicDocument(
                search_result=result,
                access_level="ORIGINAL_VERIFIED",
                accessed_at=discovery_now(),
                status_code=response.status_code,
                content_type=content_type,
                extracted_text=text,
            )

    @staticmethod
    def _snippet_only(
        result: SearchResult,
        reason: str,
        status_code: int | None = None,
        content_type: str | None = None,
    ) -> PublicDocument:
        return PublicDocument(
            search_result=result,
            access_level="SEARCH_SNIPPET_ONLY",
            status_code=status_code,
            content_type=content_type,
            error_reason=reason,
        )

    async def _unsafe_url_reason(self, url: str) -> str | None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return "unsupported_url"
        host = parsed.hostname.lower()
        if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
            return "private_host"
        try:
            addresses = await asyncio.to_thread(socket.getaddrinfo, host, None)
        except socket.gaierror:
            return "dns_failure"
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return "private_address"
        return None


class PublicWebCollector:
    is_fixture = False

    def __init__(self, provider: SearchProvider, fetcher: PublicPageFetcher) -> None:
        if provider.is_fixture:
            raise ValueError("live PublicWebCollector cannot use a fixture provider")
        self.provider = provider
        self.fetcher = fetcher

    @property
    def provider_name(self) -> str:
        return self.provider.name

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
        batches = await asyncio.gather(
            *(
                self.provider.search(
                    item.query,
                    count=count,
                    country=country,
                    search_lang=search_lang,
                    freshness=freshness,
                )
                for item in queries
            )
        )
        unique: dict[str, SearchResult] = {}
        for result in (item for batch in batches for item in batch):
            unique.setdefault(str(result.url), result)
        results = list(unique.values())
        documents = await self.fetcher.fetch_many(results[:max_original_pages])
        document_urls = {str(item.search_result.url) for item in documents}
        documents.extend(
            PublicDocument(
                search_result=result,
                access_level="SEARCH_SNIPPET_ONLY",
                error_reason="original_fetch_budget_exceeded",
            )
            for result in results
            if str(result.url) not in document_urls
        )
        return results, documents
