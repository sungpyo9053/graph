from __future__ import annotations

from typing import cast
from uuid import uuid4

from src.domain.models.discovery import DiscoveryPortfolio, DiscoveryRequest, SearchQuery
from src.graphs.discovery.graph import build_discovery_graph
from src.graphs.state import DiscoveryCollector, PortfolioGraphState
from src.llm.client import LLMClient, create_llm_client
from src.observability.heartbeat import reset_invocation_context, set_invocation_context


class PortfolioDiscoveryGraph:
    """Public facade for the compiled top-level LangGraph orchestrator."""

    def __init__(
        self,
        collector: DiscoveryCollector,
        *,
        llm: LLMClient | None = None,
        allow_test_fixture: bool = False,
        query_plan: list[SearchQuery] | None = None,
    ) -> None:
        if collector.is_fixture and not allow_test_fixture:
            raise ValueError("fixture collector is test-only and cannot run on the live path")
        self.collector = collector
        self.llm = llm or create_llm_client()
        self.query_plan = query_plan
        self.compiled = build_discovery_graph(collector, self.llm)

    async def run(self, request: DiscoveryRequest) -> DiscoveryPortfolio:
        run_id = str(uuid4())
        initial = PortfolioGraphState(
            run_id=run_id, request=request, trace=[], evidence_retry_count=0
        )
        if self.query_plan is not None:
            # The query-plan node respects this explicit plan through a focused wrapper state.
            # Inject after planning by compiling a tiny per-run override is unnecessary; replace
            # the deterministic planner output in the input and mark it for the graph node.
            initial["queries"] = self.query_plan
        tokens = set_invocation_context(run_id, "portfolio")
        try:
            result = await self.compiled.ainvoke(initial)
            return cast(DiscoveryPortfolio, result["portfolio"])
        finally:
            reset_invocation_context(tokens)
