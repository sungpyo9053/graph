from __future__ import annotations

from langgraph.graph import END

from src.graphs.candidate import (
    build_candidate_finalization_graph,
    build_candidate_graph,
)
from src.graphs.discovery.graph import build_discovery_graph
from src.graphs.problem.graph import build_problem_graph
from src.graphs.product.graph import build_product_graph
from src.graphs.quality.graph import build_quality_graph
from src.graphs.routes import GRAPH_ROUTE_REGISTRY
from src.graphs.social.graph import build_social_discovery_graph
from src.graphs.validation.graph import build_validation_graph
from src.llm.client import DeterministicFakeLLM
from tests.fixture_collector import FixtureDiscoveryCollector


def _edge_pairs(graph) -> set[tuple[str, str]]:
    return {(edge.source, edge.target) for edge in graph.get_graph().edges}


def test_documented_route_registry_is_the_runtime_builder_registry() -> None:
    collector = FixtureDiscoveryCollector()
    llm = DeterministicFakeLLM()
    graphs = {
        "portfolio": build_discovery_graph(collector, llm),
        "candidate": build_candidate_graph(collector, llm),
        "finalization": build_candidate_finalization_graph(collector, llm),
        "product": build_product_graph(collector, llm),
        "problem": build_problem_graph(llm),
        "validation": build_validation_graph(llm),
        "quality": build_quality_graph(collector, llm),
    }
    for qualified_source, routes in GRAPH_ROUTE_REGISTRY.items():
        graph_name, source = qualified_source.split(".", 1)
        nodes = set(graphs[graph_name].get_graph().nodes)
        assert source in nodes
        assert all(destination == END or destination in nodes for destination in routes.values())


def test_product_fan_out_fan_in_and_all_revision_back_edges_are_registered() -> None:
    collector = FixtureDiscoveryCollector()
    llm = DeterministicFakeLLM()
    product_edges = _edge_pairs(build_product_graph(collector, llm))
    evaluator_nodes = {
        "evaluate_problem_strength",
        "evaluate_repetition",
        "evaluate_workaround_strength",
        "evaluate_structural_gap",
        "evaluate_wedge_simplicity",
        "evaluate_switching_feasibility",
        "evaluate_founder_fit",
        "evaluate_asset_accumulation",
    }
    assert all(("design_wedge_candidates", node) in product_edges for node in evaluator_nodes)
    assert ("select_wedge", "product_quality_gate") in product_edges
    assert (
        GRAPH_ROUTE_REGISTRY["quality.targeted_revision"]["evidence_gate"]
        == "evidence_gate"
    )
    assert GRAPH_ROUTE_REGISTRY["quality.exit_challenger"]["arbitrate"] == "arbitrate"


def test_problem_graph_has_real_lane_branch_and_fan_in() -> None:
    edges = _edge_pairs(build_problem_graph(DeterministicFakeLLM()))

    assert ("identify_persona", "analyze_root_problem") in edges
    assert ("identify_persona", "analyze_behavior_opportunity") in edges
    assert ("analyze_root_problem", "review_problem_evidence") in edges
    assert ("analyze_behavior_opportunity", "review_problem_evidence") in edges


def test_social_subgraph_has_registered_order_and_portfolio_integration() -> None:
    social_edges = _edge_pairs(build_social_discovery_graph())
    assert {
        ("__start__", "extract_social_behavior_memes"),
        ("extract_social_behavior_memes", "inspect_social_comment_participation"),
        (
            "inspect_social_comment_participation",
            "verify_social_accounts_and_platforms",
        ),
        ("verify_social_accounts_and_platforms", "evaluate_social_archetype_pain_removal"),
        (
            "verify_social_accounts_and_platforms",
            "evaluate_social_archetype_behavior_gamification",
        ),
        (
            "verify_social_accounts_and_platforms",
            "evaluate_social_archetype_social_competition_collection",
        ),
        (
            "evaluate_social_archetype_pain_removal",
            "merge_social_archetypes_for_one_week_validation",
        ),
        (
            "evaluate_social_archetype_behavior_gamification",
            "merge_social_archetypes_for_one_week_validation",
        ),
        (
            "evaluate_social_archetype_social_competition_collection",
            "merge_social_archetypes_for_one_week_validation",
        ),
        ("merge_social_archetypes_for_one_week_validation", "__end__"),
    }.issubset(social_edges)

    portfolio_edges = _edge_pairs(
        build_discovery_graph(FixtureDiscoveryCollector(), DeterministicFakeLLM())
    )
    assert ("normalize_evidence", "social_discovery_subgraph") in portfolio_edges
    assert ("social_discovery_subgraph", "detect_workarounds") in portfolio_edges
