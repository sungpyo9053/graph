from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from langgraph.graph import START, StateGraph

from src.agents.atomic import (
    analyze_root_problem,
    analyze_structural_gap_node,
    design_wedge_candidates_node,
    evaluate_asset_node,
    evaluate_expansion_node,
    evidence_context,
    research_existing_alternatives,
    select_wedge,
    trace,
)
from src.domain.models.quality import (
    ArbitrationVerdict,
    CritiqueFindings,
    DiscoveryContract,
    ExitChallenge,
    RevisionRecord,
)
from src.domain.policies.quality import (
    arbitrate_findings,
    candidate_fingerprint,
    canonical_finding_fingerprint,
    evaluate_evidence_gate,
    final_verify,
    repeated_root_finding,
)
from src.graphs.routes import (
    QUALITY_ARBITRATION_ROUTES,
    QUALITY_CRITIQUE_ROUTES,
    QUALITY_EVIDENCE_ROUTES,
    QUALITY_EXIT_ROUTES,
    QUALITY_REVISION_ROUTES,
    QUALITY_VERIFY_ROUTES,
)
from src.graphs.state import CandidateGraphState, DiscoveryCollector
from src.llm.client import (
    LLMClient,
    create_fresh_llm_client,
    generate_with_schema_retry,
    merge_call_audit,
)


def build_quality_graph(collector: DiscoveryCollector, llm: LLMClient) -> Any:
    """Domain quality loop: GATE -> CRITIQUE -> ARBITRATE -> REVISE -> VERIFY."""
    builder = StateGraph(CandidateGraphState)

    def evidence_gate(state: CandidateGraphState) -> dict:
        started, clock = datetime.now(UTC), perf_counter()
        contract = state.get("discovery_contract", DiscoveryContract())
        result = evaluate_evidence_gate(dict(state), contract)
        return {
            "discovery_contract": contract,
            "quality_started_at": state.get("quality_started_at", started),
            "quality_model_calls": int(state.get("quality_model_calls", 0)),
            "exit_challenge_round": int(state.get("exit_challenge_round", 0)),
            "evidence_gate": result,
            "next_route": result.next_route,
            "visited_nodes": ["evidence_gate"],
            "trace": [trace("evidence_gate", started, clock, result.reason, actual_route=result.next_route, route_reason=result.reason)],
        }

    async def cold_critique(state: CandidateGraphState) -> dict:
        started, clock = datetime.now(UTC), perf_counter()
        contract = state["discovery_contract"]
        limit_reason = _quality_limit_reason(state, contract)
        if limit_reason:
            return _quality_limit_hold("cold_critique", started, clock, limit_reason)
        round_number = int(state.get("critique_round", 0)) + 1
        if round_number > contract.max_critique_rounds:
            return {
                "next_route": "hold",
                "visited_nodes": ["cold_critique"],
                "trace": [trace("cold_critique", started, clock, "critique limit exceeded")],
            }
        fresh = create_fresh_llm_client(llm)
        try:
            result = await generate_with_schema_retry(
                fresh,
                task="cold_critique",
                input_data=_review_packet(state),
                output_model=CritiqueFindings,
                metadata={
                    "prompt_version": "cold-critique-v1",
                    "candidate_id": state["cluster"].cluster_id,
                    "fresh_ephemeral_session": True,
                    "prior_critique_included": False,
                },
            )
        finally:
            merge_call_audit(llm, fresh)
        previous = list(state.get("critique_findings", []))
        history = [*state.get("finding_history", []), *result.findings]
        records = list(state.get("revision_records", []))
        new_categories = {item.category for item in result.findings}
        if records:
            latest = records[-1]
            resolved = [item.finding_id for item in previous if item.category not in new_categories]
            records[-1] = latest.model_copy(update={"resolved_finding_ids": resolved})
        route = "arbitrate"
        detail = f"findings={len(result.findings)}"
        return {
            "critique_findings": result.findings,
            "finding_history": history,
            "revision_records": records,
            "critique_round": round_number,
            "quality_model_calls": int(state.get("quality_model_calls", 0)) + 1,
            "next_route": route,
            "visited_nodes": ["cold_critique"],
            "trace": [trace("cold_critique", started, clock, detail, suggested_route=result.decision, actual_route=route, route_reason=detail)],
        }

    def arbitrate(state: CandidateGraphState) -> dict:
        started, clock = datetime.now(UTC), perf_counter()
        critic_findings = state.get("critique_findings", [])
        results, route = arbitrate_findings(critic_findings, dict(state))
        suggested_route = critic_findings[0].recommended_route if critic_findings else None
        fingerprints = [
            canonical_finding_fingerprint(finding, result.actual_route)
            for finding, result in zip(critic_findings, results, strict=True)
            if finding.severity == "BLOCKING"
            and result.verdict
            in {
                ArbitrationVerdict.VALID,
                ArbitrationVerdict.NEEDS_MORE_EVIDENCE,
                ArbitrationVerdict.ENVIRONMENTAL_LIMIT,
            }
        ]
        previous_fingerprints = state.get("blocking_finding_fingerprints", [])
        non_converging = repeated_root_finding(
            fingerprints,
            previous_fingerprints,
            state["discovery_contract"].repeated_root_finding_limit,
        )
        if non_converging:
            route = "hold"
        elif state.get("exit_challenger_pending") and route == "final_verify":
            # This candidate already passed final_verify. A challenger finding that
            # code arbitration rejects must finish instead of re-running challenger.
            route = "report_complete"
        reason = (
            "NON_CONVERGING_LOOP: same canonical blocking finding repeated"
            if non_converging
            else "code arbitration overrides critic recommendation"
        )
        testable_unknowns = [
            finding.reason
            for finding, result in zip(critic_findings, results, strict=True)
            if result.actual_route == "validation_hypothesis"
        ]
        validation_plan = state.get("validation_plan")
        if testable_unknowns and validation_plan is not None:
            validation_plan = validation_plan.model_copy(
                update={
                    "hypothesis": (
                        f"{validation_plan.hypothesis}; Cold Critique testable unknowns: "
                        f"{'; '.join(testable_unknowns)}"
                    )
                }
            )
        return {
            "arbitration_results": results,
            "next_route": route,
            "blocking_finding_fingerprints": [*previous_fingerprints, *fingerprints],
            "validation_hypotheses": [
                *state.get("validation_hypotheses", []),
                *testable_unknowns,
            ],
            "validation_plan": validation_plan,
            "exit_challenger_pending": False,
            "visited_nodes": ["arbitrate"],
            "trace": [
                trace(
                    "arbitrate",
                    started,
                    clock,
                    f"suggestions_not_copied=true actual_route={route} {reason}",
                    suggested_route=suggested_route,
                    actual_route=route,
                    route_reason=reason,
                )
            ],
        }

    async def revise(state: CandidateGraphState) -> dict:
        started, clock = datetime.now(UTC), perf_counter()
        route = state["next_route"]
        contract = state["discovery_contract"]
        revision_round = int(state.get("revision_round", 0)) + 1
        limit_reason = _quality_limit_reason(state, contract)
        if limit_reason:
            return _quality_limit_hold(route, started, clock, limit_reason)
        if revision_round > contract.max_revision_rounds:
            return {
                "next_route": "hold",
                "visited_nodes": [route],
                "trace": [trace(route, started, clock, "revision limit exceeded")],
            }
        before = candidate_fingerprint(dict(state))
        update: dict[str, Any] = {}
        if route == "root_problem_analysis":
            update.update(
                await analyze_root_problem(state["cluster"], state["candidate_prefix"], llm)
            )
        elif route == "market_research":
            market_update = await research_existing_alternatives(
                collector,
                state["cluster"],
                state["request"],
                state["freshness"],
                state["candidate_prefix"],
            )
            update.update(market_update)
            update.update(
                await analyze_structural_gap_node(
                    state["cluster"],
                    market_update["market_documents"],
                    state["candidate_prefix"],
                    llm,
                )
            )
        elif route == "wedge_design":
            wedge_update = await design_wedge_candidates_node(
                state["cluster"], state["candidate_prefix"], llm
            )
            update.update(wedge_update)
            update.update(select_wedge(wedge_update["wedge_candidates"], state["candidate_prefix"]))
        elif route == "asset_expansion_analysis":
            merged = {**dict(state), **update}
            asset_update = await evaluate_asset_node(merged, state["candidate_prefix"], llm)
            update.update(asset_update)
            update.update(
                await evaluate_expansion_node(
                    {**dict(state), **update}, state["candidate_prefix"], llm
                )
            )
        merged_state = {**dict(state), **update}
        after = candidate_fingerprint(merged_state)
        changed = before != after
        addressed = [
            item.finding_id
            for item in state.get("arbitration_results", [])
            if item.actual_route == route
        ]
        record = RevisionRecord(
            revision_round=revision_round,
            route=route,
            before_fingerprint=before,
            after_fingerprint=after,
            addressed_finding_ids=addressed,
            resolved_finding_ids=[],
            changed=changed,
        )
        return {
            **update,
            "revision_round": revision_round,
            "quality_model_calls": int(state.get("quality_model_calls", 0)) + 1,
            "exit_challenger_pending": False,
            "revision_records": [*state.get("revision_records", []), record],
            "next_route": "evidence_gate" if changed else "hold",
            "visited_nodes": [route],
            "trace": [
                trace(
                    route,
                    started,
                    clock,
                    f"changed={str(changed).lower()} return=evidence_gate",
                )
            ],
        }

    def verify(state: CandidateGraphState) -> dict:
        started, clock = datetime.now(UTC), perf_counter()
        result = final_verify(dict(state), state["discovery_contract"])
        return {
            "verification_result": result,
            "next_route": result.next_route,
            "visited_nodes": ["final_verify"],
            "trace": [trace("final_verify", started, clock, result.reason, actual_route=result.next_route, route_reason=result.reason)],
        }

    async def exit_challenger(state: CandidateGraphState) -> dict:
        started, clock = datetime.now(UTC), perf_counter()
        contract = state["discovery_contract"]
        round_number = int(state.get("exit_challenge_round", 0)) + 1
        limit_reason = _quality_limit_reason(state, contract)
        if round_number > contract.max_exit_challenge_rounds:
            limit_reason = (
                f"exit challenger limit exceeded: {round_number - 1}/"
                f"{contract.max_exit_challenge_rounds}"
            )
        if limit_reason:
            return _quality_limit_hold("exit_challenger", started, clock, limit_reason)
        fresh = create_fresh_llm_client(llm)
        try:
            result = await generate_with_schema_retry(
                fresh,
                task="exit_challenger",
                input_data=_review_packet(state),
                output_model=ExitChallenge,
                metadata={
                    "prompt_version": "exit-challenger-v1",
                    "candidate_id": state["cluster"].cluster_id,
                    "fresh_ephemeral_session": True,
                    "prior_critique_included": False,
                },
            )
        finally:
            merge_call_audit(llm, fresh)
        if (
            result.blocking_finding is None
            or result.blocking_finding.severity != "BLOCKING"
        ):
            route = "report_complete"
            findings = []
            pending = False
        else:
            route = "arbitrate"
            findings = [result.blocking_finding]
            pending = True
        return {
            "critique_findings": findings,
            "finding_history": [*state.get("finding_history", []), *findings],
            "next_route": route,
            "exit_challenge_round": round_number,
            "quality_model_calls": int(state.get("quality_model_calls", 0)) + 1,
            "exit_challenger_pending": pending,
            "visited_nodes": ["exit_challenger"],
            "trace": [
                trace(
                    "exit_challenger",
                    started,
                    clock,
                    f"new_blocking={str(bool(findings)).lower()} route={route}",
                    suggested_route=result.decision,
                    actual_route=route,
                    route_reason=result.decision_reason,
                )
            ],
        }

    builder.add_node("evidence_gate", evidence_gate)
    builder.add_node("cold_critique", cold_critique)
    builder.add_node("arbitrate", arbitrate)
    builder.add_node("targeted_revision", revise)
    builder.add_node("final_verify", verify)
    builder.add_node("exit_challenger", exit_challenger)
    builder.add_edge(START, "evidence_gate")
    builder.add_conditional_edges(
        "evidence_gate",
        lambda state: state.get("next_route", "hold"),
        QUALITY_EVIDENCE_ROUTES,
    )
    builder.add_conditional_edges(
        "cold_critique",
        lambda state: state.get("next_route", "hold"),
        QUALITY_CRITIQUE_ROUTES,
    )
    revision_routes = {
        "root_problem_analysis",
        "market_research",
        "wedge_design",
        "asset_expansion_analysis",
    }
    builder.add_conditional_edges(
        "arbitrate",
        lambda state: (
            "targeted_revision"
            if state.get("next_route") in revision_routes
            else state.get("next_route", "hold")
        ),
        QUALITY_ARBITRATION_ROUTES,
    )
    builder.add_conditional_edges(
        "targeted_revision",
        lambda state: state.get("next_route", "hold"),
        QUALITY_REVISION_ROUTES,
    )
    builder.add_conditional_edges(
        "final_verify",
        lambda state: state.get("next_route", "hold"),
        QUALITY_VERIFY_ROUTES,
    )
    builder.add_conditional_edges(
        "exit_challenger",
        lambda state: state.get("next_route", "hold"),
        QUALITY_EXIT_ROUTES,
    )
    return builder.compile()


def _quality_limit_reason(
    state: CandidateGraphState, contract: DiscoveryContract
) -> str | None:
    calls = int(state.get("quality_model_calls", 0))
    if calls >= contract.max_quality_model_calls:
        return f"quality model call limit reached: {calls}/{contract.max_quality_model_calls}"
    started = state.get("quality_started_at")
    if isinstance(started, datetime):
        elapsed_minutes = (datetime.now(UTC) - started).total_seconds() / 60
        if elapsed_minutes >= contract.max_quality_elapsed_minutes:
            return (
                "quality elapsed time limit reached: "
                f"{elapsed_minutes:.1f}/{contract.max_quality_elapsed_minutes:.1f} minutes"
            )
    return None


def _quality_limit_hold(
    node: str, started: datetime, clock: float, reason: str
) -> dict[str, Any]:
    return {
        "next_route": "hold",
        "visited_nodes": [node],
        "trace": [
            trace(
                node,
                started,
                clock,
                reason,
                actual_route="hold",
                route_reason=reason,
            )
        ],
    }


def _review_packet(state: CandidateGraphState) -> dict[str, Any]:
    cluster = state["cluster"]
    market = state.get("market")
    selected_wedge = state.get("selected_wedge")
    validation_plan = state.get("validation_plan")
    return {
        "candidate": {
            "persona": cluster.persona,
            "root_problem": cluster.root_problem,
            "pain": state.get("pain_summary"),
            "market": market.model_dump(mode="json") if market is not None else None,
            "selected_wedge": selected_wedge.model_dump(mode="json")
            if selected_wedge is not None
            else None,
            "assets": [item.model_dump(mode="json") for item in state.get("assets", [])],
            "expansion_paths": [
                item.model_dump(mode="json") for item in state.get("expansion_paths", [])
            ],
            "validation": validation_plan.model_dump(mode="json")
            if validation_plan is not None
            else None,
        },
        "evidence": evidence_context(cluster),
        "instruction": "find at most the strongest actionable issues; do not assign scores or mutate status",
    }
