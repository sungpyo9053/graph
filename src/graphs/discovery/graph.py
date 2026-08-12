from __future__ import annotations

import asyncio
from collections import Counter
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, cast

from langgraph.graph import END, START, StateGraph

from src.agents.atomic import (
    collect_behavior_sources,
    deduplicate_root_problems,
    detect_workarounds,
    normalize_evidence,
    plan_queries,
    review_problem_evidence,
    trace,
)
from src.domain.models.discovery import (
    CandidateQualityAudit,
    DiscoveryEvent,
    DiscoveryPortfolio,
    LLMCallAudit,
    PortfolioCandidate,
    PublicDocument,
    SourceAuditEntry,
)
from src.domain.policies.duplicates import jaccard
from src.graphs.candidate import (
    build_candidate_finalization_graph,
    build_candidate_research_graph,
)
from src.graphs.routes import DISCOVERY_ROUTES
from src.graphs.state import CandidateGraphState, DiscoveryCollector, PortfolioGraphState
from src.llm.client import LLMClient, LLMError
from src.observability.heartbeat import reset_invocation_context, set_invocation_context
from src.services.discovery.market import (
    select_balanced_top_candidates,
    select_distinct_top_candidates,
)


def build_discovery_graph(collector: DiscoveryCollector, llm: LLMClient) -> Any:
    """Portfolio orchestrator: discovery graph -> parallel candidate subgraphs -> selection."""
    research_graph = build_candidate_research_graph(collector, llm)
    finalization_graph = build_candidate_finalization_graph(collector, llm)
    builder = StateGraph(PortfolioGraphState)

    def plan(state: PortfolioGraphState) -> dict:
        planned = plan_queries(state["request"])
        if state.get("queries"):
            planned["queries"] = state["queries"]
            planned["trace"][0]["detail"] = f"items={len(state['queries'])} explicit_query_plan=true"
        return planned

    async def collect(state: PortfolioGraphState) -> dict:
        return await collect_behavior_sources(
            collector, state["request"], state["queries"], state["freshness"]
        )

    def normalize(state: PortfolioGraphState) -> dict:
        return normalize_evidence(state["documents"])

    def workarounds(state: PortfolioGraphState) -> dict:
        return detect_workarounds(state["documents"], state["queries"])

    def cluster(state: PortfolioGraphState) -> dict:
        return deduplicate_root_problems(state["observations"], state["queries"])

    def evidence_gate(state: PortfolioGraphState) -> dict:
        reviewed = review_problem_evidence(
            state["clusters"], state.get("exclusions", {}), allow_fixture=collector.is_fixture
        )
        if reviewed["eligible_clusters"]:
            reviewed["evidence_route"] = "ANALYZE"
        elif int(state.get("evidence_retry_count", 0)) < 1:
            reviewed["evidence_route"] = "COLLECT_MORE"
        else:
            reviewed["evidence_route"] = "HOLD"
        reviewed["trace"][0]["detail"] += f" route={reviewed['evidence_route']}"
        return reviewed

    def refine_queries(state: PortfolioGraphState) -> dict:
        started, clock = datetime.now(UTC), perf_counter()
        retry = int(state.get("evidence_retry_count", 0)) + 1
        if collector.provider_name == "verified-url-input":
            queries = state["queries"]
            detail = "verified URL corpus exhausted; one bounded recheck only"
        else:
            queries = [
                item.model_copy(
                    update={
                        "query": f"{item.query} 실제 경험 반복 수작업 우회 방법",
                        "discovery_intent": "collect stronger repeated-behavior originals",
                    }
                )
                for item in state["queries"]
            ]
            detail = f"neutral behavior query refinement attempt={retry}"
        return {
            "queries": queries,
            "evidence_retry_count": retry,
            "trace": [trace("refine_behavior_queries", started, clock, detail)],
        }

    async def analyze_candidates(state: PortfolioGraphState) -> dict:
        started, clock = datetime.now(UTC), perf_counter()
        ordered_clusters = sorted(
            state["eligible_clusters"],
            key=lambda item: (
                item.preliminary_score,
                len(item.independent_evidence),
                item.cluster_id,
            ),
            reverse=True,
        )
        research_quotas = {
            "PROBLEM_SOLVER": 4,
            "BEHAVIOR_REDESIGN": 4,
            "WILD_BET": 2,
        }
        research_counts = {key: 0 for key in research_quotas}
        clusters = []
        for cluster in ordered_clusters:
            lane = str(cluster.lane)
            if research_counts[lane] >= research_quotas[lane]:
                continue
            clusters.append(cluster)
            research_counts[lane] += 1
            if len(clusters) == 10:
                break

        async def run_one(index: int, cluster: Any) -> CandidateGraphState:
            token = set_invocation_context(state["run_id"], cluster.cluster_id)
            candidate_started, candidate_clock = datetime.now(UTC), perf_counter()
            try:
                try:
                    result = await research_graph.ainvoke(
                        CandidateGraphState(
                        run_id=state["run_id"],
                        cluster=cluster,
                        request=state["request"],
                        freshness=state["freshness"],
                        candidate_prefix=f"candidate-{index}:{cluster.cluster_id}",
                        live_run=not collector.is_fixture,
                        trace=[],
                        visited_nodes=[],
                        critique_findings=[],
                        finding_history=[],
                        blocking_finding_fingerprints=[],
                        arbitration_results=[],
                        revision_records=[],
                        critique_round=0,
                        revision_round=0,
                        wedge_retry_count=0,
                        validation_retry_count=0,
                        )
                    )
                except LLMError as exc:
                    result = CandidateGraphState(
                        run_id=state["run_id"],
                        cluster=cluster,
                        request=state["request"],
                        freshness=state["freshness"],
                        candidate_prefix=f"candidate-{index}:{cluster.cluster_id}",
                        live_run=not collector.is_fixture,
                        next_route="hold",
                        error_type=type(exc).__name__,
                        error_message=str(exc)[:1000],
                        trace=[
                            trace(
                                f"candidate-{index}:{cluster.cluster_id}:candidate_failure",
                                candidate_started,
                                candidate_clock,
                                f"{type(exc).__name__}: candidate isolated and held",
                                actual_route="hold",
                                route_reason="LLM failure is isolated to this candidate",
                                provider="orchestrator",
                                schema_validation="FAILED",
                                status="FAILED",
                            )
                        ],
                    )
            finally:
                reset_invocation_context(token)
            return cast(CandidateGraphState, result)

        research_results = list(
            await asyncio.gather(*(run_one(i, c) for i, c in enumerate(clusters, 1)))
        )
        ranked = sorted(
            (
                item
                for item in research_results
                if item.get("product_route") == "DESIGN_VALIDATION"
            ),
            key=lambda item: (
                sum(score.value for score in item.get("scores", {}).values()),
                item["cluster"].preliminary_score,
                len(item["cluster"].independent_evidence),
            ),
            reverse=True,
        )
        preselected: list[CandidateGraphState] = []
        final_quotas = {
            "PROBLEM_SOLVER": 2,
            "BEHAVIOR_REDESIGN": 2,
            "WILD_BET": 1,
        }
        final_counts = {key: 0 for key in final_quotas}
        for item in ranked:
            if any(
                item["cluster"].lane == existing["cluster"].lane
                and jaccard(item["root_problem"], existing["root_problem"]) >= 0.72
                for existing in preselected
            ):
                item["next_route"] = "hold"
                item["error_message"] = "not selected: duplicate root-problem archetype"
                continue
            lane = str(item["cluster"].lane)
            if final_counts[lane] >= final_quotas[lane]:
                item["next_route"] = "hold"
                item["error_message"] = f"not selected: {lane} daily lane quota reached"
                continue
            preselected.append(item)
            final_counts[lane] += 1
            if len(preselected) == state["request"].max_candidates:
                break
        selected_ids = {item["cluster"].cluster_id for item in preselected}
        for item in ranked:
            if item["cluster"].cluster_id not in selected_ids and not item.get("next_route"):
                item["next_route"] = "hold"
                item["error_message"] = (
                    "not selected: outside preliminary quality/diversity top candidates"
                )

        async def finalize_one(item: CandidateGraphState) -> CandidateGraphState:
            token = set_invocation_context(state["run_id"], item["cluster"].cluster_id)
            try:
                return cast(
                    CandidateGraphState,
                    await finalization_graph.ainvoke(item),
                )
            except LLMError as exc:
                item["next_route"] = "hold"
                item["error_type"] = type(exc).__name__
                item["error_message"] = str(exc)[:1000]
                return item
            finally:
                reset_invocation_context(token)

        finalized = list(await asyncio.gather(*(finalize_one(item) for item in preselected)))
        finalized_by_id = {item["cluster"].cluster_id: item for item in finalized}
        results = [
            finalized_by_id.get(item["cluster"].cluster_id, item)
            for item in research_results
        ]
        candidate_trace = []
        seen_trace: set[tuple[Any, ...]] = set()
        for result in results:
            for event in result.get("trace", []):
                key = (
                    event["node"],
                    event["status"],
                    event["detail"],
                    event["started_at"],
                    event["completed_at"],
                )
                if key not in seen_trace:
                    seen_trace.add(key)
                    candidate_trace.append(event)
        return {
            "candidate_results": results,
            "trace": [
                trace(
                    "orchestrate_candidate_subgraphs",
                    started,
                    clock,
                    f"research_top10={len(research_results)} quality_top5={len(finalized)} parallel=true",
                ),
                *candidate_trace,
            ],
        }

    def select(state: PortfolioGraphState) -> dict:
        started, clock = datetime.now(UTC), perf_counter()
        candidates: list[PortfolioCandidate] = []
        exclusions = Counter(state.get("exclusions", {}))
        all_queries = list(state.get("all_queries", []))
        all_results = list(state.get("all_results", []))
        all_documents = list(state.get("all_documents", []))
        quality_audits: list[CandidateQualityAudit] = []
        for result in state.get("candidate_results", []):
            all_queries.extend(result.get("market_queries", []))
            all_results.extend(result.get("market_results", []))
            all_documents.extend(result.get("market_documents", []))
            exclusions.update(result.get("exclusions", {}))
            raw_route = (
                result.get("next_route")
                or result.get("validation_route")
                or result.get("product_route")
                or result.get("problem_route")
                or "not_reached"
            )
            final_route = raw_route.lower()
            execution_status = (
                "REPORT_COMPLETE"
                if final_route == "report_complete" and result.get("thesis") is not None
                else "REJECTED"
                if final_route == "reject"
                else "NEEDS_MORE_EVIDENCE"
                if final_route in {"collect_more", "extract_behavior", "recluster"}
                else "HELD"
            )
            evidence_gate_result = result.get("evidence_gate")
            quality_audits.append(
                CandidateQualityAudit(
                    candidate_id=result["cluster"].cluster_id,
                    root_problem=result.get("root_problem", result["cluster"].root_problem),
                    execution_status=execution_status,
                    candidate_verdict=(
                        result["thesis"].verdict
                        if result.get("thesis") is not None
                        else "REJECT"
                        if final_route == "reject"
                        else "HOLD"
                        if final_route in {"hold", "human_review"}
                        else "REJECT"
                    ),
                    strongest_objection=result.get("strongest_objection", ""),
                    terminal_reason=(
                        evidence_gate_result.reason
                        if evidence_gate_result is not None
                        and not evidence_gate_result.passed
                        else result.get("strongest_objection", "")
                        or result.get("error_message", "")
                        or f"terminated at route {final_route}"
                    ),
                    error_type=result.get("error_type"),
                    error_message=result.get("error_message"),
                    evidence_gate=evidence_gate_result,
                    critique_findings=result.get("critique_findings", []),
                    finding_history=result.get("finding_history", []),
                    arbitration_results=result.get("arbitration_results", []),
                    revision_records=result.get("revision_records", []),
                    verification_result=result.get("verification_result"),
                    critique_round=result.get("critique_round", 0),
                    revision_round=result.get("revision_round", 0),
                    visited_nodes=result.get("visited_nodes", []),
                    final_route=final_route,
                )
            )
            thesis = result.get("thesis")
            market = result.get("market")
            if not result.get("accepted") or thesis is None or market is None:
                exclusions[f"candidate_route:{result.get('product_route') or result.get('validation_route') or 'rejected'}"] += 1
                continue
            candidates.append(
                PortfolioCandidate(rank=1, cluster=result["cluster"], market_structure=market, thesis=thesis)
            )
        evaluated = select_distinct_top_candidates(candidates, len(candidates))
        selected = select_balanced_top_candidates(
            candidates, state["request"].max_candidates
        )
        for index, candidate in enumerate(selected, 1):
            candidate.rank = index
        return {
            "candidates": selected,
            "evaluated_candidates": evaluated,
            "exclusions": dict(exclusions),
            "all_queries": all_queries,
            "all_results": all_results,
            "all_documents": all_documents,
            "candidate_quality_audits": quality_audits,
            "trace": [
                trace(
                    "select_balanced_up_to_five_candidates",
                    started,
                    clock,
                    f"selected={len(selected)} quotas=2_problem+2_redesign+1_wild never_padded=true",
                )
            ],
        }

    def finalize(state: PortfolioGraphState) -> dict:
        completed = datetime.now(UTC)
        audit_by_url: dict[str, PublicDocument] = {}
        for document in state.get("all_documents", []):
            url = str(document.search_result.url)
            current = audit_by_url.get(url)
            if current is None or (
                current.access_level == "SEARCH_SNIPPET_ONLY"
                and document.access_level == "ORIGINAL_VERIFIED"
            ):
                audit_by_url[url] = document
        audit = [
            SourceAuditEntry(
                title=document.search_result.title,
                url=document.search_result.url,
                query=document.search_result.query,
                provider=document.search_result.provider,
                access_level=document.access_level,
                accessed_at=document.accessed_at,
                published_at=document.search_result.published_at,
                error_reason=document.error_reason,
            )
            for document in audit_by_url.values()
        ]
        verified = sum(item.access_level == "ORIGINAL_VERIFIED" for item in audit)
        attempted = sum(item.error_reason != "original_fetch_budget_exceeded" for item in audit)
        warnings = [
            "Ranking is limited to this run's queries, provider index, date range, and verified originals.",
            "Qualitative judgments were produced by the configured structured LLM; numeric gates were applied by code.",
            "Asset and expansion scores remain zero/unknown until source-backed control and reuse are verified.",
        ]
        candidates = state.get("candidates", [])
        if len(candidates) < state["request"].max_candidates:
            warnings.append(
                f"Only {len(candidates)} candidates passed gates; results were not padded."
            )
        events = [
            DiscoveryEvent(sequence=index, **record)
            for index, record in enumerate(state.get("trace", []), 1)
        ]
        raw_llm_calls = getattr(llm, "calls", [])
        llm_audit = [
            LLMCallAudit.model_validate(item)
            for item in raw_llm_calls
            if item.get("provider") == "codex"
        ]
        llm_provider = getattr(llm, "provider", "unknown")
        portfolio = DiscoveryPortfolio(
            run_id=state["run_id"],
            mode=state["request"].mode,
            focus=state["request"].focus,
            country=state["request"].country,
            search_language=state["request"].search_lang,
            provider=collector.provider_name,
            llm_provider=llm_provider,
            started_at=state["started_at"],
            completed_at=completed,
            query_count=len(state.get("all_queries", [])),
            search_queries=[item.query for item in state.get("all_queries", [])],
            exploration_areas=sorted({item.theme for item in state.get("all_queries", [])}),
            investigation_period_start=state["period_start"],
            investigation_period_end=state["started_at"],
            result_count=len({str(item.url) for item in state.get("all_results", [])}),
            original_pages_attempted=attempted,
            original_pages_verified=verified,
            snippet_only_count=len(audit) - verified,
            excluded_count=sum(state.get("exclusions", {}).values()),
            exclusion_reasons=dict(sorted(state.get("exclusions", {}).items())),
            behavior_observation_count=len(state.get("observations", [])),
            cluster_count=len(state.get("clusters", [])),
            rejected_cluster_count=len(state.get("rejected_clusters", [])) + max(0, len(state.get("eligible_clusters", [])) - len(candidates)),
            candidates=candidates,
            evaluated_candidates=state.get("evaluated_candidates", []),
            rejected_clusters=state.get("rejected_clusters", []),
            events=events,
            llm_call_audit=llm_audit,
            candidate_quality_audits=state.get("candidate_quality_audits", []),
            source_audit=audit,
            warnings=warnings,
            data_origin="TEST_FIXTURE" if collector.is_fixture else "LIVE_PUBLIC_WEB",
            candidate_limit=state["request"].max_candidates,
        )
        return {"portfolio": portfolio, "completed_at": completed}

    builder.add_node("plan_queries", plan)
    builder.add_node("collect_behavior_sources", collect)
    builder.add_node("normalize_evidence", normalize)
    builder.add_node("detect_workarounds", workarounds)
    builder.add_node("deduplicate_root_problems", cluster)
    builder.add_node("review_problem_evidence", evidence_gate)
    builder.add_node("refine_behavior_queries", refine_queries)
    builder.add_node("orchestrate_candidate_subgraphs", analyze_candidates)
    builder.add_node("select_distinct_candidates", select)
    builder.add_node("save_result", finalize)
    builder.add_edge(START, "plan_queries")
    builder.add_edge("plan_queries", "collect_behavior_sources")
    builder.add_edge("collect_behavior_sources", "normalize_evidence")
    builder.add_edge("normalize_evidence", "detect_workarounds")
    builder.add_edge("detect_workarounds", "deduplicate_root_problems")
    builder.add_edge("deduplicate_root_problems", "review_problem_evidence")
    builder.add_conditional_edges(
        "review_problem_evidence",
        lambda state: state.get("evidence_route", "HOLD"),
        DISCOVERY_ROUTES,
    )
    builder.add_edge("refine_behavior_queries", "collect_behavior_sources")
    builder.add_edge("orchestrate_candidate_subgraphs", "select_distinct_candidates")
    builder.add_edge("select_distinct_candidates", "save_result")
    builder.add_edge("save_result", END)
    return builder.compile()
