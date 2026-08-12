from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class CritiqueCategory(StrEnum):
    WEAK_EVIDENCE = "WEAK_EVIDENCE"
    WRONG_ROOT_PROBLEM = "WRONG_ROOT_PROBLEM"
    MISSING_ALTERNATIVE = "MISSING_ALTERNATIVE"
    FALSE_STRUCTURAL_GAP = "FALSE_STRUCTURAL_GAP"
    WEAK_WEDGE = "WEAK_WEDGE"
    NO_BEHAVIOR_CHANGE = "NO_BEHAVIOR_CHANGE"
    NO_FIRST_USER_VALUE = "NO_FIRST_USER_VALUE"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    PLATFORM_DEPENDENCY = "PLATFORM_DEPENDENCY"
    REGULATORY_RISK = "REGULATORY_RISK"
    SAFETY_RISK = "SAFETY_RISK"
    FAKE_ASSET = "FAKE_ASSET"
    UNSUPPORTED_EXPANSION = "UNSUPPORTED_EXPANSION"
    DUPLICATE_IDEA = "DUPLICATE_IDEA"


class CritiqueFinding(BaseModel):
    finding_id: str = Field(default_factory=lambda: str(uuid4()))
    category: CritiqueCategory
    severity: Literal[
        "BLOCKING", "TESTABLE_UNKNOWN", "WEAK_BUT_REVISABLE", "FALSE_POSITIVE"
    ]
    claim: str
    affected_claim: str
    root_cause: str
    evidence_ids: list[str]
    reason: str
    recommended_route: Literal[
        "collect_more",
        "extract_behavior",
        "recluster",
        "root_problem_analysis",
        "market_research",
        "wedge_design",
        "asset_expansion_analysis",
        "human_review",
        "hold",
        "reject",
        "final_verify",
        "report_complete",
    ]


class CritiqueFindings(BaseModel):
    observed_facts: list[str]
    inferences: list[str]
    assumptions: list[str]
    unknowns: list[str]
    decision: str
    decision_reason: str
    findings: list[CritiqueFinding]


class ArbitrationVerdict(StrEnum):
    VALID = "VALID"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    NEEDS_MORE_EVIDENCE = "NEEDS_MORE_EVIDENCE"
    DEBATABLE = "DEBATABLE"
    ENVIRONMENTAL_LIMIT = "ENVIRONMENTAL_LIMIT"


class ArbitrationResult(BaseModel):
    finding_id: str
    category: CritiqueCategory
    verdict: ArbitrationVerdict
    evidence_ids: list[str]
    actual_route: str
    reason: str


class RevisionRecord(BaseModel):
    revision_round: int = Field(ge=1)
    route: str
    before_fingerprint: str
    after_fingerprint: str
    addressed_finding_ids: list[str]
    resolved_finding_ids: list[str]
    changed: bool


class VerificationCheck(BaseModel):
    name: str
    passed: bool
    reason: str
    evidence_ids: list[str] = Field(default_factory=list)


class VerificationResult(BaseModel):
    passed: bool
    checks: list[VerificationCheck]
    next_route: str
    reason: str


class ExitChallenge(BaseModel):
    observed_facts: list[str]
    inferences: list[str]
    assumptions: list[str]
    unknowns: list[str]
    decision: str
    decision_reason: str
    blocking_finding: CritiqueFinding | None


class DiscoveryContract(BaseModel):
    minimum_independent_behavior_evidence: int = 2
    minimum_wild_bet_behavior_evidence: int = 1
    require_original_get: bool = True
    require_workaround: bool = True
    forbid_fixture_in_live: bool = True
    forbid_conclusion_hints: bool = True
    require_fact_inference_assumption_separation: bool = True
    require_claim_evidence_links: bool = True
    require_solo_first_user_value: bool = True
    require_feasible_data_access: bool = True
    require_visible_result_for_delight: bool = True
    require_ten_second_demo_for_delight: bool = True
    delight_validation_cohort_size: int = 10
    delight_validation_observation_days: int = 7
    delight_validation_minimum_consistent_users: int = 4
    delight_validation_minimum_active_days: int = 5
    delight_validation_minimum_next_week_requests: int = 3
    delight_validation_minimum_unsolicited_shares: int = 2
    delight_validation_requires_referred_arrival: bool = True
    delight_validation_requires_curiosity_return_check: bool = True
    maximum_wild_bet_duration_days: int = 14
    maximum_wild_bet_cost_usd: float = 300
    max_critique_rounds: int = 3
    max_revision_rounds: int = 3
    max_exit_challenge_rounds: int = 4
    max_quality_model_calls: int = 12
    max_quality_elapsed_minutes: float = 15
    repeated_root_finding_limit: int = 2


class QualityStateSnapshot(BaseModel):
    root_problem: str
    structural_gap: str
    selected_wedge: dict[str, Any] | None
    assets: list[dict[str, Any]]
    expansion_paths: list[dict[str, Any]]
