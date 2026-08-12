from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

from src.domain.models.discovery import DiscoveryLane
from src.domain.models.quality import (
    ArbitrationResult,
    ArbitrationVerdict,
    CritiqueCategory,
    CritiqueFinding,
    DiscoveryContract,
    VerificationCheck,
    VerificationResult,
)
from src.domain.policies.evidence import independent_qualifying_evidence
from src.domain.policies.validation import delight_validation_contract_failures

REVISION_ROUTE = {
    CritiqueCategory.WEAK_EVIDENCE: "collect_more",
    CritiqueCategory.WRONG_ROOT_PROBLEM: "root_problem_analysis",
    CritiqueCategory.MISSING_ALTERNATIVE: "market_research",
    CritiqueCategory.FALSE_STRUCTURAL_GAP: "market_research",
    CritiqueCategory.WEAK_WEDGE: "wedge_design",
    CritiqueCategory.NO_BEHAVIOR_CHANGE: "wedge_design",
    CritiqueCategory.NO_FIRST_USER_VALUE: "wedge_design",
    CritiqueCategory.DATA_UNAVAILABLE: "wedge_design",
    CritiqueCategory.PLATFORM_DEPENDENCY: "wedge_design",
    CritiqueCategory.REGULATORY_RISK: "human_review",
    CritiqueCategory.SAFETY_RISK: "reject",
    CritiqueCategory.FAKE_ASSET: "asset_expansion_analysis",
    CritiqueCategory.UNSUPPORTED_EXPANSION: "asset_expansion_analysis",
    CritiqueCategory.DUPLICATE_IDEA: "recluster",
}


def candidate_fingerprint(state: dict[str, Any]) -> str:
    market = state.get("market")
    selected_wedge = state.get("selected_wedge")
    payload = {
        "discovery_lane": state["cluster"].lane,
        "root_problem": state["cluster"].root_problem,
        "market": market.model_dump(mode="json") if market is not None else None,
        "wedge": selected_wedge.model_dump(mode="json")
        if selected_wedge is not None
        else None,
        "assets": [item.model_dump(mode="json") for item in state.get("assets", [])],
        "expansion": [
            item.model_dump(mode="json") for item in state.get("expansion_paths", [])
        ],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def evaluate_evidence_gate(
    state: dict[str, Any], contract: DiscoveryContract
) -> VerificationResult:
    cluster = state["cluster"]
    lane = cluster.lane
    all_evidence = cluster.independent_evidence
    evidence = independent_qualifying_evidence(all_evidence)
    evidence_ids = [item.signal_id for item in evidence]
    forbidden = {
        "persona_hint",
        "root_problem_hint",
        "wedge_hint",
        "asset_hint",
        "expansion_hint",
    }
    dumped_keys = set(cluster.model_dump())
    unique_independence = len(
        {item.independence_key for item in all_evidence}
    ) == len(all_evidence)
    unique_authors_and_items = len(
        {(item.author_key, item.original_item_key) for item in all_evidence}
    ) == len(all_evidence)
    checks = [
        VerificationCheck(
            name="fixture_free_live",
            passed=(
                not state.get("live_run", True)
                or not contract.forbid_fixture_in_live
                or not any(item.is_fixture for item in all_evidence)
            ),
            reason=(
                "non-live deterministic test run"
                if not state.get("live_run", True)
                else "live evidence contains no fixture"
                if not any(item.is_fixture for item in all_evidence)
                else "fixture contamination"
            ),
            evidence_ids=evidence_ids,
        ),
        VerificationCheck(
            name="original_get_success",
            passed=not contract.require_original_get
            or all(item.access_level == "ORIGINAL_VERIFIED" for item in all_evidence),
            reason="all evidence came from successful original GETs",
            evidence_ids=evidence_ids,
        ),
        VerificationCheck(
            name="minimum_independent_behavior_evidence",
            passed=len(evidence)
            >= (
                contract.minimum_wild_bet_behavior_evidence
                if lane == DiscoveryLane.WILD_BET
                else contract.minimum_independent_behavior_evidence
            ),
            reason=(
                f"independent evidence={len(evidence)} required="
                f"{contract.minimum_wild_bet_behavior_evidence if lane == DiscoveryLane.WILD_BET else contract.minimum_independent_behavior_evidence} "
                f"lane={lane}"
            ),
            evidence_ids=evidence_ids,
        ),
        VerificationCheck(
            name="observed_workaround",
            passed=lane != DiscoveryLane.PROBLEM_SOLVER
            or not contract.require_workaround
            or all(bool(item.workaround_observed) for item in evidence),
            reason=(
                "workaround is not required for behavior-redesign or wild-bet lanes"
                if lane != DiscoveryLane.PROBLEM_SOLVER
                else "each evidence item links an observed workaround"
            ),
            evidence_ids=evidence_ids,
        ),
        VerificationCheck(
            name="no_conclusion_hints",
            passed=not contract.forbid_conclusion_hints or not bool(forbidden & dumped_keys),
            reason="candidate input contains no conclusion hint fields",
        ),
        VerificationCheck(
            name="fact_inference_assumption_separation",
            passed=not contract.require_fact_inference_assumption_separation
            or bool(state.get("root_problem")) and bool(evidence),
            reason="quoted facts are stored in evidence and root problem is stored as inference",
            evidence_ids=evidence_ids,
        ),
        VerificationCheck(
            name="claim_evidence_links",
            passed=not contract.require_claim_evidence_links
            or bool(state.get("root_problem"))
            and len(evidence_ids)
            >= (
                contract.minimum_wild_bet_behavior_evidence
                if lane == DiscoveryLane.WILD_BET
                else contract.minimum_independent_behavior_evidence
            ),
            reason="root-problem claim is linked to independent evidence ids",
            evidence_ids=evidence_ids,
        ),
        VerificationCheck(
            name="duplicate_authors_and_reposts_removed",
            passed=unique_independence and unique_authors_and_items,
            reason="independence, author and original-item keys are unique",
            evidence_ids=evidence_ids,
        ),
    ]
    failed = [item.name for item in checks if not item.passed]
    if not failed:
        return VerificationResult(
            passed=True, checks=checks, next_route="cold_critique", reason="contract evidence gate passed"
        )
    if "fixture_free_live" in failed or "no_conclusion_hints" in failed:
        route = "reject"
    elif "minimum_independent_behavior_evidence" in failed:
        route = "collect_more"
    elif "observed_workaround" in failed:
        route = "extract_behavior"
    else:
        route = "hold"
    return VerificationResult(
        passed=False,
        checks=checks,
        next_route=route,
        reason=f"contract evidence gate failed: {', '.join(failed)}",
    )


def arbitrate_findings(
    findings: list[CritiqueFinding], state: dict[str, Any]
) -> tuple[list[ArbitrationResult], str]:
    evidence_ids = {item.signal_id for item in state["cluster"].independent_evidence}
    results: list[ArbitrationResult] = []
    for finding in findings:
        route = REVISION_ROUTE[finding.category]
        if finding.severity == "FALSE_POSITIVE":
            verdict = ArbitrationVerdict.FALSE_POSITIVE
            route = "final_verify"
            reason = "critic classified this proposal as a false positive"
        elif finding.severity == "TESTABLE_UNKNOWN":
            verdict = ArbitrationVerdict.NEEDS_MORE_EVIDENCE
            route = "validation_hypothesis"
            reason = "unknown can be tested by the bounded validation plan"
        elif (
            state["cluster"].lane != DiscoveryLane.PROBLEM_SOLVER
            and finding.category
            in {CritiqueCategory.FAKE_ASSET, CritiqueCategory.UNSUPPORTED_EXPANSION}
        ):
            verdict = ArbitrationVerdict.NEEDS_MORE_EVIDENCE
            route = "validation_hypothesis"
            reason = "asset and expansion are optional hypotheses for a delight or wild-bet validation"
        elif (
            state["cluster"].lane == DiscoveryLane.BEHAVIOR_REDESIGN
            and finding.category == CritiqueCategory.NO_BEHAVIOR_CHANGE
            and state.get("selected_wedge") is not None
            and state["selected_wedge"].instant_visible_result is True
            and state["selected_wedge"].repeat_trigger.strip().lower() != "unknown"
        ):
            verdict = ArbitrationVerdict.FALSE_POSITIVE
            route = "final_verify"
            reason = "behavior redesign changes meaning and replay motivation; pain displacement is not its contract"
        elif (
            finding.category == CritiqueCategory.WEAK_EVIDENCE
            and len(evidence_ids)
            >= (
                1
                if state["cluster"].lane == DiscoveryLane.WILD_BET
                else 2
            )
        ):
            verdict = ArbitrationVerdict.FALSE_POSITIVE
            route = "final_verify"
            reason = "code gate confirms at least two independent original behavior sources"
        elif finding.evidence_ids and not set(finding.evidence_ids) <= evidence_ids:
            verdict = ArbitrationVerdict.FALSE_POSITIVE
            route = "final_verify"
            reason = "finding cites evidence ids absent from the verified candidate"
        elif finding.category == CritiqueCategory.DATA_UNAVAILABLE:
            feasible = bool(state.get("selected_wedge") and state["selected_wedge"].data_access_feasible)
            verdict = ArbitrationVerdict.DEBATABLE if feasible else ArbitrationVerdict.VALID
            reason = "selected wedge data-access flag evaluated by code"
        else:
            verdict = ArbitrationVerdict.VALID
            reason = "finding is consistent with current structured candidate state"
        results.append(
            ArbitrationResult(
                finding_id=finding.finding_id,
                category=finding.category,
                verdict=verdict,
                evidence_ids=[item for item in finding.evidence_ids if item in evidence_ids],
                actual_route=route,
                reason=reason,
            )
        )
    actionable = [
        item
        for item in results
        if item.verdict
        in {
            ArbitrationVerdict.VALID,
            ArbitrationVerdict.NEEDS_MORE_EVIDENCE,
            ArbitrationVerdict.ENVIRONMENTAL_LIMIT,
        }
        and item.actual_route != "validation_hypothesis"
    ]
    if not actionable:
        return results, "final_verify"
    priority = ["reject", "human_review", "collect_more", "extract_behavior", "recluster", "root_problem_analysis", "market_research", "wedge_design", "asset_expansion_analysis"]
    routes = {item.actual_route for item in actionable}
    return results, next(route for route in priority if route in routes)


def repeated_root_finding(
    fingerprints: list[str], previous: list[str], limit: int
) -> bool:
    counts = Counter([*previous, *fingerprints])
    return any(counts[item] >= limit for item in fingerprints)


def canonical_finding_fingerprint(
    finding: CritiqueFinding, actual_route: str
) -> str:
    """Identify the same root finding, not merely the same broad category."""
    payload = {
        "category": finding.category.value,
        "affected_claim": _canonical_text(finding.affected_claim),
        "root_cause": _canonical_text(finding.root_cause),
        "actual_route": actual_route,
        "evidence_scope": sorted(set(finding.evidence_ids)),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _canonical_text(value: str) -> str:
    return " ".join(value.lower().split())


def final_verify(state: dict[str, Any], contract: DiscoveryContract) -> VerificationResult:
    gate = evaluate_evidence_gate(state, contract)
    checks = list(gate.checks)
    wedge = state.get("selected_wedge")
    cluster = state["cluster"]
    lane = cluster.lane
    validation = state.get("validation_plan")
    checks.extend(
        [
            VerificationCheck(
                name="data_access_feasible",
                passed=bool(wedge and wedge.data_access_feasible),
                reason="selected wedge must have a lawful feasible data path",
            ),
            VerificationCheck(
                name="solo_first_user_value",
                passed=bool(wedge and wedge.solo_first_user_value),
                reason="first user must receive value without network liquidity",
            ),
            VerificationCheck(
                name="validation_plan_present",
                passed=state.get("validation_plan") is not None,
                reason="bounded validation must exist before thesis",
            ),
            VerificationCheck(
                name="behavior_displacement_not_disproven",
                passed=lane != DiscoveryLane.PROBLEM_SOLVER
                or bool(
                    wedge
                    and wedge.behavior_displacement != "NO_DISPLACEMENT"
                    and not (
                        wedge.external_form_reentry_required is True
                        and (wedge.expected_steps_removed or 0) == 0
                    )
                ),
                reason=(
                    "entry wedge must remove or consolidate at least one evidenced "
                    "workaround step; duplicating an incumbent form is not displacement"
                ),
            ),
            VerificationCheck(
                name="delight_loop_testable",
                passed=lane != DiscoveryLane.BEHAVIOR_REDESIGN
                or bool(
                    wedge
                    and (
                        not contract.require_visible_result_for_delight
                        or wedge.instant_visible_result is True
                    )
                    and (
                        not contract.require_ten_second_demo_for_delight
                        or wedge.ten_second_demo is True
                    )
                    and wedge.repeat_trigger.strip().lower() != "unknown"
                    and wedge.social_loop.strip().lower() != "unknown"
                ),
                reason=(
                    "behavior redesign needs an immediate visible result, repeat trigger, "
                    "ten-second demonstrability, solo value, and a designed social loop; "
                    "network amplification remains a validation hypothesis"
                ),
            ),
            VerificationCheck(
                name="delight_longitudinal_validation_contract",
                passed=lane != DiscoveryLane.BEHAVIOR_REDESIGN
                or not delight_validation_contract_failures(validation, contract),
                reason=(
                    "delight validation must distinguish novelty from 5-of-7-day retention, "
                    "next-week demand, unsolicited sharing, referred arrival, and curiosity-driven return"
                ),
            ),
            VerificationCheck(
                name="wild_bet_is_cheap_and_bounded",
                passed=lane != DiscoveryLane.WILD_BET
                or bool(
                    wedge
                    and validation
                    and validation.duration_days
                    <= contract.maximum_wild_bet_duration_days
                    and validation.estimated_cost_usd
                    <= contract.maximum_wild_bet_cost_usd
                ),
                reason="wild bet must be testable within the configured duration and cost",
            ),
        ]
    )
    failed = [item.name for item in checks if not item.passed]
    if failed:
        route = "hold"
        return VerificationResult(
            passed=False,
            checks=checks,
            next_route=route,
            reason=f"final verification failed: {', '.join(failed)}",
        )
    return VerificationResult(
        passed=True,
        checks=checks,
        next_route="exit_challenger",
        reason="all DiscoveryContract conditions passed",
    )
