from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any

from src.agents.models import (
    AssetExpansionAnalysis,
    BehaviorReframeAnalysis,
    PersonaAnalysis,
    RootProblemAnalysis,
    StructuralGapAnalysis,
    WedgeDesignAnalysis,
)
from src.domain.models.discovery import DiscoveryLane, DiscoveryRequest, ProblemCluster
from src.domain.models.schemas import Score
from src.graphs.state import DiscoveryCollector, TraceRecord
from src.llm.client import LLMClient, generate_with_schema_retry
from src.services.discovery.clustering import (
    cluster_observations,
    has_minimum_strong_evidence,
)
from src.services.discovery.extraction import extract_observations
from src.services.discovery.market import analyze_market_structure, market_queries
from src.services.discovery.query_plan import build_query_plan
from src.services.discovery.thesis import (
    build_thesis,
    design_validation,
    evaluate_asset_score,
    evaluate_expansion_score,
)


def trace(
    name: str,
    started: datetime,
    clock: float,
    detail: str,
    *,
    suggested_route: str | None = None,
    actual_route: str | None = None,
    route_reason: str = "",
    provider: str | None = None,
    schema_validation: str | None = None,
    status: str = "SUCCEEDED",
) -> TraceRecord:
    completed = datetime.now(UTC)
    qualitative = any(
        marker in name
        for marker in (
            "identify_persona",
            "analyze_root_problem",
            "analyze_structural_gap",
            "design_wedge_candidates",
            "evaluate_asset_accumulation",
            "cold_critique",
            "exit_challenger",
        )
    )
    return TraceRecord(
        node=name,
        status=status,
        detail=detail,
        started_at=started,
        completed_at=completed,
        duration_ms=round((perf_counter() - clock) * 1000),
        input_reference="candidate_state",
        output_reference="candidate_state_delta",
        suggested_route=suggested_route,
        actual_route=actual_route,
        route_reason=route_reason,
        attempt=1,
        provider=provider or ("structured_llm" if qualitative else "code"),
        schema_validation=schema_validation or ("VALID" if qualitative else "NOT_APPLICABLE"),
    )


def evidence_context(cluster: ProblemCluster) -> list[dict[str, Any]]:
    """Bounded evidence passed to qualitative nodes; never sends an entire fetched page."""
    observation_by_signal = {item.evidence.signal_id: item for item in cluster.observations}
    payload: list[dict[str, Any]] = []
    for item in cluster.independent_evidence:
        observation = observation_by_signal.get(item.signal_id)
        payload.append(
            {
                "source_id": item.signal_id,
                "url": str(item.source_url) if item.source_url else None,
                "confirmed_excerpt": item.original_text[:700],
                "observed_behavior": item.behavior_observed[:700],
                "current_workaround": item.workaround_observed,
                "confirmed_frequency": observation.frequency if observation else "unknown",
                "confirmed_loss": observation.measurable_loss if observation else "unknown",
            }
        )
    return payload


def plan_queries(request: DiscoveryRequest) -> dict[str, Any]:
    started, clock = datetime.now(UTC), perf_counter()
    period_start = started - timedelta(days=request.lookback_days)
    queries = build_query_plan(request)
    return {
        "started_at": started,
        "period_start": period_start,
        "freshness": f"{period_start.date().isoformat()}to{started.date().isoformat()}",
        "queries": queries,
        "trace": [trace("plan_queries", started, clock, f"items={len(queries)}")],
    }


async def collect_behavior_sources(
    collector: DiscoveryCollector,
    request: DiscoveryRequest,
    queries: list[Any],
    freshness: str,
) -> dict[str, Any]:
    started, clock = datetime.now(UTC), perf_counter()
    results, documents = await collector.search(
        queries,
        count=request.results_per_query,
        country=request.country,
        search_lang=request.search_lang,
        freshness=freshness,
        max_original_pages=request.max_original_pages,
    )
    return {
        "results": results,
        "documents": documents,
        "all_queries": list(queries),
        "all_results": list(results),
        "all_documents": list(documents),
        "trace": [
            trace(
                "collect_behavior_sources",
                started,
                clock,
                f"results={len(results)} documents={len(documents)}",
            )
        ],
    }


def normalize_evidence(documents: list[Any]) -> dict[str, Any]:
    started, clock = datetime.now(UTC), perf_counter()
    by_url: dict[str, Any] = {}
    for document in documents:
        url = str(document.search_result.url).split("#", 1)[0]
        current = by_url.get(url)
        if current is None or (
            current.access_level == "SEARCH_SNIPPET_ONLY"
            and document.access_level == "ORIGINAL_VERIFIED"
        ):
            by_url[url] = document
    normalized = list(by_url.values())
    return {
        "documents": normalized,
        "trace": [trace("normalize_evidence", started, clock, f"items={len(normalized)}")],
    }


def detect_workarounds(documents: list[Any], queries: list[Any]) -> dict[str, Any]:
    started, clock = datetime.now(UTC), perf_counter()
    observations, exclusions = extract_observations(documents, queries)
    return {
        "observations": observations,
        "exclusions": dict(exclusions),
        "trace": [
            trace("detect_workarounds", started, clock, f"observations={len(observations)}")
        ],
    }


def deduplicate_root_problems(observations: list[Any], queries: list[Any]) -> dict[str, Any]:
    started, clock = datetime.now(UTC), perf_counter()
    clusters = cluster_observations(observations, queries)
    return {
        "clusters": clusters,
        "trace": [
            trace("deduplicate_root_problems", started, clock, f"clusters={len(clusters)}")
        ],
    }


def review_problem_evidence(
    clusters: list[ProblemCluster], exclusions: dict[str, int], *, allow_fixture: bool
) -> dict[str, Any]:
    started, clock = datetime.now(UTC), perf_counter()
    eligible = [
        item for item in clusters if has_minimum_strong_evidence(item, allow_fixture=allow_fixture)
    ]
    rejected = [item for item in clusters if item not in eligible]
    counts = Counter(exclusions)
    counts["cluster_below_two_independent_A_to_C_originals"] += sum(
        item.lane != DiscoveryLane.WILD_BET for item in rejected
    )
    counts["wild_bet_below_one_independent_behavior_original"] += sum(
        item.lane == DiscoveryLane.WILD_BET for item in rejected
    )
    return {
        "eligible_clusters": eligible,
        "rejected_clusters": rejected,
        "exclusions": dict(counts),
        "trace": [
            trace(
                "review_problem_evidence",
                started,
                clock,
                f"eligible={len(eligible)} rejected={len(rejected)}",
            )
        ],
    }


def extract_pain(cluster: ProblemCluster, prefix: str) -> dict[str, Any]:
    started, clock = datetime.now(UTC), perf_counter()
    pain = " | ".join(dict.fromkeys(item.pain for item in cluster.observations))
    return {
        "pain_summary": pain,
        "trace": [trace(f"{prefix}:extract_pain", started, clock, pain[:120])],
    }


async def identify_persona(
    cluster: ProblemCluster, prefix: str, llm: LLMClient
) -> dict[str, Any]:
    started, clock = datetime.now(UTC), perf_counter()
    result = await generate_with_schema_retry(
        llm,
        task="identify_persona",
        input_data={
            "evidence": evidence_context(cluster),
        },
        output_model=PersonaAnalysis,
        metadata={"prompt_version": "persona-from-evidence-v1", "candidate_id": cluster.cluster_id},
    )
    updated = cluster.model_copy(update={"persona": result.persona})
    return {
        "cluster": updated,
        "persona": result.persona,
        "situation": result.situation,
        "trace": [trace(f"{prefix}:identify_persona", started, clock, result.source_support)],
    }


async def analyze_root_problem(
    cluster: ProblemCluster, prefix: str, llm: LLMClient
) -> dict[str, Any]:
    started, clock = datetime.now(UTC), perf_counter()
    result = await generate_with_schema_retry(
        llm,
        task="analyze_root_problem",
        input_data={
            "persona": cluster.persona,
            "observed_behavior": [item.repeated_behavior for item in cluster.observations],
            "workarounds": [item.workaround for item in cluster.observations],
            "pain": [item.pain for item in cluster.observations],
            "evidence": evidence_context(cluster),
        },
        output_model=RootProblemAnalysis,
        metadata={"prompt_version": "root-problem-v1", "candidate_id": cluster.cluster_id},
    )
    root = result.root_problem.strip()
    updated = cluster.model_copy(update={"root_problem": root})
    return {
        "cluster": updated,
        "root_problem": root,
        "trace": [trace(f"{prefix}:analyze_root_problem", started, clock, root[:160])],
    }


async def analyze_behavior_reframe(
    cluster: ProblemCluster, prefix: str, llm: LLMClient
) -> dict[str, Any]:
    started, clock = datetime.now(UTC), perf_counter()
    result = await generate_with_schema_retry(
        llm,
        task="analyze_behavior_reframe",
        input_data={
            "observed_behavior": [item.repeated_behavior for item in cluster.observations],
            "confirmed_frequency": [item.frequency for item in cluster.observations],
            "evidence": evidence_context(cluster),
            "constraint": (
                "Do not invent a pain or product. Analyze how competition, collection, "
                "identity, sharing, or progression could change the meaning of the existing behavior."
            ),
        },
        output_model=BehaviorReframeAnalysis,
        metadata={
            "prompt_version": "behavior-reframe-v1",
            "candidate_id": cluster.cluster_id,
        },
    )
    opportunity = result.behavior_opportunity.strip()
    updated = cluster.model_copy(update={"root_problem": opportunity})
    return {
        "cluster": updated,
        "root_problem": opportunity,
        "behavior_reframe": result,
        "trace": [
            trace(
                f"{prefix}:analyze_behavior_opportunity",
                started,
                clock,
                opportunity[:160],
            )
        ],
    }


def problem_gate(cluster: ProblemCluster, root_problem: str, prefix: str) -> dict[str, Any]:
    started, clock = datetime.now(UTC), perf_counter()
    minimum = 1 if cluster.lane == "WILD_BET" else 2
    passed = len(cluster.independent_evidence) >= minimum and bool(root_problem)
    route = "ANALYZE_MARKET_STRUCTURE" if passed else "REJECT"
    return {
        "evidence_passed": passed,
        "problem_route": route,
        "trace": [trace(f"{prefix}:review_problem_evidence", started, clock, route)],
    }


async def research_existing_alternatives(
    collector: DiscoveryCollector,
    cluster: ProblemCluster,
    request: DiscoveryRequest,
    freshness: str,
    prefix: str,
) -> dict[str, Any]:
    started, clock = datetime.now(UTC), perf_counter()
    queries = market_queries(cluster)
    results, documents = await collector.search(
        queries,
        count=min(request.results_per_query, 8),
        country=request.country,
        search_lang=request.search_lang,
        freshness=freshness,
        max_original_pages=max(4, request.max_original_pages // 8),
    )
    return {
        "market_queries": queries,
        "market_results": results,
        "market_documents": documents,
        "trace": [
            trace(
                f"{prefix}:analyze_existing_alternatives",
                started,
                clock,
                f"documents={len(documents)}",
            )
        ],
    }


async def analyze_structural_gap_node(
    cluster: ProblemCluster, documents: list[Any], prefix: str, llm: LLMClient
) -> dict[str, Any]:
    started, clock = datetime.now(UTC), perf_counter()
    market, exclusions = analyze_market_structure(cluster, documents)
    result = await generate_with_schema_retry(
        llm,
        task="analyze_structural_gap",
        input_data={
            "alternatives": [item.model_dump(mode="json") for item in market.alternatives],
            "structural_gap": market.structural_gap,
            "why_unsolved": market.why_unsolved,
            "behavior_evidence_count": len(cluster.independent_evidence),
        },
        output_model=StructuralGapAnalysis,
        metadata={"prompt_version": "structural-gap-v1", "candidate_id": cluster.cluster_id},
    )
    market = market.model_copy(
        update={"structural_gap": result.structural_gap, "why_unsolved": result.why_unsolved}
    )
    return {
        "market": market,
        "causal_gap_verified": result.causal_gap_verified,
        "exclusions": dict(exclusions),
        "trace": [
            trace(f"{prefix}:analyze_structural_gap", started, clock, market.structural_gap[:160])
        ],
    }


async def design_wedge_candidates_node(
    cluster: ProblemCluster, prefix: str, llm: LLMClient
) -> dict[str, Any]:
    started, clock = datetime.now(UTC), perf_counter()
    result = await generate_with_schema_retry(
        llm,
        task="design_wedge_candidates",
        input_data={
            "discovery_lane": cluster.lane,
            "root_problem": cluster.root_problem,
            "persona": cluster.persona,
            "workarounds": [item.workaround for item in cluster.observations],
            "evidence": evidence_context(cluster),
            "constraints": "maximum 3 materially different wedges; each must be one input -> one result",
            "behavior_displacement_contract": (
                "For PROBLEM_SOLVER, state whether the wedge removes or consolidates a workaround. "
                "For BEHAVIOR_REDESIGN/WILD_BET, do not require displacement; instead define the "
                "instant visible result, repeat trigger, social loop, ten-second demo, solo value, "
                "network amplification, and a bounded validation cost."
            ),
        },
        output_model=WedgeDesignAnalysis,
        metadata={"prompt_version": "wedge-design-v2", "candidate_id": cluster.cluster_id},
    )
    wedges = result.candidates[:3]
    return {
        "wedge_candidates": wedges,
        "trace": [trace(f"{prefix}:design_wedge_candidates", started, clock, "items=1")],
    }


def evaluation_node(name: str, score: Score, prefix: str) -> dict[str, Any]:
    started, clock = datetime.now(UTC), perf_counter()
    event_names = {
        "problem_strength_score": "evaluate_problem_strength",
        "repetition_score": "evaluate_repetition",
        "workaround_score": "evaluate_workaround_strength",
        "structural_gap_score": "evaluate_structural_gap",
        "wedge_simplicity_score": "evaluate_wedge_simplicity",
        "switching_score": "evaluate_switching_feasibility",
        "founder_fit_score": "evaluate_founder_fit",
    }
    return {
        name: score,
        "trace": [trace(f"{prefix}:{event_names.get(name, name)}", started, clock, score.rationale)],
    }


async def evaluate_asset_node(
    state: dict[str, Any], prefix: str, llm: LLMClient
) -> dict[str, Any]:
    started, clock = datetime.now(UTC), perf_counter()
    result = await generate_with_schema_retry(
        llm,
        task="analyze_asset_expansion",
        input_data={
            "root_problem": state["cluster"].root_problem,
            "selected_wedge_candidates": [item.model_dump() for item in state["wedge_candidates"]],
            "evidence": evidence_context(state["cluster"]),
        },
        output_model=AssetExpansionAnalysis,
        metadata={"prompt_version": "asset-expansion-from-wedge-v1", "candidate_id": state["cluster"].cluster_id},
    )
    from src.domain.models.schemas import AccumulatingAsset

    evidence_status = (
        "VERIFIED"
        if result.asset_source_support == "VERIFIED"
        and result.controlled_by_product
        and result.reusable_in_later_cases
        else "HYPOTHESIS"
    )
    assets = [
        AccumulatingAsset(
            asset=result.asset,
            accumulation_mechanism=result.accumulation_mechanism,
            strategic_value=result.rationale,
            evidence_status=evidence_status,
        )
    ]
    return {
        "assets": assets,
        "asset_expansion_analysis": result,
        "asset_score": evaluate_asset_score(assets),
        "trace": [trace(f"{prefix}:evaluate_asset_accumulation", started, clock, result.rationale)],
    }


async def evaluate_expansion_node(
    state: dict[str, Any], prefix: str, llm: LLMClient
) -> dict[str, Any]:
    del llm
    started, clock = datetime.now(UTC), perf_counter()
    result = state["asset_expansion_analysis"]
    from src.domain.models.schemas import ExpansionPath

    paths = [ExpansionPath(
        stage=1,
        problem=result.expansion_problem,
        asset_used=state["assets"][0].asset if state["assets"] else "unknown",
        adjacency_reason=result.causal_link,
        evidence_status=(
            "SUPPORTED" if result.expansion_source_support == "VERIFIED" else "UNSUPPORTED"
        ),
    )]
    return {
        "expansion_paths": paths,
        "expansion_score": evaluate_expansion_score(paths, state["assets"]),
        "trace": [trace(f"{prefix}:evaluate_expansion_potential", started, clock, result.rationale)],
    }


def merge_evaluations(state: dict[str, Any], prefix: str) -> dict[str, Any]:
    started, clock = datetime.now(UTC), perf_counter()
    names = (
        "problem_strength_score",
        "repetition_score",
        "workaround_score",
        "structural_gap_score",
        "wedge_simplicity_score",
        "switching_score",
        "asset_score",
        "expansion_score",
        "founder_fit_score",
    )
    scores = {name.removesuffix("_score"): state[name] for name in names}
    return {
        "scores": scores,
        "trace": [trace(f"{prefix}:merge_evaluations", started, clock, f"items={len(scores)}")],
    }


def select_wedge(wedges: list[Any], prefix: str) -> dict[str, Any]:
    started, clock = datetime.now(UTC), perf_counter()
    selected = wedges[0]
    return {
        "selected_wedge": selected,
        "trace": [trace(f"{prefix}:select_wedge", started, clock, selected.name)],
    }


def design_validation_node(
    cluster: ProblemCluster, prefix: str, hypotheses: list[str] | None = None
) -> dict[str, Any]:
    started, clock = datetime.now(UTC), perf_counter()
    plan = design_validation(cluster)
    if hypotheses:
        plan = plan.model_copy(
            update={
                "hypothesis": f"{plan.hypothesis}; testable unknowns: {'; '.join(hypotheses)}"
            }
        )
    return {
        "validation_plan": plan,
        "trace": [trace(f"{prefix}:design_validation", started, clock, f"days={plan.duration_days}")],
    }


def write_thesis_node(state: dict[str, Any], prefix: str) -> dict[str, Any]:
    started, clock = datetime.now(UTC), perf_counter()
    thesis = build_thesis(
        state["cluster"],
        state["market"],
        scores_override=state["scores"],
        selected_wedge=state["selected_wedge"],
        assets_override=state["assets"],
        expansion_override=state["expansion_paths"],
        validation_override=state["validation_plan"],
        strongest_objection_override=state.get("strongest_objection"),
        causal_gap_verified=bool(state.get("causal_gap_verified", False)),
        unknowns_override=state.get("unknowns", []),
    )
    return {
        "thesis": thesis,
        "accepted": True,
        "trace": [trace(f"{prefix}:write_problem_wedge_expansion_thesis", started, clock, thesis.verdict)],
    }
