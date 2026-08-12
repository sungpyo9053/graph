from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator

from src.domain.models.quality import (
    ArbitrationResult,
    CritiqueFinding,
    RevisionRecord,
    VerificationResult,
)
from src.domain.models.schemas import (
    Alternative,
    Evidence,
    ProblemWedgeExpansionThesis,
    Score,
)


class DiscoveryMode(StrEnum):
    OPEN = "open"
    FOCUSED = "focused"


class DiscoveryLane(StrEnum):
    PROBLEM_SOLVER = "PROBLEM_SOLVER"
    BEHAVIOR_REDESIGN = "BEHAVIOR_REDESIGN"
    WILD_BET = "WILD_BET"


class DiscoveryRequest(BaseModel):
    mode: DiscoveryMode
    focus: str | None = None
    max_candidates: int = Field(default=5, ge=1, le=5)
    country: str = Field(default="US", min_length=2, max_length=2)
    search_lang: str = Field(default="en", min_length=2, max_length=5)
    results_per_query: int = Field(default=10, ge=1, le=20)
    lookback_days: int = Field(default=730, ge=1, le=3650)
    max_original_pages: int = Field(default=80, ge=1, le=200)

    @model_validator(mode="after")
    def focused_requires_focus(self) -> DiscoveryRequest:
        if self.mode == DiscoveryMode.FOCUSED and not (self.focus or "").strip():
            raise ValueError("focused discovery requires --focus")
        return self


class SearchQuery(BaseModel):
    query: str
    theme: str
    lane: DiscoveryLane = DiscoveryLane.PROBLEM_SOLVER
    discovery_intent: str = "find repeated behavior and an observed workaround"


class SearchResult(BaseModel):
    title: str
    url: HttpUrl
    description: str
    provider: str
    query: str
    rank: int = Field(ge=1)
    published_at: datetime | None = None
    result_type: str = "web"
    is_fixture: bool = False
    author_key: str | None = None


class PublicDocument(BaseModel):
    search_result: SearchResult
    access_level: Literal["ORIGINAL_VERIFIED", "SEARCH_SNIPPET_ONLY"]
    accessed_at: datetime | None = None
    status_code: int | None = None
    content_type: str | None = None
    extracted_text: str | None = None
    error_reason: str | None = None


class BehaviorObservation(BaseModel):
    theme: str
    lane: DiscoveryLane = DiscoveryLane.PROBLEM_SOLVER
    persona: str
    repeated_behavior: str
    pain: str
    frequency: str
    measurable_loss: str
    workaround: str
    evidence: Evidence


class MarketStructureResearch(BaseModel):
    alternatives: list[Alternative] = Field(default_factory=list)
    structural_gap: str
    why_unsolved: str
    source_urls: list[HttpUrl] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class ProblemCluster(BaseModel):
    cluster_id: str
    theme: str
    lane: DiscoveryLane = DiscoveryLane.PROBLEM_SOLVER
    persona: str = "unknown: derive from verified originals"
    root_problem: str = "unknown: derive after behavior clustering"
    observations: list[BehaviorObservation]
    independent_evidence: list[Evidence]
    problem_strength: Score
    repetition: Score
    workaround_strength: Score
    preliminary_score: int = Field(ge=0, le=45)


class PortfolioCandidate(BaseModel):
    rank: int = Field(ge=1)
    cluster: ProblemCluster
    market_structure: MarketStructureResearch
    thesis: ProblemWedgeExpansionThesis


class DiscoveryEvent(BaseModel):
    sequence: int = Field(ge=1)
    node: str
    status: Literal["SUCCEEDED", "SKIPPED", "REJECTED", "FAILED"]
    detail: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int = Field(ge=0)
    input_reference: str = "candidate_state"
    output_reference: str = "candidate_state_delta"
    suggested_route: str | None = None
    actual_route: str | None = None
    route_reason: str = ""
    attempt: int = Field(default=1, ge=1)
    provider: str = "code"
    schema_validation: str = "NOT_APPLICABLE"


class LLMCallAudit(BaseModel):
    provider: str
    node: str
    model: str
    started_at: datetime
    duration_ms: int = Field(ge=0)
    exit_code: int
    schema_validation_result: str
    retry_count: int = Field(ge=0)
    ephemeral: bool = True
    sandbox: str = "read-only"
    prior_critique_included: bool | None = None
    invocation_id: str
    skip_git_repo_check_reason: str | None = None


class CandidateQualityAudit(BaseModel):
    candidate_id: str
    root_problem: str
    execution_status: Literal[
        "REPORT_COMPLETE", "HELD", "REJECTED", "NEEDS_MORE_EVIDENCE"
    ]
    candidate_verdict: Literal[
        "VALIDATE_PROBLEM", "VALIDATE_DELIGHT", "WILD_BET", "HOLD", "REJECT"
    ]
    strongest_objection: str = ""
    terminal_reason: str
    error_type: str | None = None
    error_message: str | None = None
    evidence_gate: VerificationResult | None = None
    critique_findings: list[CritiqueFinding] = Field(default_factory=list)
    finding_history: list[CritiqueFinding] = Field(default_factory=list)
    arbitration_results: list[ArbitrationResult] = Field(default_factory=list)
    revision_records: list[RevisionRecord] = Field(default_factory=list)
    verification_result: VerificationResult | None = None
    critique_round: int = 0
    revision_round: int = 0
    visited_nodes: list[str] = Field(default_factory=list)
    final_route: str

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_candidate_verdict(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        migrated = dict(data)
        legacy = migrated.get("candidate_verdict")
        if legacy == "VALIDATE":
            migrated["candidate_verdict"] = "VALIDATE_PROBLEM"
        elif legacy in {"RESEARCH", "INTERVIEW"}:
            migrated["candidate_verdict"] = "HOLD"
        return migrated


class SourceAuditEntry(BaseModel):
    title: str
    url: HttpUrl
    query: str
    provider: str
    access_level: Literal["ORIGINAL_VERIFIED", "SEARCH_SNIPPET_ONLY"]
    accessed_at: datetime | None = None
    published_at: datetime | None = None
    error_reason: str | None = None


class DiscoveryPortfolio(BaseModel):
    run_id: str
    mode: DiscoveryMode
    focus: str | None
    country: str = "US"
    search_language: str = "en"
    provider: str
    llm_provider: str
    started_at: datetime
    completed_at: datetime
    query_count: int
    search_queries: list[str]
    exploration_areas: list[str]
    investigation_period_start: datetime
    investigation_period_end: datetime
    result_count: int
    original_pages_attempted: int
    original_pages_verified: int
    snippet_only_count: int
    excluded_count: int
    exclusion_reasons: dict[str, int]
    behavior_observation_count: int
    cluster_count: int
    rejected_cluster_count: int
    candidates: list[PortfolioCandidate]
    evaluated_candidates: list[PortfolioCandidate] = Field(default_factory=list)
    rejected_clusters: list[ProblemCluster] = Field(default_factory=list)
    events: list[DiscoveryEvent]
    llm_call_audit: list[LLMCallAudit] = Field(default_factory=list)
    candidate_quality_audits: list[CandidateQualityAudit] = Field(default_factory=list)
    source_audit: list[SourceAuditEntry]
    warnings: list[str] = Field(default_factory=list)
    data_origin: Literal["LIVE_PUBLIC_WEB", "TEST_FIXTURE"]
    candidate_limit: int = Field(default=5, ge=1, le=5)


def discovery_now() -> datetime:
    return datetime.now(UTC)
