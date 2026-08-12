from __future__ import annotations

from src.desktop.topology import (
    EDGES,
    NODES,
    SNAPSHOTS,
    compile_runtime_graphs,
    normalize_runtime_node,
)


def test_desktop_topology_has_only_resolved_edges() -> None:
    names = [item.name for item in NODES]
    assert len(names) == len(set(names))
    node_set = set(names)
    assert all(edge.source in node_set and edge.target in node_set for edge in EDGES)


def test_desktop_topology_is_extracted_from_compiled_langgraphs() -> None:
    compiled = compile_runtime_graphs()
    snapshots = {item.name: item for item in SNAPSHOTS}
    assert set(snapshots) == set(compiled)
    for graph_name, runtime_graph in compiled.items():
        drawable = runtime_graph.get_graph()
        assert set(snapshots[graph_name].nodes) == set(drawable.nodes)
        assert set(snapshots[graph_name].edges) == {
            (edge.source, edge.target, str(edge.data or ""), bool(edge.conditional))
            for edge in drawable.edges
        }


def test_desktop_topology_exposes_compiled_fanout_fanin_and_revision_loops() -> None:
    edges = {
        (item.source, item.target, item.label, item.conditional, item.loop)
        for item in EDGES
    }
    assert (
        "social:verify_social_accounts_and_platforms",
        "social:evaluate_social_archetype_behavior_gamification",
        "",
        False,
        False,
    ) in edges
    assert (
        "social:evaluate_social_archetype_pain_removal",
        "social:merge_social_archetypes_for_one_week_validation",
        "",
        False,
        False,
    ) in edges
    assert (
        "portfolio:refine_behavior_queries",
        "portfolio:collect_behavior_sources",
        "",
        False,
        True,
    ) in edges
    assert (
        "quality:targeted_revision",
        "quality:evidence_gate",
        "",
        True,
        True,
    ) in edges
    assert ("quality:exit_challenger", "quality:arbitrate", "", True, True) in edges


def test_runtime_node_normalization_preserves_subgraph_nodes() -> None:
    assert (
        normalize_runtime_node("candidate-1:cluster-a:extract_pain")
        == "problem:extract_pain"
    )
    assert (
        normalize_runtime_node("candidate-1:cluster-a:review_problem_evidence")
        == "problem:review_problem_evidence"
    )
    assert (
        normalize_runtime_node("review_problem_evidence")
        == "problem:review_problem_evidence"
    )
    assert (
        normalize_runtime_node("review_problem_evidence", "portfolio")
        == "portfolio:review_problem_evidence"
    )
    assert (
        normalize_runtime_node("evaluate_social_archetype_behavior_gamification")
        == "social:evaluate_social_archetype_behavior_gamification"
    )
