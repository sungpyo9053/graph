from __future__ import annotations

from langgraph.graph import END

from src.graphs.candidate import (
    build_candidate_finalization_graph,
    build_candidate_graph,
)
from src.graphs.discovery.graph import build_discovery_graph
from src.graphs.product.graph import build_product_graph
from src.graphs.quality.graph import build_quality_graph
from src.graphs.routes import GRAPH_ROUTE_REGISTRY
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
