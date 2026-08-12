from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NodeSpec:
    name: str
    label: str
    group: str
    x: int
    y: int


@dataclass(frozen=True)
class EdgeSpec:
    source: str
    target: str
    label: str = ""
    loop: bool = False


NODES = (
    NodeSpec("plan_queries", "검색 계획", "PORTFOLIO", 40, 45),
    NodeSpec("collect_behavior_sources", "공개 원문 수집", "PORTFOLIO", 230, 45),
    NodeSpec("normalize_evidence", "근거 정규화", "PORTFOLIO", 440, 45),
    NodeSpec("social_discovery_subgraph", "SNS Subgraph 진입", "PORTFOLIO", 630, 45),
    NodeSpec("detect_workarounds", "행동·우회 추출", "PORTFOLIO", 820, 45),
    NodeSpec("deduplicate_root_problems", "문제 군집화", "PORTFOLIO", 1030, 45),
    NodeSpec("review_problem_evidence", "독립 근거 Gate", "PORTFOLIO", 1240, 45),
    NodeSpec("refine_behavior_queries", "추가 검색", "PORTFOLIO", 1240, 170),
    NodeSpec("orchestrate_candidate_subgraphs", "후보 fan-out", "PORTFOLIO", 1450, 45),
    NodeSpec("select_balanced_up_to_five_candidates", "후보 fan-in·선정", "PORTFOLIO", 1660, 45),
    NodeSpec("save_result", "결과 저장", "PORTFOLIO", 1850, 45),

    NodeSpec("extract_social_behavior_memes", "SNS 행동·밈 추출", "SOCIAL", 430, 155),
    NodeSpec("inspect_social_comment_participation", "댓글 참여 확인", "SOCIAL", 640, 155),
    NodeSpec("verify_social_accounts_and_platforms", "계정·플랫폼 교차확인", "SOCIAL", 850, 155),
    NodeSpec("evaluate_social_archetype_pain_removal", "불편 제거 원형", "SOCIAL", 1060, 115),
    NodeSpec("evaluate_social_archetype_behavior_gamification", "행동 게임화 원형", "SOCIAL", 1060, 180),
    NodeSpec("evaluate_social_archetype_social_competition_collection", "공유·경쟁·수집 원형", "SOCIAL", 1060, 245),
    NodeSpec("merge_social_archetypes_for_one_week_validation", "SNS 원형 fan-in", "SOCIAL", 1280, 180),

    NodeSpec("extract_pain", "Pain 추출", "PROBLEM", 80, 375),
    NodeSpec("identify_persona", "사용자 식별", "PROBLEM", 290, 375),
    NodeSpec("analyze_root_problem", "근본문제 분석", "PROBLEM", 500, 335),
    NodeSpec("analyze_behavior_opportunity", "행동 의미 재설계", "PROBLEM", 500, 425),
    NodeSpec("problem_review", "Problem Gate", "PROBLEM", 730, 375),

    NodeSpec("analyze_existing_alternatives", "기존 대안 조사", "PRODUCT", 80, 600),
    NodeSpec("analyze_structural_gap", "구조적 공백", "PRODUCT", 290, 600),
    NodeSpec("design_wedge_candidates", "Wedge 설계", "PRODUCT", 500, 600),
    NodeSpec("evaluate_problem_strength", "문제 강도", "PRODUCT", 730, 520),
    NodeSpec("evaluate_repetition", "반복성", "PRODUCT", 730, 575),
    NodeSpec("evaluate_workaround_strength", "우회 행동", "PRODUCT", 730, 630),
    NodeSpec("evaluate_structural_gap", "공백 점수", "PRODUCT", 730, 685),
    NodeSpec("evaluate_switching_feasibility", "전환 가능성", "PRODUCT", 950, 520),
    NodeSpec("evaluate_wedge_simplicity", "Wedge 단순성", "PRODUCT", 950, 575),
    NodeSpec("evaluate_founder_fit", "Founder Fit", "PRODUCT", 950, 630),
    NodeSpec("evaluate_asset_accumulation", "축적 자산", "PRODUCT", 950, 685),
    NodeSpec("evaluate_expansion_potential", "확장 가능성", "PRODUCT", 1170, 685),
    NodeSpec("merge_evaluations", "평가 fan-in", "PRODUCT", 1390, 600),
    NodeSpec("select_wedge", "Wedge 선택", "PRODUCT", 1590, 600),
    NodeSpec("product_quality_gate", "Product Gate", "PRODUCT", 1780, 600),
    NodeSpec("simplify_wedge_to_one_input_one_output", "1입력·1출력 단순화", "PRODUCT", 1590, 750),

    NodeSpec("design_validation", "검증 실험 설계", "VALIDATION", 760, 900),
    NodeSpec("validation_contract_gate", "Validation Gate", "VALIDATION", 1030, 900),

    NodeSpec("evidence_gate", "Evidence Gate", "QUALITY", 80, 1130),
    NodeSpec("cold_critique", "Cold Critique", "QUALITY", 300, 1130),
    NodeSpec("arbitrate", "Code Arbitration", "QUALITY", 520, 1130),
    NodeSpec("targeted_revision", "Targeted Revision", "QUALITY", 740, 1260),
    NodeSpec("final_verify", "Final Verify", "QUALITY", 780, 1130),
    NodeSpec("exit_challenger", "Exit Challenger", "QUALITY", 1010, 1130),
    NodeSpec("write_problem_wedge_expansion_thesis", "Thesis 작성", "QUALITY", 1260, 1130),
    NodeSpec("collect_more", "COLLECT MORE", "TERMINAL", 1510, 930),
    NodeSpec("extract_behavior", "EXTRACT BEHAVIOR", "TERMINAL", 1510, 1010),
    NodeSpec("recluster", "RECLUSTER", "TERMINAL", 1510, 1090),
    NodeSpec("human_review", "HUMAN REVIEW", "TERMINAL", 1510, 1170),
    NodeSpec("hold", "HOLD", "TERMINAL", 1740, 1010),
    NodeSpec("reject", "REJECT", "TERMINAL", 1740, 1090),
    NodeSpec("report_complete", "REPORT COMPLETE", "TERMINAL", 1740, 1170),
)


EDGES = (
    EdgeSpec("plan_queries", "collect_behavior_sources"),
    EdgeSpec("collect_behavior_sources", "normalize_evidence"),
    EdgeSpec("normalize_evidence", "social_discovery_subgraph"),
    EdgeSpec("social_discovery_subgraph", "extract_social_behavior_memes", "subgraph START"),
    EdgeSpec("extract_social_behavior_memes", "inspect_social_comment_participation"),
    EdgeSpec("inspect_social_comment_participation", "verify_social_accounts_and_platforms"),
    EdgeSpec("verify_social_accounts_and_platforms", "evaluate_social_archetype_pain_removal", "fan-out"),
    EdgeSpec("verify_social_accounts_and_platforms", "evaluate_social_archetype_behavior_gamification", "fan-out"),
    EdgeSpec("verify_social_accounts_and_platforms", "evaluate_social_archetype_social_competition_collection", "fan-out"),
    EdgeSpec("evaluate_social_archetype_pain_removal", "merge_social_archetypes_for_one_week_validation", "fan-in"),
    EdgeSpec("evaluate_social_archetype_behavior_gamification", "merge_social_archetypes_for_one_week_validation", "fan-in"),
    EdgeSpec("evaluate_social_archetype_social_competition_collection", "merge_social_archetypes_for_one_week_validation", "fan-in"),
    EdgeSpec("merge_social_archetypes_for_one_week_validation", "detect_workarounds", "subgraph END"),
    EdgeSpec("detect_workarounds", "deduplicate_root_problems"),
    EdgeSpec("deduplicate_root_problems", "review_problem_evidence"),
    EdgeSpec("review_problem_evidence", "refine_behavior_queries", "COLLECT_MORE"),
    EdgeSpec("refine_behavior_queries", "collect_behavior_sources", "retry", True),
    EdgeSpec("review_problem_evidence", "orchestrate_candidate_subgraphs", "ANALYZE"),
    EdgeSpec("orchestrate_candidate_subgraphs", "extract_pain", "candidate fan-out"),
    EdgeSpec("extract_pain", "identify_persona"),
    EdgeSpec("identify_persona", "analyze_root_problem", "PROBLEM_SOLVER"),
    EdgeSpec("identify_persona", "analyze_behavior_opportunity", "REDESIGN / WILD"),
    EdgeSpec("analyze_root_problem", "problem_review"),
    EdgeSpec("analyze_behavior_opportunity", "problem_review"),
    EdgeSpec("problem_review", "analyze_existing_alternatives", "ANALYZE"),
    EdgeSpec("problem_review", "hold", "HOLD"),
    EdgeSpec("problem_review", "reject", "REJECT"),
    EdgeSpec("analyze_existing_alternatives", "analyze_structural_gap"),
    EdgeSpec("analyze_structural_gap", "design_wedge_candidates"),
    EdgeSpec("design_wedge_candidates", "evaluate_problem_strength", "fan-out"),
    EdgeSpec("design_wedge_candidates", "evaluate_repetition", "fan-out"),
    EdgeSpec("design_wedge_candidates", "evaluate_workaround_strength", "fan-out"),
    EdgeSpec("design_wedge_candidates", "evaluate_structural_gap", "fan-out"),
    EdgeSpec("design_wedge_candidates", "evaluate_switching_feasibility", "fan-out"),
    EdgeSpec("design_wedge_candidates", "evaluate_wedge_simplicity", "fan-out"),
    EdgeSpec("design_wedge_candidates", "evaluate_founder_fit", "fan-out"),
    EdgeSpec("design_wedge_candidates", "evaluate_asset_accumulation", "fan-out"),
    EdgeSpec("evaluate_asset_accumulation", "evaluate_expansion_potential"),
    EdgeSpec("evaluate_problem_strength", "merge_evaluations"),
    EdgeSpec("evaluate_repetition", "merge_evaluations"),
    EdgeSpec("evaluate_workaround_strength", "merge_evaluations"),
    EdgeSpec("evaluate_structural_gap", "merge_evaluations"),
    EdgeSpec("evaluate_switching_feasibility", "merge_evaluations"),
    EdgeSpec("evaluate_wedge_simplicity", "merge_evaluations"),
    EdgeSpec("evaluate_founder_fit", "merge_evaluations"),
    EdgeSpec("evaluate_expansion_potential", "merge_evaluations"),
    EdgeSpec("merge_evaluations", "select_wedge"),
    EdgeSpec("select_wedge", "product_quality_gate"),
    EdgeSpec("product_quality_gate", "simplify_wedge_to_one_input_one_output", "REVISE_WEDGE"),
    EdgeSpec("simplify_wedge_to_one_input_one_output", "evaluate_problem_strength", "re-evaluate", True),
    EdgeSpec("product_quality_gate", "design_validation", "DESIGN_VALIDATION"),
    EdgeSpec("product_quality_gate", "hold", "HOLD"),
    EdgeSpec("product_quality_gate", "reject", "REJECT"),
    EdgeSpec("design_validation", "validation_contract_gate"),
    EdgeSpec("validation_contract_gate", "evidence_gate", "APPROVE"),
    EdgeSpec("validation_contract_gate", "design_wedge_candidates", "REVISE_WEDGE", True),
    EdgeSpec("validation_contract_gate", "hold", "HOLD"),
    EdgeSpec("validation_contract_gate", "reject", "REJECT"),
    EdgeSpec("evidence_gate", "cold_critique", "pass"),
    EdgeSpec("cold_critique", "arbitrate"),
    EdgeSpec("arbitrate", "targeted_revision", "revise"),
    EdgeSpec("targeted_revision", "evidence_gate", "changed", True),
    EdgeSpec("targeted_revision", "analyze_root_problem", "root problem", True),
    EdgeSpec("targeted_revision", "analyze_existing_alternatives", "market", True),
    EdgeSpec("targeted_revision", "design_wedge_candidates", "wedge", True),
    EdgeSpec("targeted_revision", "evaluate_asset_accumulation", "asset/expansion", True),
    EdgeSpec("arbitrate", "final_verify", "verify"),
    EdgeSpec("arbitrate", "collect_more", "WEAK_EVIDENCE"),
    EdgeSpec("arbitrate", "extract_behavior", "behavior error"),
    EdgeSpec("arbitrate", "recluster", "DUPLICATE/cluster"),
    EdgeSpec("arbitrate", "human_review", "risk"),
    EdgeSpec("arbitrate", "hold", "limit/non-converging"),
    EdgeSpec("arbitrate", "reject", "blocking"),
    EdgeSpec("final_verify", "exit_challenger", "pass"),
    EdgeSpec("final_verify", "hold", "contract unknown"),
    EdgeSpec("final_verify", "reject", "contract fail"),
    EdgeSpec("exit_challenger", "arbitrate", "new BLOCKING", True),
    EdgeSpec("exit_challenger", "write_problem_wedge_expansion_thesis", "clear"),
    EdgeSpec("write_problem_wedge_expansion_thesis", "report_complete"),
    EdgeSpec("orchestrate_candidate_subgraphs", "select_balanced_up_to_five_candidates", "candidate fan-in"),
    EdgeSpec("select_balanced_up_to_five_candidates", "save_result"),
)


ALIASES = {
    "review_problem_evidence": "review_problem_evidence",
    "select_distinct_candidates": "select_balanced_up_to_five_candidates",
    "select_balanced_candidates": "select_balanced_up_to_five_candidates",
    "select_balanced_up_to_five_candidates": "select_balanced_up_to_five_candidates",
}


def normalize_runtime_node(raw: str) -> str:
    node = raw.rsplit(":", 1)[-1]
    if node == "review_problem_evidence" and ":" in raw:
        return "problem_review"
    return ALIASES.get(node, node)
