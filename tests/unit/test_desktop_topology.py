from __future__ import annotations

from src.desktop.topology import EDGES, NODES, normalize_runtime_node


def test_desktop_topology_has_only_resolved_edges() -> None:
    names = [item.name for item in NODES]
    assert len(names) == len(set(names))
    node_set = set(names)
    assert all(edge.source in node_set and edge.target in node_set for edge in EDGES)


def test_desktop_topology_exposes_fanout_fanin_and_revision_loops() -> None:
    edges = {(item.source, item.target, item.label, item.loop) for item in EDGES}
    assert (
        "verify_social_accounts_and_platforms",
        "evaluate_social_archetype_behavior_gamification",
        "fan-out",
        False,
    ) in edges
    assert (
        "evaluate_social_archetype_pain_removal",
        "merge_social_archetypes_for_one_week_validation",
        "fan-in",
        False,
    ) in edges
    assert (
        "refine_behavior_queries",
        "collect_behavior_sources",
        "retry",
        True,
    ) in edges
    assert ("targeted_revision", "evidence_gate", "changed", True) in edges
    assert ("exit_challenger", "arbitrate", "new BLOCKING", True) in edges


def test_runtime_node_normalization_preserves_subgraph_nodes() -> None:
    assert normalize_runtime_node("candidate-1:cluster-a:extract_pain") == "extract_pain"
    assert (
        normalize_runtime_node("candidate-1:cluster-a:review_problem_evidence")
        == "problem_review"
    )
    assert normalize_runtime_node("review_problem_evidence") == "review_problem_evidence"
    assert (
        normalize_runtime_node("evaluate_social_archetype_behavior_gamification")
        == "evaluate_social_archetype_behavior_gamification"
    )
