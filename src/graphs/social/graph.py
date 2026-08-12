from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from langgraph.graph import END, START, StateGraph

from src.agents.atomic import trace
from src.domain.models.discovery import IdeaArchetype
from src.graphs.state import PortfolioGraphState
from src.services.discovery.social import extract_social_signals, select_social_archetypes


def build_social_discovery_graph() -> Any:
    """Extract social behavior and fan it into three bounded idea archetypes."""
    builder = StateGraph(PortfolioGraphState)

    def extract(state: PortfolioGraphState) -> dict:
        started, clock = datetime.now(UTC), perf_counter()
        signals, observations = extract_social_signals(
            state.get("documents", []), state.get("queries", [])
        )
        return {
            "social_signals": signals,
            "social_observations": observations,
            "trace": [
                trace(
                    "extract_social_behavior_memes",
                    started,
                    clock,
                    f"signals={len(signals)} observations={len(observations)}",
                )
            ],
        }

    def inspect_comments(state: PortfolioGraphState) -> dict:
        started, clock = datetime.now(UTC), perf_counter()
        participation = sum(
            bool(item.comment_participation_excerpts)
            for item in state.get("social_signals", [])
        )
        return {
            "trace": [
                trace(
                    "inspect_social_comment_participation",
                    started,
                    clock,
                    f"signals_with_mimicry_comments={participation}",
                )
            ]
        }

    def verify_independence(state: PortfolioGraphState) -> dict:
        started, clock = datetime.now(UTC), perf_counter()
        by_platform = Counter(item.platform for item in state.get("social_signals", []))
        accounts = {
            item.account_key
            for item in state.get("social_signals", [])
            if item.account_key
        }
        return {
            "trace": [
                trace(
                    "verify_social_accounts_and_platforms",
                    started,
                    clock,
                    f"accounts={len(accounts)} platforms={len(by_platform)}",
                )
            ]
        }

    def archetype_node(archetype: IdeaArchetype) -> Any:
        def evaluate(state: PortfolioGraphState) -> dict:
            started, clock = datetime.now(UTC), perf_counter()
            matches = [
                item
                for item in select_social_archetypes(state.get("social_signals", []))
                if item.archetype == archetype
            ]
            return {
                "social_archetypes": matches,
                "trace": [
                    trace(
                        f"evaluate_social_archetype_{archetype.value.lower()}",
                        started,
                        clock,
                        f"candidates={len(matches)}",
                    )
                ],
            }

        return evaluate

    def merge_archetypes(state: PortfolioGraphState) -> dict:
        started, clock = datetime.now(UTC), perf_counter()
        counts = Counter(item.archetype for item in state.get("social_archetypes", []))
        detail = " ".join(f"{item.value}={counts[item]}" for item in IdeaArchetype)
        return {
            "trace": [
                trace(
                    "merge_social_archetypes_for_one_week_validation",
                    started,
                    clock,
                    detail,
                )
            ]
        }

    builder.add_node("extract_social_behavior_memes", extract)
    builder.add_node("inspect_social_comment_participation", inspect_comments)
    builder.add_node("verify_social_accounts_and_platforms", verify_independence)
    for archetype in IdeaArchetype:
        builder.add_node(
            f"evaluate_social_archetype_{archetype.value.lower()}",
            archetype_node(archetype),
        )
    builder.add_node("merge_social_archetypes_for_one_week_validation", merge_archetypes)
    builder.add_edge(START, "extract_social_behavior_memes")
    builder.add_edge("extract_social_behavior_memes", "inspect_social_comment_participation")
    builder.add_edge(
        "inspect_social_comment_participation", "verify_social_accounts_and_platforms"
    )
    for archetype in IdeaArchetype:
        node = f"evaluate_social_archetype_{archetype.value.lower()}"
        builder.add_edge("verify_social_accounts_and_platforms", node)
        builder.add_edge(node, "merge_social_archetypes_for_one_week_validation")
    builder.add_edge("merge_social_archetypes_for_one_week_validation", END)
    return builder.compile()
