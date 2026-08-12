from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse


class SocialPlatformAdapter(Protocol):
    name: str

    def matches(self, url: str) -> bool: ...

    def account_key(self, url: str) -> str | None: ...


@dataclass(frozen=True)
class PathAccountAdapter:
    name: str
    hosts: tuple[str, ...]
    account_prefix: str | None = None
    account_position: int = 0

    def matches(self, url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        return any(host == item or host.endswith(f".{item}") for item in self.hosts)

    def account_key(self, url: str) -> str | None:
        parts = [item for item in urlparse(url).path.split("/") if item]
        if len(parts) <= self.account_position:
            return None
        value = parts[self.account_position]
        if self.account_prefix and not value.startswith(self.account_prefix):
            return None
        if value.lower() in {"p", "reel", "reels", "watch", "shorts", "r", "comments"}:
            return None
        return f"{self.name}:{value.lower()}"


@dataclass(frozen=True)
class HostOnlyAdapter:
    name: str
    hosts: tuple[str, ...]

    def matches(self, url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        return any(host == item or host.endswith(f".{item}") for item in self.hosts)

    def account_key(self, url: str) -> None:
        del url
        return None


SOCIAL_ADAPTERS: tuple[PathAccountAdapter | HostOnlyAdapter, ...] = (
    PathAccountAdapter("x", ("x.com", "twitter.com"), account_position=0),
    PathAccountAdapter("threads", ("threads.net",), account_prefix="@", account_position=0),
    PathAccountAdapter("tiktok", ("tiktok.com",), account_prefix="@", account_position=0),
    HostOnlyAdapter("youtube", ("youtube.com", "youtu.be")),
    HostOnlyAdapter("instagram", ("instagram.com",)),
    HostOnlyAdapter("reddit", ("reddit.com",)),
    HostOnlyAdapter("facebook", ("facebook.com",)),
    HostOnlyAdapter("dcinside", ("dcinside.com",)),
    HostOnlyAdapter("theqoo", ("theqoo.net",)),
    HostOnlyAdapter("instiz", ("instiz.net",)),
    HostOnlyAdapter("clien", ("clien.net",)),
    HostOnlyAdapter("ppomppu", ("ppomppu.co.kr",)),
)


def social_source_metadata(url: str) -> tuple[str, str | None] | None:
    for adapter in SOCIAL_ADAPTERS:
        if adapter.matches(url):
            return adapter.name, adapter.account_key(url)
    return None
