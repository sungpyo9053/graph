from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from src.agents.atomic import (
    analyze_behavior_reframe,
    analyze_root_problem,
    extract_pain,
    identify_persona,
    problem_gate,
)
from src.domain.models.discovery import DiscoveryLane
from src.graphs.state import CandidateGraphState
from src.llm.client import LLMClient


def build_problem_graph(llm: LLMClient) -> Any:
    builder = StateGraph(CandidateGraphState)

    def pain_node(state: CandidateGraphState) -> dict:
        return extract_pain(state["cluster"], state["candidate_prefix"])

    async def persona_node(state: CandidateGraphState) -> dict:
        return await identify_persona(state["cluster"], state["candidate_prefix"], llm)

    async def root_node(state: CandidateGraphState) -> dict:
        return await analyze_root_problem(state["cluster"], state["candidate_prefix"], llm)

    async def reframe_node(state: CandidateGraphState) -> dict:
        return await analyze_behavior_reframe(
            state["cluster"], state["candidate_prefix"], llm
        )

    def review_node(state: CandidateGraphState) -> dict:
        return problem_gate(
            state["cluster"], state.get("root_problem", ""), state["candidate_prefix"]
        )

    builder.add_node("extract_pain", pain_node)
    builder.add_node("identify_persona", persona_node)
    builder.add_node("analyze_root_problem", root_node)
    builder.add_node("analyze_behavior_opportunity", reframe_node)
    builder.add_node("review_problem_evidence", review_node)
    builder.add_edge(START, "extract_pain")
    builder.add_edge("extract_pain", "identify_persona")
    builder.add_conditional_edges(
        "identify_persona",
        lambda state: (
            "analyze_root_problem"
            if state["cluster"].lane == DiscoveryLane.PROBLEM_SOLVER
            else "analyze_behavior_opportunity"
        ),
        {
            "analyze_root_problem": "analyze_root_problem",
            "analyze_behavior_opportunity": "analyze_behavior_opportunity",
        },
    )
    builder.add_edge("analyze_root_problem", "review_problem_evidence")
    builder.add_edge("analyze_behavior_opportunity", "review_problem_evidence")
    builder.add_edge("review_problem_evidence", END)
    return builder.compile()
