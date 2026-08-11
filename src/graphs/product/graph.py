from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from langgraph.graph import END, START, StateGraph

from src.agents.atomic import (
    analyze_structural_gap_node,
    design_wedge_candidates_node,
    evaluate_asset_node,
    evaluate_expansion_node,
    evaluation_node,
    merge_evaluations,
    research_existing_alternatives,
    select_wedge,
    trace,
)
from src.domain.models.schemas import unknown_score
from src.domain.policies.product import evaluate_product_testability
from src.graphs.state import CandidateGraphState, DiscoveryCollector
from src.llm.client import LLMClient
from src.services.discovery.thesis import (
    evaluate_founder_fit,
    evaluate_structural_gap,
    evaluate_switching,
    evaluate_wedge_simplicity,
)


def build_product_graph(collector: DiscoveryCollector, llm: LLMClient) -> Any:
    builder = StateGraph(CandidateGraphState)

    async def research(state: CandidateGraphState) -> dict:
        return await research_existing_alternatives(
            collector,
            state["cluster"],
            state["request"],
            state["freshness"],
            state["candidate_prefix"],
        )

    async def gap(state: CandidateGraphState) -> dict:
        return await analyze_structural_gap_node(
            state["cluster"], state["market_documents"], state["candidate_prefix"], llm
        )

    async def wedges(state: CandidateGraphState) -> dict:
        return await design_wedge_candidates_node(
            state["cluster"], state["candidate_prefix"], llm
        )

    def problem_strength(state: CandidateGraphState) -> dict:
        return evaluation_node(
            "problem_strength_score",
            state["cluster"].problem_strength,
            state["candidate_prefix"],
        )

    def repetition(state: CandidateGraphState) -> dict:
        return evaluation_node(
            "repetition_score", state["cluster"].repetition, state["candidate_prefix"]
        )

    def workaround(state: CandidateGraphState) -> dict:
        return evaluation_node(
            "workaround_score",
            state["cluster"].workaround_strength,
            state["candidate_prefix"],
        )

    def structural(state: CandidateGraphState) -> dict:
        score = (
            evaluate_structural_gap(state["market"])
            if state.get("causal_gap_verified", False)
            else unknown_score(10, "LLM found no directly verified causal structural gap")
        )
        return evaluation_node("structural_gap_score", score, state["candidate_prefix"])

    def simplicity(state: CandidateGraphState) -> dict:
        return evaluation_node(
            "wedge_simplicity_score",
            evaluate_wedge_simplicity(state["wedge_candidates"][0]),
            state["candidate_prefix"],
        )

    def switching(state: CandidateGraphState) -> dict:
        return evaluation_node(
            "switching_score", evaluate_switching(state["cluster"]), state["candidate_prefix"]
        )

    async def asset(state: CandidateGraphState) -> dict:
        return await evaluate_asset_node(dict(state), state["candidate_prefix"], llm)

    async def expansion(state: CandidateGraphState) -> dict:
        return await evaluate_expansion_node(dict(state), state["candidate_prefix"], llm)

    def founder(state: CandidateGraphState) -> dict:
        return evaluation_node(
            "founder_fit_score", evaluate_founder_fit(state["cluster"]), state["candidate_prefix"]
        )

    def merge(state: CandidateGraphState) -> dict:
        return merge_evaluations(dict(state), state["candidate_prefix"])

    def choose_wedge(state: CandidateGraphState) -> dict:
        return select_wedge(state["wedge_candidates"], state["candidate_prefix"])

    def product_gate(state: CandidateGraphState) -> dict:
        started, clock = datetime.now(UTC), perf_counter()
        wedge = state["selected_wedge"]
        decision = evaluate_product_testability(state["cluster"], wedge)
        return {
            "product_route": decision.route,
            "unknowns": list(decision.unknowns),
            "validation_hypotheses": list(decision.unknowns),
            "trace": [
                trace(
                    f"{state['candidate_prefix']}:product_quality_gate",
                    started,
                    clock,
                    decision.reason,
                    actual_route=decision.route,
                    route_reason=decision.reason,
                )
            ],
        }

    builder.add_node("analyze_existing_alternatives", research)
    builder.add_node("analyze_structural_gap", gap)
    builder.add_node("design_wedge_candidates", wedges)
    evaluators = {
        "evaluate_problem_strength": problem_strength,
        "evaluate_repetition": repetition,
        "evaluate_workaround_strength": workaround,
        "evaluate_structural_gap": structural,
        "evaluate_wedge_simplicity": simplicity,
        "evaluate_switching_feasibility": switching,
        "evaluate_founder_fit": founder,
    }
    for name, node in evaluators.items():
        builder.add_node(name, node)
    builder.add_node("evaluate_asset_accumulation", asset)
    builder.add_node("evaluate_expansion_potential", expansion)
    builder.add_node("merge_evaluations", merge)
    builder.add_node("select_wedge", choose_wedge)
    builder.add_node("product_quality_gate", product_gate)

    builder.add_edge(START, "analyze_existing_alternatives")
    builder.add_edge("analyze_existing_alternatives", "analyze_structural_gap")
    builder.add_edge("analyze_structural_gap", "design_wedge_candidates")
    for name in evaluators:
        builder.add_edge("design_wedge_candidates", name)
    builder.add_edge("design_wedge_candidates", "evaluate_asset_accumulation")
    builder.add_edge("evaluate_asset_accumulation", "evaluate_expansion_potential")
    builder.add_edge([*evaluators, "evaluate_expansion_potential"], "merge_evaluations")
    builder.add_edge("merge_evaluations", "select_wedge")
    builder.add_edge("select_wedge", "product_quality_gate")
    builder.add_edge("product_quality_gate", END)
    return builder.compile()
