from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from pydantic import ValidationError

from src.collectors.public_web import PublicPageFetcher, PublicWebCollector
from src.collectors.verified_urls import VerifiedUrlCollector
from src.config import Settings
from src.domain.models.discovery import DiscoveryMode, DiscoveryRequest
from src.domain.models.url_input import VerifiedUrlInput
from src.search.brave import BraveSearchProvider
from src.search.provider import SearchError
from src.services.daily.registry import CandidateRegistryStore
from src.services.daily.reporting import write_daily_result
from src.services.daily.runner import DailyDiscoveryProcessor
from src.services.discovery.orchestrator import PortfolioDiscoveryGraph
from src.services.discovery.reporting import write_portfolio


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evidence-based problem discovery graph")
    commands = parser.add_subparsers(dest="command", required=True)
    discover = commands.add_parser("discover", help="research public web sources")
    discover.add_argument("--mode", choices=["open", "focused"], default="open")
    discover.add_argument("--focus")
    discover.add_argument("--max-candidates", type=int, default=None)
    discover.add_argument("--country")
    discover.add_argument("--search-lang")
    discover.add_argument("--lookback-days", type=int)
    discover.add_argument("--results-per-query", type=int)
    discover.add_argument("--max-original-pages", type=int)
    discover.add_argument("--output-dir", type=Path)
    daily = commands.add_parser("discover-daily", help="run one persisted daily discovery")
    daily.add_argument("--mode", choices=["open", "focused"], default="open")
    daily.add_argument("--focus")
    daily.add_argument("--market", default="KR")
    daily.add_argument("--language", default="ko")
    daily.add_argument("--candidate-count", type=int, default=5)
    daily.add_argument("--lookback-days", type=int)
    daily.add_argument("--results-per-query", type=int)
    daily.add_argument("--max-original-pages", type=int)
    daily.add_argument("--output-dir", type=Path)
    from_urls = commands.add_parser(
        "discover-from-urls", help="discover from 10-30 verified public URLs without a paid API"
    )
    from_urls.add_argument("--input", type=Path, required=True)
    from_urls.add_argument("--output-dir", type=Path)
    from_urls.add_argument("--lookback-days", type=int, default=3650)
    from_urls.add_argument("--max-original-pages", type=int, default=30)
    return parser


async def discover(args: argparse.Namespace, config: Settings) -> Path:
    provider = _live_provider(config)
    request = DiscoveryRequest(
        mode=DiscoveryMode(args.mode),
        focus=args.focus,
        max_candidates=args.max_candidates or 5,
        country=args.country or config.discovery_country,
        search_lang=args.search_lang or config.discovery_search_lang,
        lookback_days=args.lookback_days or config.discovery_lookback_days,
        results_per_query=args.results_per_query or config.discovery_results_per_query,
        max_original_pages=args.max_original_pages or config.discovery_max_original_pages,
    )
    collector = PublicWebCollector(provider, PublicPageFetcher())
    portfolio = await PortfolioDiscoveryGraph(collector).run(request)
    output_dir = args.output_dir or Path(config.discovery_output_dir)
    return write_portfolio(portfolio, output_dir)


async def discover_daily(args: argparse.Namespace, config: Settings) -> Path:
    provider = _live_provider(config)
    request = DiscoveryRequest(
        mode=DiscoveryMode(args.mode),
        focus=args.focus,
        max_candidates=args.candidate_count,
        country=args.market,
        search_lang=args.language,
        lookback_days=args.lookback_days or config.discovery_lookback_days,
        results_per_query=args.results_per_query or config.discovery_results_per_query,
        max_original_pages=args.max_original_pages or config.discovery_max_original_pages,
    )
    output_dir = args.output_dir or Path(config.discovery_output_dir)
    collector = PublicWebCollector(provider, PublicPageFetcher())
    portfolio = await PortfolioDiscoveryGraph(collector).run(request)
    store = CandidateRegistryStore(output_dir / "daily" / "candidate-registry.json")
    daily_result = DailyDiscoveryProcessor(store).process(portfolio)
    return write_daily_result(daily_result, output_dir)


async def discover_from_urls(args: argparse.Namespace, config: Settings) -> Path:
    source = VerifiedUrlInput.model_validate_json(args.input.read_text(encoding="utf-8"))
    request = DiscoveryRequest(
        mode=DiscoveryMode.FOCUSED,
        focus=source.label,
        max_candidates=5,
        country=source.market,
        search_lang=source.language,
        lookback_days=args.lookback_days,
        results_per_query=20,
        max_original_pages=args.max_original_pages,
    )
    collector = VerifiedUrlCollector(source, PublicPageFetcher())
    portfolio = await PortfolioDiscoveryGraph(
        collector, query_plan=source.query_plan()
    ).run(request)
    output_dir = args.output_dir or Path(config.discovery_output_dir)
    return write_portfolio(portfolio, output_dir)


def _live_provider(config: Settings) -> BraveSearchProvider:
    if config.search_provider.lower() != "brave":
        raise ValueError("SEARCH_PROVIDER must be 'brave' in this release")
    if config.brave_search_api_key is None or not config.brave_search_api_key.get_secret_value():
        raise ValueError("BRAVE_SEARCH_API_KEY is required for live discovery")
    return BraveSearchProvider(config.brave_search_api_key.get_secret_value())


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "discover":
            run_dir = asyncio.run(discover(args, Settings()))
            print(f"Discovery completed: {run_dir}")
            print(f"Summary: {run_dir / 'summary.md'}")
            return 0
        if args.command == "discover-daily":
            run_dir = asyncio.run(discover_daily(args, Settings()))
            print(f"Daily discovery completed: {run_dir}")
            print(f"Review packet: {run_dir / 'review-packet.md'}")
            return 0
        if args.command == "discover-from-urls":
            run_dir = asyncio.run(discover_from_urls(args, Settings()))
            print(f"URL discovery completed: {run_dir}")
            print(f"Summary: {run_dir / 'summary.md'}")
            return 0
    except (SearchError, ValidationError, ValueError) as exc:
        print(f"discovery failed: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
