from __future__ import annotations

from collections.abc import Hashable

from langgraph.graph import END

DISCOVERY_ROUTES: dict[Hashable, str] = {
    "COLLECT_MORE": "refine_behavior_queries",
    "ANALYZE": "orchestrate_candidate_subgraphs",
    "HOLD": "select_distinct_candidates",
}

CANDIDATE_PROBLEM_ROUTES: dict[Hashable, str] = {
    "ANALYZE_MARKET_STRUCTURE": "product_graph",
    "REJECT": END,
    "HOLD": END,
}
CANDIDATE_PRODUCT_ROUTES: dict[Hashable, str] = {
    "DESIGN_VALIDATION": "validation_graph",
    "REJECT": END,
    "HOLD": END,
}
CANDIDATE_VALIDATION_ROUTES: dict[Hashable, str] = {
    "APPROVE": "quality_graph",
    "REVISE_WEDGE": "product_graph",
    "HOLD": END,
    "REJECT": END,
}
FINALIZATION_VALIDATION_ROUTES: dict[Hashable, str] = {
    "APPROVE": "quality_graph",
    "HOLD": END,
    "REJECT": END,
}
CANDIDATE_QUALITY_ROUTES: dict[Hashable, str] = {
    "report_complete": "write_problem_wedge_expansion_thesis",
    "hold": END,
    "reject": END,
    "human_review": END,
    "collect_more": END,
    "extract_behavior": END,
    "recluster": END,
}

QUALITY_EVIDENCE_ROUTES: dict[Hashable, str] = {
    "cold_critique": "cold_critique",
    "hold": END,
    "reject": END,
    "collect_more": END,
    "extract_behavior": END,
}
QUALITY_CRITIQUE_ROUTES: dict[Hashable, str] = {"arbitrate": "arbitrate", "hold": END}
QUALITY_ARBITRATION_ROUTES: dict[Hashable, str] = {
    "targeted_revision": "targeted_revision",
    "final_verify": "final_verify",
    "hold": END,
    "reject": END,
    "human_review": END,
    "collect_more": END,
    "extract_behavior": END,
    "recluster": END,
}
QUALITY_REVISION_ROUTES: dict[Hashable, str] = {"evidence_gate": "evidence_gate", "hold": END}
QUALITY_VERIFY_ROUTES: dict[Hashable, str] = {
    "exit_challenger": "exit_challenger",
    "hold": END,
    "reject": END,
}
QUALITY_EXIT_ROUTES: dict[Hashable, str] = {
    "arbitrate": "arbitrate",
    "report_complete": END,
    "hold": END,
}

GRAPH_ROUTE_REGISTRY: dict[str, dict[Hashable, str]] = {
    "portfolio.review_problem_evidence": DISCOVERY_ROUTES,
    "candidate.problem_graph": CANDIDATE_PROBLEM_ROUTES,
    "candidate.product_graph": CANDIDATE_PRODUCT_ROUTES,
    "candidate.validation_graph": CANDIDATE_VALIDATION_ROUTES,
    "finalization.validation_graph": FINALIZATION_VALIDATION_ROUTES,
    "candidate.quality_graph": CANDIDATE_QUALITY_ROUTES,
    "quality.evidence_gate": QUALITY_EVIDENCE_ROUTES,
    "quality.cold_critique": QUALITY_CRITIQUE_ROUTES,
    "quality.arbitrate": QUALITY_ARBITRATION_ROUTES,
    "quality.targeted_revision": QUALITY_REVISION_ROUTES,
    "quality.final_verify": QUALITY_VERIFY_ROUTES,
    "quality.exit_challenger": QUALITY_EXIT_ROUTES,
}
