from __future__ import annotations

from dataclasses import dataclass

from src.domain.models.discovery import DiscoveryLane, ProblemCluster
from src.domain.models.schemas import RiskLevel, WedgeCandidate
from src.domain.policies.risk import assess_risk

TESTABLE_UNKNOWNS = (
    "switching behavior is unvalidated",
    "willingness to pay is unknown",
    "asset value is unvalidated",
    "expansion path is unvalidated",
    "repeat usage is unvalidated",
)


@dataclass(frozen=True)
class ProductGateDecision:
    route: str
    reason: str
    unknowns: tuple[str, ...] = TESTABLE_UNKNOWNS


def can_attempt_wedge_simplification(
    cluster: ProblemCluster, wedge: WedgeCandidate, retry_count: int
) -> tuple[bool, str]:
    """Allow one bounded redesign when manual one-input/one-output value is plausible."""
    minimum_evidence = 1 if cluster.lane == DiscoveryLane.WILD_BET else 2
    has_input = bool(
        wedge.user_input.strip()
        and wedge.user_input.strip().lower() != "unknown"
    )
    failed_simplicity = (
        wedge.complexity.strip().upper() != "LOW"
        or not wedge.data_access_feasible
        or not wedge.solo_first_user_value
    )
    allowed = (
        retry_count < 1
        and len(cluster.independent_evidence) >= minimum_evidence
        and wedge.problem_relevance
        and wedge.manual_validation_feasible
        and has_input
        and failed_simplicity
    )
    reason = (
        "one bounded simplification is allowed because verified behavior and a user-provided "
        "input can support a manual one-input/one-output test"
        if allowed
        else "wedge cannot be simplified safely within the single-retry contract"
    )
    return allowed, reason


def evaluate_product_testability(
    cluster: ProblemCluster, wedge: WedgeCandidate
) -> ProductGateDecision:
    risk, risk_reasons = assess_risk(
        " ".join(
            [wedge.user_input, wedge.core_process, wedge.expected_output, wedge.required_data]
        )
    )
    required_fields_present = all(
        value.strip() and value.strip().lower() != "unknown"
        for value in (wedge.user_input, wedge.core_process, wedge.expected_output)
    )
    minimum_evidence = 1 if cluster.lane == DiscoveryLane.WILD_BET else 2
    if len(cluster.independent_evidence) < minimum_evidence:
        return ProductGateDecision(
            "REJECT",
            f"fewer than {minimum_evidence} independent behavior originals for {cluster.lane}",
        )
    if not wedge.problem_relevance:
        return ProductGateDecision("REJECT", "wedge is unrelated to the evidenced problem")
    if cluster.lane == DiscoveryLane.PROBLEM_SOLVER and (
        wedge.behavior_displacement == "NO_DISPLACEMENT"
        or (
            wedge.external_form_reentry_required is True
            and (wedge.expected_steps_removed or 0) == 0
        )
    ):
        return ProductGateDecision(
            "REJECT",
            "wedge does not remove or consolidate an evidenced workaround step",
        )
    if risk == RiskLevel.BLOCKED:
        return ProductGateDecision(
            "REJECT", f"blocked safety or legal risk: {', '.join(risk_reasons)}"
        )
    if not wedge.data_access_feasible:
        return ProductGateDecision("HOLD", "required data is not currently accessible")
    if not wedge.solo_first_user_value:
        return ProductGateDecision(
            "HOLD", "first value requires supplier or network participation"
        )
    if not wedge.manual_validation_feasible:
        return ProductGateDecision("HOLD", "a bounded validation experiment is not feasible")
    if not required_fields_present:
        return ProductGateDecision(
            "HOLD", "required user input or experiment output is unavailable"
        )
    unknowns = list(TESTABLE_UNKNOWNS)
    if (
        cluster.lane == DiscoveryLane.PROBLEM_SOLVER
        and wedge.behavior_displacement == "UNKNOWN"
    ):
        unknowns.append("whether the wedge removes a current workaround step is unknown")
    if (
        cluster.lane == DiscoveryLane.PROBLEM_SOLVER
        and wedge.external_form_reentry_required is None
    ):
        unknowns.append("whether an incumbent form requires duplicate data entry is unknown")
    if cluster.lane == DiscoveryLane.BEHAVIOR_REDESIGN:
        if wedge.instant_visible_result is not True:
            unknowns.append("whether the reframed behavior produces an immediate visible result")
        if wedge.ten_second_demo is not True:
            unknowns.append("whether the delight loop is understandable in ten seconds")
        if wedge.repeat_trigger.strip().lower() == "unknown":
            unknowns.append("repeat trigger for the existing behavior")
        if wedge.network_amplification is not True:
            unknowns.append("whether additional participants amplify the delight loop")
    if cluster.lane == DiscoveryLane.WILD_BET:
        if wedge.validation_cost_usd is None:
            unknowns.append("bounded validation cost for the wild bet")
        elif wedge.validation_cost_usd > 300:
            return ProductGateDecision(
                "HOLD", "wild-bet validation exceeds the configured cheap-test budget"
            )
    return ProductGateDecision(
        "DESIGN_VALIDATION", "minimum testability contract passed", tuple(unknowns)
    )
