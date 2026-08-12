from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.domain.models.discovery import (
    BehaviorObservation,
    DiscoveryLane,
    DiscoveryMode,
    DiscoveryRequest,
    MarketStructureResearch,
    ProblemCluster,
)
from src.domain.models.quality import CritiqueCategory, CritiqueFinding, DiscoveryContract
from src.domain.models.schemas import (
    Evidence,
    EvidenceGrade,
    EvidenceSourceRole,
    Score,
    ValidationPlan,
    WedgeCandidate,
)
from src.domain.policies.product import evaluate_product_testability
from src.domain.policies.quality import (
    arbitrate_findings,
    canonical_finding_fingerprint,
    evaluate_evidence_gate,
    final_verify,
    repeated_root_finding,
)
from src.graphs.quality.graph import build_quality_graph
from src.graphs.state import CandidateGraphState
from src.llm.client import DeterministicFakeLLM
from tests.fixture_collector import FixtureDiscoveryCollector


def _evidence(index: int, *, fixture: bool = True) -> Evidence:
    return Evidence(
        signal_id=f"evidence-{index}",
        grade=EvidenceGrade.B,
        claim="a repeated behavior and workaround were observed",
        behavior_observed="the user repeats the manual check",
        workaround_observed="the user records the result in a spreadsheet",
        source_type="community",
        source_name=f"source-{index}",
        author_key=f"author-{index}",
        original_item_key=f"original-{index}",
        original_text=f"verified quote {index}",
        source_url=f"https://example.com/original-{index}",
        published_at=datetime(2026, 1, index, tzinfo=UTC),
        collected_at=datetime(2026, 8, 1, tzinfo=UTC),
        independence_key=f"independent-{index}",
        freshness_score=1,
        is_fixture=fixture,
        access_level="ORIGINAL_VERIFIED",
        accessed_at=datetime(2026, 8, 1, tzinfo=UTC),
        source_role=EvidenceSourceRole.FIRSTHAND_BEHAVIOR,
        behavior_claim_verified=True,
    )


def _state(*, fixture: bool = True, data_access: bool = True) -> CandidateGraphState:
    evidence = [_evidence(1, fixture=fixture), _evidence(2, fixture=fixture)]
    observations = [
        BehaviorObservation(
            theme="manual-work",
            persona="a user observed in the originals",
            repeated_behavior=item.behavior_observed,
            pain="time loss",
            frequency="repeated; exact frequency unknown",
            measurable_loss="unknown",
            workaround=item.workaround_observed or "",
            evidence=item,
        )
        for item in evidence
    ]
    cluster = ProblemCluster(
        cluster_id="cluster-1",
        theme="manual-work",
        persona="a user observed in the originals",
        root_problem="the state must be reconstructed from fragmented sources",
        observations=observations,
        independent_evidence=evidence,
        problem_strength=Score(value=15, max_points=15, rationale="two sources"),
        repetition=Score(value=15, max_points=15, rationale="repeated behavior"),
        workaround_strength=Score(value=15, max_points=15, rationale="workaround"),
        preliminary_score=45,
    )
    wedge = WedgeCandidate(
        name="one-case result",
        approach_type="single_case_decision",
        target_user=cluster.persona,
        buyer="unknown",
        user_input="one case",
        core_process="normalize supplied evidence",
        expected_output="one sourced result",
        switching_reason="remove one manual reconstruction",
        switching_cost="submit one case",
        time_to_first_value="first result",
        solo_first_user_value=True,
        acquisition_channel="the observed community",
        monetization_hypothesis="unknown",
        required_data="user-provided evidence",
        data_access_feasible=data_access,
        complexity="LOW",
    )
    return CandidateGraphState(
        cluster=cluster,
        request=DiscoveryRequest(mode=DiscoveryMode.OPEN),
        freshness="2024-08-01to2026-08-01",
        candidate_prefix="candidate-1:cluster-1",
        live_run=not fixture,
        root_problem=cluster.root_problem,
        pain_summary="time loss",
        market=MarketStructureResearch(
            structural_gap="causal gap remains unknown",
            why_unsolved="unknown",
        ),
        selected_wedge=wedge,
        wedge_candidates=[wedge],
        assets=[],
        expansion_paths=[],
        validation_plan=ValidationPlan(
            hypothesis="the workaround can be displaced",
            target_user=cluster.persona,
            method="manual concierge test",
            duration_days=7,
            success_criterion="2 of 5 repeat use",
            failure_criterion="fewer than 2 repeat use",
            estimated_cost_usd=0,
            next_action_if_pass="interview repeat users",
            next_action_if_fail="reject",
        ),
        discovery_contract=DiscoveryContract(),
        critique_findings=[],
        finding_history=[],
        arbitration_results=[],
        revision_records=[],
        critique_round=0,
        revision_round=0,
        visited_nodes=[],
        trace=[],
    )


def _finding(
    category: CritiqueCategory,
    *,
    finding_id: str = "finding-1",
    route: str = "report_complete",
) -> CritiqueFinding:
    return CritiqueFinding(
        finding_id=finding_id,
        category=category,
        severity="BLOCKING",
        claim="a blocking issue is alleged",
        affected_claim="first-user value",
        root_cause="the user must perform the full workaround before receiving output",
        evidence_ids=["evidence-1"],
        reason="structured critic reason",
        recommended_route=route,  # type: ignore[arg-type]
    )


def test_code_arbitration_rejects_false_positive_and_selects_exact_routes() -> None:
    state = _state()
    results, route = arbitrate_findings([_finding(CritiqueCategory.WEAK_EVIDENCE)], state)
    assert results[0].verdict == "FALSE_POSITIVE"
    assert route == "final_verify"
    assert results[0].actual_route != "report_complete"

    one_source = _state()
    one_source["cluster"] = one_source["cluster"].model_copy(
        update={"independent_evidence": one_source["cluster"].independent_evidence[:1]}
    )
    _, evidence_route = arbitrate_findings(
        [_finding(CritiqueCategory.WEAK_EVIDENCE)], one_source
    )
    _, wedge_route = arbitrate_findings(
        [_finding(CritiqueCategory.WEAK_WEDGE)], state
    )
    assert evidence_route == "collect_more"
    assert wedge_route == "wedge_design"


def test_contract_blocks_fixture_contamination_and_inaccessible_high_score() -> None:
    live_fixture = _state()
    live_fixture["live_run"] = True
    gate = evaluate_evidence_gate(live_fixture, DiscoveryContract())
    assert gate.passed is False
    assert gate.next_route == "reject"
    assert next(check for check in gate.checks if check.name == "fixture_free_live").passed is False

    inaccessible = _state(data_access=False)
    verified = final_verify(inaccessible, DiscoveryContract())
    assert verified.passed is False
    assert verified.next_route == "hold"
    assert next(check for check in verified.checks if check.name == "data_access_feasible").passed is False


def test_evidence_gate_rejects_procedural_guides_as_user_behavior() -> None:
    state = _state(fixture=False)
    guides = [
        item.model_copy(
            update={
                "source_role": EvidenceSourceRole.PROCEDURAL_GUIDE,
                "behavior_claim_verified": False,
            }
        )
        for item in state["cluster"].independent_evidence
    ]
    state["cluster"] = state["cluster"].model_copy(
        update={"independent_evidence": guides}
    )

    gate = evaluate_evidence_gate(state, DiscoveryContract())

    assert gate.passed is False
    assert gate.next_route == "collect_more"
    count = next(
        check for check in gate.checks
        if check.name == "minimum_independent_behavior_evidence"
    )
    assert count.passed is False
    assert "independent evidence=0" in count.reason


def test_product_unknowns_move_to_validation_instead_of_hold() -> None:
    state = _state()
    decision = evaluate_product_testability(state["cluster"], state["selected_wedge"])
    assert decision.route == "DESIGN_VALIDATION"
    assert "asset value is unvalidated" in decision.unknowns
    assert "switching behavior is unvalidated" in decision.unknowns


def test_product_holds_inaccessible_data_and_rejects_weak_behavior_evidence() -> None:
    inaccessible = _state(data_access=False)
    assert (
        evaluate_product_testability(
            inaccessible["cluster"], inaccessible["selected_wedge"]
        ).route
        == "HOLD"
    )
    weak = _state()
    weak["cluster"] = weak["cluster"].model_copy(
        update={"independent_evidence": weak["cluster"].independent_evidence[:1]}
    )
    assert (
        evaluate_product_testability(weak["cluster"], weak["selected_wedge"]).route
        == "REJECT"
    )


def test_product_rejects_unrelated_wedge_and_holds_impossible_experiment() -> None:
    state = _state()
    unrelated = state["selected_wedge"].model_copy(update={"problem_relevance": False})
    assert evaluate_product_testability(state["cluster"], unrelated).route == "REJECT"
    impossible = state["selected_wedge"].model_copy(
        update={"manual_validation_feasible": False}
    )
    assert evaluate_product_testability(state["cluster"], impossible).route == "HOLD"


def test_product_rejects_wedge_that_duplicates_incumbent_form_without_removing_steps() -> None:
    state = _state()
    no_displacement = state["selected_wedge"].model_copy(
        update={
            "behavior_displacement": "NO_DISPLACEMENT",
            "expected_steps_removed": 0,
            "external_form_reentry_required": True,
        }
    )

    decision = evaluate_product_testability(state["cluster"], no_displacement)

    assert decision.route == "REJECT"
    assert "does not remove or consolidate" in decision.reason


def test_unknown_displacement_is_validation_hypothesis_not_automatic_hold() -> None:
    state = _state()
    unknown = state["selected_wedge"].model_copy(
        update={
            "behavior_displacement": "UNKNOWN",
            "expected_steps_removed": None,
            "external_form_reentry_required": None,
        }
    )

    decision = evaluate_product_testability(state["cluster"], unknown)

    assert decision.route == "DESIGN_VALIDATION"
    assert any("workaround step" in item for item in decision.unknowns)


def test_final_verify_blocks_known_no_displacement() -> None:
    state = _state()
    state["selected_wedge"] = state["selected_wedge"].model_copy(
        update={
            "behavior_displacement": "NO_DISPLACEMENT",
            "expected_steps_removed": 0,
            "external_form_reentry_required": True,
        }
    )

    result = final_verify(state, DiscoveryContract())

    assert result.passed is False
    assert result.next_route == "hold"
    assert next(
        check for check in result.checks
        if check.name == "behavior_displacement_not_disproven"
    ).passed is False


def test_behavior_redesign_gate_does_not_require_pain_or_workaround_displacement() -> None:
    state = _state()
    evidence = [
        item.model_copy(update={"workaround_observed": None})
        for item in state["cluster"].independent_evidence
    ]
    observations = [
        item.model_copy(
            update={
                "lane": DiscoveryLane.BEHAVIOR_REDESIGN,
                "workaround": "not applicable: existing behavior is the substrate",
                "evidence": evidence[index],
            }
        )
        for index, item in enumerate(state["cluster"].observations)
    ]
    state["cluster"] = state["cluster"].model_copy(
        update={
            "lane": DiscoveryLane.BEHAVIOR_REDESIGN,
            "observations": observations,
            "independent_evidence": evidence,
        }
    )
    state["selected_wedge"] = state["selected_wedge"].model_copy(
        update={
            "behavior_displacement": "NO_DISPLACEMENT",
            "instant_visible_result": True,
            "ten_second_demo": True,
            "repeat_trigger": "the visible territory changes after every run",
            "social_loop": "friends compare territories",
            "network_amplification": True,
        }
    )

    gate = evaluate_evidence_gate(state, DiscoveryContract())
    product = evaluate_product_testability(state["cluster"], state["selected_wedge"])
    verified = final_verify(state, DiscoveryContract())

    assert gate.passed is True
    assert product.route == "DESIGN_VALIDATION"
    assert verified.passed is True


def test_wild_bet_uses_validation_plan_cost_for_cheap_bounded_gate() -> None:
    state = _state()
    evidence = state["cluster"].independent_evidence[:1]
    state["cluster"] = state["cluster"].model_copy(
        update={
            "lane": DiscoveryLane.WILD_BET,
            "independent_evidence": evidence,
            "observations": state["cluster"].observations[:1],
        }
    )
    state["selected_wedge"] = state["selected_wedge"].model_copy(
        update={"validation_cost_usd": None}
    )

    assert evaluate_evidence_gate(state, DiscoveryContract()).passed is True
    assert final_verify(state, DiscoveryContract()).passed is True

    state["validation_plan"] = state["validation_plan"].model_copy(
        update={"estimated_cost_usd": 500}
    )
    assert final_verify(state, DiscoveryContract()).passed is False


def test_delight_network_amplification_unknown_is_validation_hypothesis_not_hold() -> None:
    state = _state()
    state["cluster"] = state["cluster"].model_copy(
        update={"lane": DiscoveryLane.BEHAVIOR_REDESIGN}
    )
    state["selected_wedge"] = state["selected_wedge"].model_copy(
        update={
            "instant_visible_result": True,
            "ten_second_demo": True,
            "repeat_trigger": "each completed ritual adds a visible tile",
            "social_loop": "friends can compare selected tiles",
            "network_amplification": False,
        }
    )

    product = evaluate_product_testability(state["cluster"], state["selected_wedge"])
    verified = final_verify(state, DiscoveryContract())

    assert "whether additional participants amplify the delight loop" in product.unknowns
    assert verified.passed is True


def test_delight_arbitration_does_not_require_pain_displacement_or_verified_expansion() -> None:
    state = _state()
    state["cluster"] = state["cluster"].model_copy(
        update={"lane": DiscoveryLane.BEHAVIOR_REDESIGN}
    )
    state["selected_wedge"] = state["selected_wedge"].model_copy(
        update={
            "instant_visible_result": True,
            "repeat_trigger": "every run changes the visible territory",
            "ten_second_demo": True,
            "social_loop": "friends compare territories",
            "network_amplification": True,
        }
    )
    no_displacement = _finding(CritiqueCategory.NO_BEHAVIOR_CHANGE)
    fake_asset = _finding(
        CritiqueCategory.FAKE_ASSET,
        finding_id="asset-finding",
    )

    results, route = arbitrate_findings(
        [no_displacement, fake_asset], state
    )

    assert results[0].verdict == "FALSE_POSITIVE"
    assert results[1].actual_route == "validation_hypothesis"
    assert route == "final_verify"


def test_same_blocking_root_finding_stops_after_two_rounds() -> None:
    first = _finding(CritiqueCategory.WEAK_WEDGE, finding_id="first")
    second = _finding(CritiqueCategory.WEAK_WEDGE, finding_id="second")
    first_key = canonical_finding_fingerprint(first, "wedge_design")
    second_key = canonical_finding_fingerprint(second, "wedge_design")
    assert repeated_root_finding([second_key], [first_key], limit=2) is True


def test_same_category_with_different_root_cause_does_not_stop_loop() -> None:
    first = _finding(CritiqueCategory.WEAK_WEDGE, finding_id="first")
    second = _finding(CritiqueCategory.WEAK_WEDGE, finding_id="second").model_copy(
        update={
            "affected_claim": "input burden",
            "root_cause": "data entry takes longer than the current workaround",
            "evidence_ids": ["evidence-2"],
        }
    )
    first_key = canonical_finding_fingerprint(first, "wedge_design")
    second_key = canonical_finding_fingerprint(second, "wedge_design")
    assert first_key != second_key
    assert repeated_root_finding([second_key], [first_key], limit=2) is False


@pytest.mark.asyncio
async def test_revision_returns_through_evidence_gate_then_nonconverging_loop_stops() -> None:
    response = {
        "observed_facts": ["evidence is present"],
        "inferences": ["the wedge may be too broad"],
        "assumptions": [],
        "unknowns": [],
        "decision": "REVISE",
        "decision_reason": "wedge issue",
        "findings": [
            _finding(CritiqueCategory.WEAK_WEDGE).model_dump(mode="json")
        ],
    }
    llm = DeterministicFakeLLM({"cold_critique": response})
    result = await build_quality_graph(FixtureDiscoveryCollector(), llm).ainvoke(_state())
    nodes = [item["node"] for item in result["trace"]]
    assert nodes.count("evidence_gate") == 2
    assert "wedge_design" in nodes
    assert result["revision_records"][0].route == "wedge_design"
    assert result["next_route"] == "hold"
    assert any("NON_CONVERGING_LOOP" in item["detail"] for item in result["trace"])


@pytest.mark.asyncio
async def test_exit_challenger_new_blocking_finding_prevents_completion() -> None:
    blocking = _finding(CritiqueCategory.SAFETY_RISK, route="report_complete")
    llm = DeterministicFakeLLM(
        {
            "exit_challenger": {
                "observed_facts": ["a new safety issue is grounded in evidence"],
                "inferences": [],
                "assumptions": [],
                "unknowns": [],
                "decision": "BLOCK",
                "decision_reason": "new blocking finding",
                "blocking_finding": blocking.model_dump(mode="json"),
            }
        }
    )
    result = await build_quality_graph(FixtureDiscoveryCollector(), llm).ainvoke(_state())
    nodes = [item["node"] for item in result["trace"]]
    assert "exit_challenger" in nodes
    assert nodes[-1] == "arbitrate"
    assert result["next_route"] == "reject"
    assert result["next_route"] != blocking.recommended_route


@pytest.mark.asyncio
async def test_exit_challenger_testable_unknown_completes_without_reentry() -> None:
    testable = _finding(CritiqueCategory.NO_BEHAVIOR_CHANGE).model_copy(
        update={"severity": "TESTABLE_UNKNOWN"}
    )
    llm = DeterministicFakeLLM(
        {
            "exit_challenger": {
                "observed_facts": ["the behavior is not yet observed after the wedge"],
                "inferences": [],
                "assumptions": [],
                "unknowns": ["switching behavior"],
                "decision": "TEST",
                "decision_reason": "this belongs in validation, not a completion loop",
                "blocking_finding": testable.model_dump(mode="json"),
            }
        }
    )
    result = await build_quality_graph(FixtureDiscoveryCollector(), llm).ainvoke(_state())
    assert result["next_route"] == "report_complete"
    assert [call["task"] for call in llm.calls].count("exit_challenger") == 1


@pytest.mark.asyncio
async def test_exit_challenger_false_positive_does_not_run_challenger_again() -> None:
    unsupported = _finding(CritiqueCategory.WRONG_ROOT_PROBLEM).model_copy(
        update={"evidence_ids": ["not-a-candidate-evidence-id"]}
    )
    llm = DeterministicFakeLLM(
        {
            "exit_challenger": {
                "observed_facts": [],
                "inferences": ["a blocker was proposed"],
                "assumptions": [],
                "unknowns": [],
                "decision": "BLOCK",
                "decision_reason": "the cited evidence is not in the candidate",
                "blocking_finding": unsupported.model_dump(mode="json"),
            }
        }
    )
    result = await build_quality_graph(FixtureDiscoveryCollector(), llm).ainvoke(_state())
    assert result["next_route"] == "report_complete"
    assert result["arbitration_results"][0].verdict == "FALSE_POSITIVE"
    assert [call["task"] for call in llm.calls].count("exit_challenger") == 1


@pytest.mark.asyncio
async def test_quality_model_call_limit_holds_before_exit_challenger() -> None:
    state = _state()
    state["discovery_contract"] = DiscoveryContract(max_quality_model_calls=1)
    llm = DeterministicFakeLLM()
    result = await build_quality_graph(FixtureDiscoveryCollector(), llm).ainvoke(state)
    assert result["next_route"] == "hold"
    assert [call["task"] for call in llm.calls] == ["cold_critique"]
    assert any("quality model call limit reached" in item["detail"] for item in result["trace"])


@pytest.mark.asyncio
async def test_testable_unknown_updates_validation_plan_without_hold() -> None:
    finding = _finding(CritiqueCategory.NO_BEHAVIOR_CHANGE).model_copy(
        update={
            "severity": "TESTABLE_UNKNOWN",
            "reason": "actual switching behavior has not yet been observed",
        }
    )
    response = {
        "observed_facts": ["the workaround exists"],
        "inferences": [],
        "assumptions": [],
        "unknowns": ["switching behavior"],
        "decision": "TEST",
        "decision_reason": "move the unknown into validation",
        "findings": [finding.model_dump(mode="json")],
    }
    result = await build_quality_graph(
        FixtureDiscoveryCollector(),
        DeterministicFakeLLM({"cold_critique": response}),
    ).ainvoke(_state())
    assert result["next_route"] == "report_complete"
    assert "actual switching behavior" in result["validation_plan"].hypothesis
    assert result["arbitration_results"][0].actual_route == "validation_hypothesis"


@pytest.mark.asyncio
async def test_only_contract_complete_path_reaches_report_completion() -> None:
    llm = DeterministicFakeLLM()
    result = await build_quality_graph(FixtureDiscoveryCollector(), llm).ainvoke(_state())
    assert result["verification_result"].passed is True
    assert result["next_route"] == "report_complete"
    cold = next(call for call in llm.calls if call["task"] == "cold_critique")
    challenger = next(call for call in llm.calls if call["task"] == "exit_challenger")
    assert cold["metadata"]["fresh_ephemeral_session"] is True
    assert cold["metadata"]["prior_critique_included"] is False
    assert "critique_findings" not in cold["input_data"]
    assert challenger["metadata"]["fresh_ephemeral_session"] is True
    assert "critique_findings" not in challenger["input_data"]
