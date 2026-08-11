"""Canonical graph builders and node inventory used by runtime and UI documentation."""

from src.graphs.candidate import build_candidate_graph
from src.graphs.discovery.graph import build_discovery_graph
from src.graphs.problem.graph import build_problem_graph
from src.graphs.product.graph import build_product_graph
from src.graphs.quality.graph import build_quality_graph
from src.graphs.validation.graph import build_validation_graph

DISCOVERY_NODES = (
    "plan_queries",
    "collect_behavior_sources",
    "normalize_evidence",
    "detect_workarounds",
    "deduplicate_root_problems",
    "review_problem_evidence",
)

PROBLEM_NODES = (
    "extract_pain",
    "identify_persona",
    "analyze_root_problem",
    "review_problem_evidence",
)

PRODUCT_NODES = (
    "analyze_existing_alternatives",
    "analyze_structural_gap",
    "design_wedge_candidates",
    "evaluate_problem_strength",
    "evaluate_repetition",
    "evaluate_workaround_strength",
    "evaluate_structural_gap",
    "evaluate_switching_feasibility",
    "evaluate_wedge_simplicity",
    "evaluate_asset_accumulation",
    "evaluate_expansion_potential",
    "evaluate_founder_fit",
    "merge_evaluations",
    "select_wedge",
    "product_quality_gate",
)

VALIDATION_NODES = (
    "design_validation",
    "validation_contract_gate",
)

QUALITY_NODES = (
    "evidence_gate",
    "cold_critique",
    "arbitrate",
    "targeted_revision",
    "final_verify",
    "exit_challenger",
    "write_problem_wedge_expansion_thesis",
)

__all__ = [
    "DISCOVERY_NODES",
    "PROBLEM_NODES",
    "PRODUCT_NODES",
    "QUALITY_NODES",
    "VALIDATION_NODES",
    "build_candidate_graph",
    "build_discovery_graph",
    "build_problem_graph",
    "build_product_graph",
    "build_quality_graph",
    "build_validation_graph",
]
