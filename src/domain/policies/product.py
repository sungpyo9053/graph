from __future__ import annotations

from dataclasses import dataclass

from src.domain.models.discovery import ProblemCluster
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
    if len(cluster.independent_evidence) < 2:
        return ProductGateDecision("REJECT", "fewer than two independent behavior originals")
    if not wedge.problem_relevance:
        return ProductGateDecision("REJECT", "wedge is unrelated to the evidenced problem")
    if wedge.behavior_displacement == "NO_DISPLACEMENT" or (
        wedge.external_form_reentry_required is True
        and (wedge.expected_steps_removed or 0) == 0
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
    if wedge.behavior_displacement == "UNKNOWN":
        unknowns.append("whether the wedge removes a current workaround step is unknown")
    if wedge.external_form_reentry_required is None:
        unknowns.append("whether an incumbent form requires duplicate data entry is unknown")
    return ProductGateDecision(
        "DESIGN_VALIDATION", "minimum testability contract passed", tuple(unknowns)
    )
