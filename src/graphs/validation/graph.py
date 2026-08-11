from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from langgraph.graph import END, START, StateGraph

from src.agents.atomic import design_validation_node, trace
from src.graphs.state import CandidateGraphState
from src.llm.client import LLMClient


def build_validation_graph(llm: LLMClient) -> Any:
    builder = StateGraph(CandidateGraphState)

    def design(state: CandidateGraphState) -> dict:
        return design_validation_node(
            state["cluster"],
            state["candidate_prefix"],
            state.get("validation_hypotheses", []),
        )

    def review(state: CandidateGraphState) -> dict:
        started, clock = datetime.now(UTC), perf_counter()
        plan = state["validation_plan"]
        route = "APPROVE" if plan.duration_days <= 14 else "HOLD"
        reason = "code validation contract passed" if route == "APPROVE" else "validation exceeds 14 days"
        return {
            "validation_route": route,
            "trace": [
                trace(
                    f"{state['candidate_prefix']}:validation_contract_gate",
                    started,
                    clock,
                    reason,
                    actual_route=route,
                    route_reason=reason,
                )
            ],
        }

    builder.add_node("design_validation", design)
    builder.add_node("validation_contract_gate", review)
    builder.add_edge(START, "design_validation")
    builder.add_edge("design_validation", "validation_contract_gate")
    builder.add_edge("validation_contract_gate", END)
    return builder.compile()
