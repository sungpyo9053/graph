from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


def utcnow() -> datetime:
    return datetime.now(UTC)


class Route(StrEnum):
    COLLECT_MORE = "COLLECT_MORE"
    MERGE_EXISTING = "MERGE_EXISTING"
    REVISE_ROOT_PROBLEM = "REVISE_ROOT_PROBLEM"
    ANALYZE_MARKET_STRUCTURE = "ANALYZE_MARKET_STRUCTURE"
    RESEARCH_STRUCTURE_MORE = "RESEARCH_STRUCTURE_MORE"
    REVISE_WEDGE = "REVISE_WEDGE"
    DESIGN_VALIDATION = "DESIGN_VALIDATION"
    REVISE_VALIDATION = "REVISE_VALIDATION"
    APPROVE = "APPROVE"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    HOLD = "HOLD"
    REJECT = "REJECT"


class RunStatus(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    HELD = "HELD"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCKED = "BLOCKED"


class EvidenceGrade(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


class EvidenceSourceRole(StrEnum):
    """How a fetched original supports a claim.

    Only FIRSTHAND_BEHAVIOR is eligible for the independent behavior-evidence
    gate. Guides and official process pages remain useful for market/process
    research, but they are not observations of a user performing the behavior.
    """

    FIRSTHAND_BEHAVIOR = "FIRSTHAND_BEHAVIOR"
    PROCEDURAL_GUIDE = "PROCEDURAL_GUIDE"
    OFFICIAL_PROCESS = "OFFICIAL_PROCESS"
    SECONDARY_REPORT = "SECONDARY_REPORT"
    UNCLASSIFIED = "UNCLASSIFIED"


class FinalVerdict(StrEnum):
    VALIDATE_PROBLEM = "VALIDATE_PROBLEM"
    VALIDATE_DELIGHT = "VALIDATE_DELIGHT"
    WILD_BET = "WILD_BET"
    HOLD = "HOLD"
    REJECT = "REJECT"


class ApprovalDecision(StrEnum):
    APPROVE = "APPROVE"
    REVISE = "REVISE"
    HOLD = "HOLD"
    REJECT = "REJECT"


class Score(BaseModel):
    value: int = Field(ge=0)
    max_points: int = Field(default=100, gt=0)
    rationale: str = Field(min_length=1)
    confidence: float = Field(default=0, ge=0, le=1)
    unknown: bool = False

    @model_validator(mode="after")
    def value_within_maximum(self) -> Score:
        if self.value > self.max_points:
            raise ValueError("score value cannot exceed max_points")
        return self


class Signal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    source_type: str
    source_name: str
    author_key: str
    original_item_key: str
    text: str
    source_url: HttpUrl | None = None
    published_at: datetime | None = None
    collected_at: datetime = Field(default_factory=utcnow)
    is_fixture: bool = False
    fixture_label: str | None = None


class Evidence(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    signal_id: str
    grade: EvidenceGrade
    claim: str
    behavior_observed: str
    workaround_observed: str | None = None
    source_type: str
    source_name: str
    author_key: str
    original_item_key: str
    original_text: str
    source_url: HttpUrl | None = None
    published_at: datetime | None = None
    collected_at: datetime
    independence_key: str
    freshness_score: float = Field(ge=0, le=1)
    is_fixture: bool = False
    access_level: str = "ORIGINAL_VERIFIED"
    accessed_at: datetime | None = None
    source_role: EvidenceSourceRole = EvidenceSourceRole.UNCLASSIFIED
    behavior_claim_verified: bool = False


class Alternative(BaseModel):
    name: str
    kind: str
    strengths: list[str]
    unresolved_reasons: list[str]
    source: str | None = None
    is_fixture: bool = False


class WedgeCandidate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    approach_type: str
    target_user: str
    buyer: str
    user_input: str
    core_process: str
    expected_output: str
    switching_reason: str
    switching_cost: str
    time_to_first_value: str
    solo_first_user_value: bool
    acquisition_channel: str
    monetization_hypothesis: str
    required_data: str
    data_access_feasible: bool
    problem_relevance: bool = True
    manual_validation_feasible: bool = True
    behavior_displacement: Literal[
        "REMOVES_STEP", "CONSOLIDATES_STEPS", "NO_DISPLACEMENT", "UNKNOWN"
    ] = "UNKNOWN"
    expected_steps_removed: int | None = Field(default=None, ge=0)
    external_form_reentry_required: bool | None = None
    instant_visible_result: bool | None = None
    repeat_trigger: str = "unknown"
    social_loop: str = "unknown"
    ten_second_demo: bool | None = None
    network_amplification: bool | None = None
    validation_cost_usd: float | None = Field(default=None, ge=0)
    complexity: str


class AccumulatingAsset(BaseModel):
    asset: str
    accumulation_mechanism: str
    strategic_value: str
    evidence_status: str


class ExpansionPath(BaseModel):
    stage: int = Field(ge=1, le=3)
    problem: str
    asset_used: str
    adjacency_reason: str
    evidence_status: str


class ValidationPlan(BaseModel):
    hypothesis: str
    target_user: str
    method: str
    duration_days: int = Field(ge=1)
    success_criterion: str
    failure_criterion: str
    estimated_cost_usd: float = Field(ge=0)
    next_action_if_pass: str
    next_action_if_fail: str
    cohort_size: int | None = Field(default=None, ge=1)
    observation_days: int | None = Field(default=None, ge=1)
    minimum_consistent_users: int | None = Field(default=None, ge=1)
    minimum_active_days: int | None = Field(default=None, ge=1)
    minimum_next_week_requests: int | None = Field(default=None, ge=1)
    minimum_unsolicited_shares: int | None = Field(default=None, ge=1)
    minimum_unrewarded_second_cycle_starts: int | None = Field(default=None, ge=1)
    require_referred_user_arrival: bool = False
    require_curiosity_driven_return_check: bool = False


class RetryCounts(BaseModel):
    evidence: int = 0
    root_problem: int = 0
    structure: int = 0
    wedge: int = 0
    validation: int = 0


class ThesisEvidence(BaseModel):
    original_text: str
    source: str
    url: str | None
    date: datetime | None
    grade: EvidenceGrade
    independence_key: str
    observed_fact: str
    is_fixture: bool
    access_level: str = "ORIGINAL_VERIFIED"
    accessed_at: datetime | None = None
    source_role: EvidenceSourceRole = EvidenceSourceRole.UNCLASSIFIED


class ProblemWedgeExpansionThesis(BaseModel):
    discovery_lane: Literal["PROBLEM_SOLVER", "BEHAVIOR_REDESIGN", "WILD_BET"] = (
        "PROBLEM_SOLVER"
    )
    idea_name: str
    one_line_thesis: str
    repeated_behavior: str
    frequency: str
    measurable_loss: str
    current_workaround: str
    behavior_reframe: str = "not applicable"
    visible_result: str = "unknown"
    repeat_trigger: str = "unknown"
    social_loop: str = "unknown"
    surface_pain: str
    root_problem: str
    persona: str
    evidence: list[ThesisEvidence]
    existing_alternatives: list[Alternative]
    structural_gap: str
    wedge_statement: str
    core_user_action: str
    switching_reason: str
    switching_cost: str
    time_to_first_value: str
    accumulating_assets: list[AccumulatingAsset]
    expansion_paths: list[ExpansionPath]
    market_and_revenue_hypothesis: str
    first_user_access: str
    strongest_objection: str
    kill_conditions: list[str]
    validation: ValidationPlan
    scores: dict[str, Score]
    total_score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    verdict: FinalVerdict
    next_action: str
    unknowns: list[str]
    assumptions: list[str]
    is_fixture: bool = False

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_verdict(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        migrated = dict(data)
        legacy = migrated.get("verdict")
        if legacy == "VALIDATE":
            migrated["verdict"] = "VALIDATE_PROBLEM"
        elif legacy in {"RESEARCH", "INTERVIEW"}:
            migrated["verdict"] = "HOLD"
        return migrated


class IdeaState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    run_id: str
    status: RunStatus = RunStatus.CREATED
    current_node: str = "START"
    behavior_signals: list[Signal] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    observed_facts: list[str] = Field(default_factory=list)
    inferences: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    persona: str = ""
    situation: str = ""
    repeated_behavior: str = ""
    pain: str = ""
    frequency: str = ""
    measurable_loss: str = ""
    current_workaround: str = ""
    root_problem: str = ""
    existing_alternatives: list[Alternative] = Field(default_factory=list)
    structural_gap: str = ""
    why_unsolved: str = ""
    wedge_candidates: list[WedgeCandidate] = Field(default_factory=list)
    selected_wedge: WedgeCandidate | None = None
    core_user_action: str = ""
    expected_output: str = ""
    switching_reason: str = ""
    switching_cost: str = ""
    time_to_first_value: str = ""
    accumulating_assets: list[AccumulatingAsset] = Field(default_factory=list)
    expansion_paths: list[ExpansionPath] = Field(default_factory=list)
    founder_fit: str = ""
    problem_strength_score: Score = Field(
        default_factory=lambda: unknown_score(15, "문제 근거 없음")
    )
    repetition_score: Score = Field(default_factory=lambda: unknown_score(15, "반복성 근거 없음"))
    workaround_score: Score = Field(
        default_factory=lambda: unknown_score(15, "우회 행동 근거 없음")
    )
    structural_gap_score: Score = Field(
        default_factory=lambda: unknown_score(10, "구조적 공백 근거 없음")
    )
    wedge_simplicity_score: Score = Field(default_factory=lambda: unknown_score(10, "웨지 없음"))
    switching_score: Score = Field(default_factory=lambda: unknown_score(10, "전환 근거 없음"))
    asset_score: Score = Field(default_factory=lambda: unknown_score(10, "축적 자산 근거 없음"))
    expansion_score: Score = Field(default_factory=lambda: unknown_score(10, "확장 근거 없음"))
    founder_fit_score: Score = Field(default_factory=lambda: unknown_score(5, "Founder Fit 미평가"))
    confidence: float = Field(default=0, ge=0, le=1)
    strongest_objection: str = ""
    kill_conditions: list[str] = Field(default_factory=list)
    validation_plan: ValidationPlan | None = None
    final_thesis: ProblemWedgeExpansionThesis | None = None
    retry_counts: RetryCounts = Field(default_factory=RetryCounts)
    total_node_count: int = 0
    total_model_calls: int = 0
    estimated_cost: float = 0
    risk_level: RiskLevel = RiskLevel.LOW
    rejection_reasons: list[str] = Field(default_factory=list)
    duplicate_candidate_id: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    suggested_next_route: Route | None = None
    actual_next_route: Route | None = None
    route_reason: str = ""
    pending_approval_id: str | None = None
    started_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    is_fixture: bool = False

    @property
    def total_score(self) -> int:
        return sum(
            score.value
            for score in (
                self.problem_strength_score,
                self.repetition_score,
                self.workaround_score,
                self.structural_gap_score,
                self.wedge_simplicity_score,
                self.switching_score,
                self.asset_score,
                self.expansion_score,
                self.founder_fit_score,
            )
        )


def unknown_score(max_points: int, rationale: str) -> Score:
    return Score(value=0, max_points=max_points, rationale=rationale, confidence=0, unknown=True)


class IdeaCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3, max_length=3000)


class ApprovalInput(BaseModel):
    decision: ApprovalDecision
    revise_node: str | None = None
    reason: str = ""


JsonDict = dict[str, Any]
