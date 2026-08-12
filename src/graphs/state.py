from __future__ import annotations

import operator
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, Protocol, TypedDict

from src.agents.models import AssetExpansionAnalysis, BehaviorReframeAnalysis
from src.domain.models.discovery import (
    BehaviorObservation,
    CandidateQualityAudit,
    DiscoveryPortfolio,
    DiscoveryRequest,
    MarketStructureResearch,
    PortfolioCandidate,
    ProblemCluster,
    PublicDocument,
    SearchQuery,
    SearchResult,
    SocialArchetypeCandidate,
    SocialSignal,
)
from src.domain.models.quality import (
    ArbitrationResult,
    CritiqueFinding,
    DiscoveryContract,
    RevisionRecord,
    VerificationResult,
)
from src.domain.models.schemas import (
    AccumulatingAsset,
    ExpansionPath,
    ProblemWedgeExpansionThesis,
    Score,
    ValidationPlan,
    WedgeCandidate,
)


class DiscoveryCollector(Protocol):
    is_fixture: bool

    @property
    def provider_name(self) -> str: ...

    async def search(
        self,
        queries: list[SearchQuery],
        *,
        count: int,
        country: str,
        search_lang: str,
        freshness: str,
        max_original_pages: int,
    ) -> tuple[list[SearchResult], list[PublicDocument]]: ...


class TraceRecord(TypedDict, total=False):
    node: str
    status: str
    detail: str
    started_at: Any
    completed_at: Any
    duration_ms: int
    input_reference: str
    output_reference: str
    suggested_route: str | None
    actual_route: str | None
    route_reason: str
    attempt: int
    provider: str
    schema_validation: str


class PortfolioGraphState(TypedDict, total=False):
    run_id: str
    request: DiscoveryRequest
    started_at: Any
    completed_at: Any
    freshness: str
    period_start: Any
    queries: list[SearchQuery]
    results: list[SearchResult]
    documents: list[PublicDocument]
    observations: list[BehaviorObservation]
    social_observations: list[BehaviorObservation]
    social_signals: list[SocialSignal]
    social_archetypes: Annotated[list[SocialArchetypeCandidate], operator.add]
    clusters: list[ProblemCluster]
    eligible_clusters: list[ProblemCluster]
    rejected_clusters: list[ProblemCluster]
    evidence_route: str
    evidence_retry_count: int
    exclusions: dict[str, int]
    candidate_results: list[CandidateGraphState]
    candidates: list[PortfolioCandidate]
    evaluated_candidates: list[PortfolioCandidate]
    candidate_quality_audits: list[CandidateQualityAudit]
    all_queries: list[SearchQuery]
    all_results: list[SearchResult]
    all_documents: list[PublicDocument]
    portfolio: DiscoveryPortfolio
    trace: Annotated[list[TraceRecord], operator.add]


class CandidateGraphState(TypedDict, total=False):
    run_id: str
    cluster: ProblemCluster
    request: DiscoveryRequest
    freshness: str
    candidate_prefix: str
    live_run: bool
    evidence_passed: bool
    pain_summary: str
    persona: str
    situation: str
    root_problem: str
    behavior_reframe: BehaviorReframeAnalysis
    unknowns: list[str]
    validation_hypotheses: list[str]
    problem_route: str
    market_queries: list[SearchQuery]
    market_results: list[SearchResult]
    market_documents: list[PublicDocument]
    market: MarketStructureResearch
    causal_gap_verified: bool
    exclusions: dict[str, int]
    wedge_candidates: list[WedgeCandidate]
    selected_wedge: WedgeCandidate
    problem_strength_score: Score
    repetition_score: Score
    workaround_score: Score
    structural_gap_score: Score
    wedge_simplicity_score: Score
    switching_score: Score
    asset_score: Score
    expansion_score: Score
    founder_fit_score: Score
    scores: dict[str, Score]
    assets: list[AccumulatingAsset]
    asset_expansion_analysis: AssetExpansionAnalysis
    expansion_paths: list[ExpansionPath]
    strongest_objection: str
    kill_conditions: list[str]
    product_route: str
    wedge_retry_count: int
    wedge_simplification_used: bool
    validation_plan: ValidationPlan
    validation_route: str
    validation_retry_count: int
    thesis: ProblemWedgeExpansionThesis
    accepted: bool
    discovery_contract: DiscoveryContract
    evidence_gate: VerificationResult
    critique_findings: list[CritiqueFinding]
    finding_history: list[CritiqueFinding]
    blocking_finding_fingerprints: list[str]
    arbitration_results: list[ArbitrationResult]
    revision_records: list[RevisionRecord]
    verification_result: VerificationResult
    critique_round: int
    revision_round: int
    exit_challenge_round: int
    quality_model_calls: int
    quality_started_at: Any
    exit_challenger_pending: bool
    visited_nodes: Annotated[list[str], operator.add]
    next_route: str
    error_type: str
    error_message: str
    trace: Annotated[list[TraceRecord], operator.add]


NodeCallable = Callable[[dict[str, Any]], dict[str, Any] | Awaitable[dict[str, Any]]]
