from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from src.agents.atomic import write_thesis_node
from src.graphs.problem.graph import build_problem_graph
from src.graphs.product.graph import build_product_graph
from src.graphs.quality.graph import build_quality_graph
from src.graphs.routes import (
    CANDIDATE_PROBLEM_ROUTES,
    CANDIDATE_PRODUCT_ROUTES,
    CANDIDATE_QUALITY_ROUTES,
    CANDIDATE_VALIDATION_ROUTES,
    FINALIZATION_VALIDATION_ROUTES,
)
from src.graphs.state import CandidateGraphState, DiscoveryCollector
from src.graphs.validation.graph import build_validation_graph
from src.llm.client import LLMClient


def build_candidate_graph(collector: DiscoveryCollector, llm: LLMClient) -> Any:
    """Top-level per-candidate orchestrator over three independently testable subgraphs."""
    builder = StateGraph(CandidateGraphState)
    builder.add_node("problem_graph", build_problem_graph(llm))
    builder.add_node("product_graph", build_product_graph(collector, llm))
    builder.add_node("validation_graph", build_validation_graph(llm))
    builder.add_node("quality_graph", build_quality_graph(collector, llm))

    def write(state: CandidateGraphState) -> dict:
        return write_thesis_node(dict(state), state["candidate_prefix"])

    builder.add_node("write_problem_wedge_expansion_thesis", write)
    builder.add_edge(START, "problem_graph")
    builder.add_conditional_edges(
        "problem_graph",
        lambda state: state.get("problem_route", "REJECT"),
        CANDIDATE_PROBLEM_ROUTES,
    )
    builder.add_conditional_edges(
        "product_graph",
        lambda state: state.get("product_route", "HOLD"),
        CANDIDATE_PRODUCT_ROUTES,
    )
    builder.add_conditional_edges(
        "validation_graph",
        lambda state: state.get("validation_route", "HOLD"),
        CANDIDATE_VALIDATION_ROUTES,
    )
    builder.add_conditional_edges(
        "quality_graph",
        lambda state: state.get("next_route", "hold"),
        CANDIDATE_QUALITY_ROUTES,
    )
    builder.add_edge("write_problem_wedge_expansion_thesis", END)
    return builder.compile()


def build_candidate_research_graph(collector: DiscoveryCollector, llm: LLMClient) -> Any:
    """Expensive root/market/wedge analysis, bounded to the top ten evidence clusters."""
    builder = StateGraph(CandidateGraphState)
    builder.add_node("problem_graph", build_problem_graph(llm))
    builder.add_node("product_graph", build_product_graph(collector, llm))
    builder.add_edge(START, "problem_graph")
    builder.add_conditional_edges(
        "problem_graph",
        lambda state: state.get("problem_route", "REJECT"),
        CANDIDATE_PROBLEM_ROUTES,
    )
    builder.add_edge("product_graph", END)
    return builder.compile()


def build_candidate_finalization_graph(
    collector: DiscoveryCollector, llm: LLMClient
) -> Any:
    """Validation and adversarial quality loop, only for preliminary top five."""
    builder = StateGraph(CandidateGraphState)
    builder.add_node("validation_graph", build_validation_graph(llm))
    builder.add_node("quality_graph", build_quality_graph(collector, llm))

    def write(state: CandidateGraphState) -> dict:
        return write_thesis_node(dict(state), state["candidate_prefix"])

    builder.add_node("write_problem_wedge_expansion_thesis", write)
    builder.add_edge(START, "validation_graph")
    builder.add_conditional_edges(
        "validation_graph",
        lambda state: state.get("validation_route", "HOLD"),
        FINALIZATION_VALIDATION_ROUTES,
    )
    builder.add_conditional_edges(
        "quality_graph",
        lambda state: state.get("next_route", "hold"),
        CANDIDATE_QUALITY_ROUTES,
    )
    builder.add_edge("write_problem_wedge_expansion_thesis", END)
    return builder.compile()
