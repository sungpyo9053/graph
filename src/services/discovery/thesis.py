from __future__ import annotations

from urllib.parse import urlparse

from src.domain.models.discovery import DiscoveryLane, MarketStructureResearch, ProblemCluster
from src.domain.models.schemas import (
    AccumulatingAsset,
    ExpansionPath,
    FinalVerdict,
    ProblemWedgeExpansionThesis,
    Score,
    ThesisEvidence,
    ValidationPlan,
    WedgeCandidate,
    unknown_score,
)
from src.domain.scoring.scoring import grounded_score

FOUNDER_TERMS = {
    "software": 5,
    "system": 5,
    "operations": 5,
    "status": 5,
    "routing": 5,
    "logistics": 5,
    "reliability": 5,
    "observability": 5,
    "data": 4,
    "finance": 3,
    "care": 2,
    "compliance": 3,
    "property": 3,
}


def build_thesis(
    cluster: ProblemCluster,
    market: MarketStructureResearch,
    *,
    scores_override: dict[str, Score] | None = None,
    selected_wedge: WedgeCandidate | None = None,
    assets_override: list[AccumulatingAsset] | None = None,
    expansion_override: list[ExpansionPath] | None = None,
    validation_override: ValidationPlan | None = None,
    strongest_objection_override: str | None = None,
    causal_gap_verified: bool = False,
    unknowns_override: list[str] | None = None,
) -> ProblemWedgeExpansionThesis:
    observations = cluster.observations
    evidence = cluster.independent_evidence
    frequency_values = sorted(
        {item.frequency for item in observations if item.frequency != "unknown"}
    )
    loss_values = sorted(
        {item.measurable_loss for item in observations if item.measurable_loss != "unknown"}
    )
    frequency = ", ".join(frequency_values) or "unknown"
    measurable_loss = ", ".join(loss_values) or "unknown"
    workaround = " | ".join(dict.fromkeys(item.workaround for item in observations))[:1600]
    scores = scores_override or evaluate_all_scores(cluster, market)
    total = sum(item.value for item in scores.values())
    confidence = round(sum(item.confidence for item in scores.values()) / len(scores), 3)
    wedge = selected_wedge or design_wedge(cluster)
    assets = assets_override if assets_override is not None else evaluate_assets(cluster)
    expansion_paths = (
        expansion_override
        if expansion_override is not None
        else evaluate_expansion_paths(cluster, assets)
    )
    validation = validation_override or design_validation(cluster)
    verdict = classify_candidate_verdict(
        lane=cluster.lane,
        evidence_count=len(evidence),
        total_score=total,
        market=market,
        wedge=wedge,
        assets=assets,
        expansion_paths=expansion_paths,
        causal_gap_verified=causal_gap_verified,
        behavior_ready=frequency != "unknown" and measurable_loss != "unknown",
        validation=validation,
    )
    thesis_evidence = [
        ThesisEvidence(
            original_text=item.original_text,
            source=item.source_name,
            url=str(item.source_url) if item.source_url else None,
            date=item.published_at,
            grade=item.grade,
            independence_key=item.independence_key,
            observed_fact=item.behavior_observed,
            is_fixture=item.is_fixture,
            access_level=item.access_level,
            accessed_at=item.accessed_at,
            source_role=item.source_role,
        )
        for item in evidence
    ]
    source_domains = sorted(
        {urlparse(item.url or "").hostname or "unknown" for item in thesis_evidence}
    )
    return ProblemWedgeExpansionThesis(
        discovery_lane=cluster.lane,
        idea_name=f"{cluster.theme.replace('_', ' ').replace(':', ' / ')} wedge",
        one_line_thesis=(
            f"{cluster.persona} repeats an existing behavior; test {wedge.expected_output} as a new visible meaning."
            if cluster.lane != DiscoveryLane.PROBLEM_SOLVER
            else f"{cluster.persona} faces {cluster.root_problem}; test {wedge.expected_output} as the smallest entry wedge."
        ),
        repeated_behavior=" | ".join(
            dict.fromkeys(item.repeated_behavior for item in observations)
        )[:1800],
        frequency=frequency,
        measurable_loss=measurable_loss,
        current_workaround=workaround,
        behavior_reframe=(
            cluster.root_problem
            if cluster.lane != DiscoveryLane.PROBLEM_SOLVER
            else "not applicable"
        ),
        visible_result=wedge.expected_output,
        repeat_trigger=wedge.repeat_trigger,
        social_loop=wedge.social_loop,
        surface_pain=" | ".join(dict.fromkeys(item.pain for item in observations)),
        root_problem=cluster.root_problem,
        persona=cluster.persona,
        evidence=thesis_evidence,
        existing_alternatives=market.alternatives,
        structural_gap=market.structural_gap,
        wedge_statement=wedge.expected_output,
        core_user_action=f"{wedge.user_input} → {wedge.core_process} → {wedge.expected_output}",
        switching_reason=wedge.switching_reason,
        switching_cost=wedge.switching_cost,
        time_to_first_value=wedge.time_to_first_value,
        accumulating_assets=assets,
        expansion_paths=expansion_paths,
        market_and_revenue_hypothesis=(
            "buyer and pricing are unverified; current spend is evidenced as time or workaround effort, not proven budget"
        ),
        first_user_access=(
            f"approach contributors or communities represented by verified source domains: {', '.join(source_domains)}"
        ),
        strongest_objection=strongest_objection_override or contrarian_objection(cluster, market),
        kill_conditions=_kill_conditions(cluster.lane),
        validation=validation,
        scores=scores,
        total_score=total,
        confidence=confidence,
        verdict=verdict,
        next_action=(
            f"show a ten-second behavior-reframe prototype to 10 {cluster.persona} participants and measure voluntary replay or sharing"
            if cluster.lane != DiscoveryLane.PROBLEM_SOLVER
            else f"recruit 10 {cluster.persona} participants from the verified source communities for interviews"
        ),
        unknowns=list(dict.fromkeys([
            "willingness to pay",
            "buyer identity",
            "source access and storage rights",
            *market.unknowns,
            *(unknowns_override or []),
        ])),
        assumptions=[
            "root problem is an inference from observed behavior",
            "wedge, accumulating asset, and expansion path are hypotheses",
        ],
        is_fixture=any(item.is_fixture for item in evidence),
    )


def classify_candidate_verdict(
    *,
    lane: DiscoveryLane,
    evidence_count: int,
    total_score: int,
    market: MarketStructureResearch,
    wedge: WedgeCandidate,
    assets: list[AccumulatingAsset],
    expansion_paths: list[ExpansionPath],
    causal_gap_verified: bool,
    behavior_ready: bool,
    validation: ValidationPlan,
) -> FinalVerdict:
    """Business verdict is distinct from a successfully written report."""
    del assets, expansion_paths, causal_gap_verified
    if evidence_count < 1:
        return FinalVerdict.REJECT
    if lane == DiscoveryLane.BEHAVIOR_REDESIGN:
        if (
            evidence_count >= 2
            and wedge.instant_visible_result is True
            and wedge.ten_second_demo is True
            and wedge.solo_first_user_value
            and wedge.data_access_feasible
            and wedge.repeat_trigger.strip().lower() != "unknown"
            and wedge.social_loop.strip().lower() != "unknown"
            and wedge.network_amplification is True
        ):
            return FinalVerdict.VALIDATE_DELIGHT
        if (
            wedge.validation_cost_usd is not None
            and wedge.validation_cost_usd <= 300
            and validation.duration_days <= 14
            and wedge.manual_validation_feasible
        ):
            return FinalVerdict.WILD_BET
        return FinalVerdict.HOLD
    if lane == DiscoveryLane.WILD_BET:
        if (
            wedge.validation_cost_usd is not None
            and wedge.validation_cost_usd <= 300
            and validation.duration_days <= 14
            and wedge.manual_validation_feasible
            and wedge.solo_first_user_value
        ):
            return FinalVerdict.WILD_BET
        return FinalVerdict.HOLD
    if evidence_count < 2 or not market.alternatives:
        return FinalVerdict.REJECT
    if not behavior_ready:
        return FinalVerdict.HOLD
    if total_score >= 45 and wedge.solo_first_user_value and wedge.data_access_feasible:
        return FinalVerdict.VALIDATE_PROBLEM
    return FinalVerdict.HOLD


def _kill_conditions(lane: DiscoveryLane) -> list[str]:
    if lane == DiscoveryLane.PROBLEM_SOLVER:
        return [
            "fewer than 3 of 10 interviews confirm the behavior occurs at least weekly",
            "fewer than 2 users replace at least half of the workaround during the concierge test",
            "required source access is prohibited, unstable, or unavailable",
        ]
    if lane == DiscoveryLane.BEHAVIOR_REDESIGN:
        return [
            "fewer than 3 of 10 target users understand the transformed result within ten seconds",
            "fewer than 2 of 10 voluntarily repeat or share the behavior within seven days",
            "the first user receives no visible result without inviting another person",
        ]
    return [
        "the prototype cannot be produced within 14 days and the configured cheap-test budget",
        "none of 10 exposed target users voluntarily retries, shares, or asks to keep it",
        "the experiment requires prohibited data or non-consensual external actions",
    ]


def _founder_fit(root_problem: str) -> int:
    lowered = root_problem.lower()
    return max((value for term, value in FOUNDER_TERMS.items() if term in lowered), default=2)


def design_wedge(cluster: ProblemCluster) -> WedgeCandidate:
    """Create one deliberately narrow input -> result wedge; no product suite."""
    return WedgeCandidate(
        name=f"{cluster.theme} entry wedge",
        approach_type="single_case_decision",
        target_user=cluster.persona,
        buyer="unknown",
        user_input="one user case or source",
        core_process="normalize evidence and expose unresolved exceptions",
        expected_output="one sourced next-action result for the current case",
        switching_reason="remove one repeated checking, copying, or calling step",
        switching_cost="provide the first case and verify uncertain output",
        time_to_first_value="first manually produced result during validation",
        solo_first_user_value=True,
        acquisition_channel="verified source communities",
        monetization_hypothesis="unknown until payment behavior is observed",
        required_data="user-provided case and lawfully accessible source evidence",
        data_access_feasible=True,
        problem_relevance=True,
        manual_validation_feasible=True,
        behavior_displacement="UNKNOWN",
        expected_steps_removed=None,
        external_form_reentry_required=None,
        complexity="LOW",
    )


def evaluate_structural_gap(market: MarketStructureResearch) -> Score:
    if not market.alternatives:
        return unknown_score(10, "no verified original source for existing alternatives")
    return grounded_score(
        min(6, len(market.alternatives) * 2),
        10,
        f"verified alternatives: {len(market.alternatives)}; causal structural gap remains unverified",
        min(0.6, len(market.alternatives) / 5),
    )


def evaluate_wedge_simplicity(wedge: WedgeCandidate) -> Score:
    if wedge.complexity != "LOW":
        return grounded_score(0, 10, "entry wedge is not a single low-complexity result", 0.8)
    return grounded_score(8, 10, "one user case produces one decision-relevant result", 0.55)


def evaluate_switching(
    cluster: ProblemCluster, wedge: WedgeCandidate | None = None
) -> Score:
    if cluster.lane != DiscoveryLane.PROBLEM_SOLVER:
        if wedge is None:
            return unknown_score(10, "behavior-reframe wedge has not been designed")
        signals = sum(
            (
                wedge.instant_visible_result is True,
                wedge.ten_second_demo is True,
                wedge.repeat_trigger.strip().lower() != "unknown",
                wedge.solo_first_user_value,
            )
        )
        return grounded_score(
            min(10, signals * 2),
            10,
            f"delight-loop testability signals={signals}/4; real replay and sharing remain unvalidated",
            min(0.6, signals / 8),
        )
    count = len([item for item in cluster.observations if item.workaround.strip()])
    if count == 0:
        return unknown_score(10, "no observed workaround to replace")
    return grounded_score(
        min(6, count * 2),
        10,
        f"{count} observed workaround records; actual switching remains untested",
        min(0.5, count / 6),
    )


def evaluate_assets(cluster: ProblemCluster) -> list[AccumulatingAsset]:
    return [
        AccumulatingAsset(
            asset="unknown until derived from the selected wedge and observed repeated use",
            accumulation_mechanism="each completed case may record source, state, exception, and outcome",
            strategic_value="unknown until reuse in a later case is observed",
            evidence_status="HYPOTHESIS",
        )
    ]


def evaluate_asset_score(assets: list[AccumulatingAsset]) -> Score:
    if not assets or all(item.evidence_status != "VERIFIED" for item in assets):
        return unknown_score(10, "asset accumulation is a hypothesis; no observed reuse or control")
    return grounded_score(6, 10, "verified asset is produced and reused by the entry workflow", 0.6)


def evaluate_expansion_paths(
    cluster: ProblemCluster, assets: list[AccumulatingAsset]
) -> list[ExpansionPath]:
    status = "SUPPORTED" if assets and all(item.evidence_status == "VERIFIED" for item in assets) else "UNSUPPORTED"
    return [
        ExpansionPath(
            stage=1,
            problem="unknown until an adjacent problem demonstrably reuses the controlled asset",
            asset_used=assets[0].asset if assets else "unknown",
            adjacency_reason="requires proof that the entry-workflow asset lowers the adjacent problem's cost",
            evidence_status=status,
        )
    ]


def evaluate_expansion_score(paths: list[ExpansionPath], assets: list[AccumulatingAsset]) -> Score:
    if not paths or not assets or any(item.evidence_status != "VERIFIED" for item in assets):
        return unknown_score(10, "no verified controlled asset connects the wedge to an adjacent problem")
    if any(item.evidence_status not in {"SUPPORTED", "VERIFIED"} for item in paths):
        return unknown_score(10, "expansion path is a narrative hypothesis, not asset-backed evidence")
    return grounded_score(6, 10, "verified asset reduces an adjacent problem's cost", 0.55)


def evaluate_founder_fit(cluster: ProblemCluster) -> Score:
    return grounded_score(
        _founder_fit(cluster.root_problem),
        5,
        "fit with Python/backend/systems/SRE/observability experience; cannot override evidence gates",
        0.8,
    )


def evaluate_all_scores(
    cluster: ProblemCluster, market: MarketStructureResearch
) -> dict[str, Score]:
    wedge = design_wedge(cluster)
    assets = evaluate_assets(cluster)
    paths = evaluate_expansion_paths(cluster, assets)
    return {
        "problem_strength": cluster.problem_strength,
        "repetition": cluster.repetition,
        "workaround": cluster.workaround_strength,
        "structural_gap": evaluate_structural_gap(market),
        "wedge_simplicity": evaluate_wedge_simplicity(wedge),
        "switching": evaluate_switching(cluster),
        "asset": evaluate_asset_score(assets),
        "expansion": evaluate_expansion_score(paths, assets),
        "founder_fit": evaluate_founder_fit(cluster),
    }


def contrarian_objection(
    cluster: ProblemCluster, market: MarketStructureResearch
) -> str:
    if cluster.lane == DiscoveryLane.BEHAVIOR_REDESIGN:
        return (
            "the visible reinterpretation may be briefly novel but fail to create voluntary replay or sharing"
        )
    if cluster.lane == DiscoveryLane.WILD_BET:
        return (
            "the strange concept may earn curiosity clicks without producing any repeat behavior"
        )
    if not market.alternatives:
        return "the market structure is unknown, so the claimed gap may not exist"
    return (
        "the observed workaround may be flexible enough that users will not switch, and no verified "
        "controlled accumulating asset currently supports the claimed expansion"
    )


def design_validation(cluster: ProblemCluster) -> ValidationPlan:
    if cluster.lane == DiscoveryLane.BEHAVIOR_REDESIGN:
        return ValidationPlan(
            hypothesis="the visible reinterpretation makes users voluntarily repeat or share an existing behavior",
            target_user=f"10 people already performing: {cluster.persona}",
            method="show a ten-second clickable or video prototype, then run a seven-day manual replay test",
            duration_days=7,
            success_criterion="at least 3 of 10 understand it immediately and at least 2 voluntarily replay or share",
            failure_criterion="fewer than 2 voluntarily replay or share without reminders",
            estimated_cost_usd=100,
            next_action_if_pass="test whether social participation amplifies an already useful solo loop",
            next_action_if_fail="discard the reframe without changing the underlying behavior evidence",
        )
    if cluster.lane == DiscoveryLane.WILD_BET:
        return ValidationPlan(
            hypothesis="a strange but legible reinterpretation creates unsolicited replay, sharing, or keep requests",
            target_user=f"10 people already performing: {cluster.persona}",
            method="produce one manual sample or ten-second video and expose it in the source community",
            duration_days=7,
            success_criterion="at least 2 people voluntarily retry, share, or ask to keep using it",
            failure_criterion="no voluntary retry, share, or keep request",
            estimated_cost_usd=100,
            next_action_if_pass="promote to a behavior-redesign validation with stronger evidence",
            next_action_if_fail="reject the wild bet after the bounded test",
        )
    return ValidationPlan(
        hypothesis="target users will replace at least half of the observed workaround with the wedge output",
        target_user=f"10 people matching: {cluster.persona}",
        method="problem interviews followed by a seven-day manual concierge using user-provided cases",
        duration_days=7,
        success_criterion="at least 3 of 10 users reduce the workaround by 50% and request continued use",
        failure_criterion="fewer than 2 users reduce the workaround or no user requests continued use",
        estimated_cost_usd=100,
        next_action_if_pass="verify that repeated use creates a reusable controlled asset",
        next_action_if_fail="stop and revisit the root problem or wedge",
    )
