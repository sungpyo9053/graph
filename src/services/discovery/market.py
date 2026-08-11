from __future__ import annotations

from collections import Counter

from src.domain.models.discovery import (
    MarketStructureResearch,
    PortfolioCandidate,
    ProblemCluster,
    PublicDocument,
    SearchQuery,
)
from src.domain.models.schemas import Alternative
from src.domain.policies.duplicates import (
    behavior_solution_signature,
    jaccard,
    same_behavior_solution_archetype,
)


def market_queries(cluster: ProblemCluster) -> list[SearchQuery]:
    return [
        SearchQuery(
            query=f'"{cluster.root_problem[:140]}" 기존 서비스 대안 후기',
            theme=cluster.theme,
            discovery_intent="research existing alternatives after root-problem derivation",
        ),
        SearchQuery(
            query=f"{cluster.persona[:100]} {cluster.root_problem[:120]} 현재 해결 방법",
            theme=cluster.theme,
            discovery_intent="research why current alternatives leave the behavior unresolved",
        ),
    ]


def analyze_market_structure(
    cluster: ProblemCluster,
    documents: list[PublicDocument],
) -> tuple[MarketStructureResearch, Counter[str]]:
    alternatives: list[Alternative] = []
    exclusions: Counter[str] = Counter()
    urls = []
    for document in documents:
        if document.access_level != "ORIGINAL_VERIFIED" or not document.extracted_text:
            exclusions[f"market_snippet_only:{document.error_reason or 'not_fetched'}"] += 1
            continue
        result = document.search_result
        urls.append(result.url)
        alternatives.append(
            Alternative(
                name=result.title[:180],
                kind="existing alternative source",
                strengths=[document.extracted_text[:240]],
                unresolved_reasons=[
                    "source proves an alternative exists, not why the workaround persists"
                ],
                source=str(result.url),
                is_fixture=result.is_fixture,
            )
        )
    alternatives = alternatives[:6]
    if alternatives:
        gap = (
            "Verified originals show alternatives while independent behavior originals still show "
            "an active workaround; the causal structural reason remains unverified."
        )
        why = (
            f"{len(alternatives)} verified alternative sources coexist with "
            f"{len(cluster.independent_evidence)} independent behavior sources."
        )
        unknowns = ["causal reason incumbent alternatives leave the workaround in place"]
    else:
        gap = "unknown: no existing-alternative original page was successfully verified"
        why = "market structure could not be verified from original pages in this run"
        unknowns = ["existing alternatives", "structural gap", "why incumbents have not solved it"]
    return (
        MarketStructureResearch(
            alternatives=alternatives,
            structural_gap=gap,
            why_unsolved=why,
            source_urls=urls,
            unknowns=unknowns,
        ),
        exclusions,
    )


def select_distinct_top_candidates(
    candidates: list[PortfolioCandidate], maximum: int
) -> list[PortfolioCandidate]:
    ordered = sorted(
        candidates,
        key=lambda item: (
            item.thesis.total_score,
            len(item.thesis.evidence),
            item.cluster.cluster_id,
        ),
        reverse=True,
    )
    selected: list[PortfolioCandidate] = []
    for candidate in ordered:
        if any(
            _same_candidate_archetype(candidate, existing)
            for existing in selected
        ):
            continue
        selected.append(candidate)
        if len(selected) == maximum:
            break
    return selected


def _same_candidate_archetype(
    candidate: PortfolioCandidate, existing: PortfolioCandidate
) -> bool:
    if jaccard(candidate.cluster.root_problem, existing.cluster.root_problem) >= 0.72:
        return True
    candidate_parts = candidate.thesis.core_user_action.split("→")
    existing_parts = existing.thesis.core_user_action.split("→")
    candidate_behavior = " ".join(
        f"{item.repeated_behavior} {item.workaround}"
        for item in candidate.cluster.observations
    )
    existing_behavior = " ".join(
        f"{item.repeated_behavior} {item.workaround}"
        for item in existing.cluster.observations
    )
    if (
        jaccard(candidate_behavior, existing_behavior) >= 0.78
        and jaccard(candidate.thesis.core_user_action, existing.thesis.core_user_action)
        >= 0.72
    ):
        return True
    candidate_signature = behavior_solution_signature(
        repeated_behavior=" ".join(
            item.repeated_behavior for item in candidate.cluster.observations
        ),
        workaround=" ".join(item.workaround for item in candidate.cluster.observations),
        wedge_input=candidate_parts[0],
        wedge_output=candidate_parts[-1],
        solution_archetype=" ".join(candidate_parts[1:-1]),
    )
    existing_signature = behavior_solution_signature(
        repeated_behavior=" ".join(
            item.repeated_behavior for item in existing.cluster.observations
        ),
        workaround=" ".join(item.workaround for item in existing.cluster.observations),
        wedge_input=existing_parts[0],
        wedge_output=existing_parts[-1],
        solution_archetype=" ".join(existing_parts[1:-1]),
    )
    return same_behavior_solution_archetype(candidate_signature, existing_signature)
