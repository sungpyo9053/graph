from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.domain.models.schemas import WedgeCandidate


class QualitativeAnalysis(BaseModel):
    observed_facts: list[str]
    inferences: list[str]
    assumptions: list[str]
    unknowns: list[str]
    decision: str
    decision_reason: str


class PersonaAnalysis(QualitativeAnalysis):
    persona: str
    situation: str
    source_support: str
    confidence: float = Field(ge=0, le=1)


class RootProblemAnalysis(QualitativeAnalysis):
    root_problem: str
    rationale: str
    confidence: float = Field(ge=0, le=1)


class BehaviorReframeAnalysis(QualitativeAnalysis):
    behavior_opportunity: str
    current_meaning: str
    reframe_axes: list[Literal["COMPETITION", "COLLECTION", "IDENTITY", "SHARING", "PROGRESSION"]]
    rationale: str
    confidence: float = Field(ge=0, le=1)


class StructuralGapAnalysis(QualitativeAnalysis):
    structural_gap: str
    why_unsolved: str
    causal_gap_verified: bool
    rationale: str
    confidence: float = Field(ge=0, le=1)


class WedgeCandidates(QualitativeAnalysis):
    candidates: list[WedgeCandidate] = Field(min_length=1, max_length=3)
    rationale: str


class AssetExpansionAnalysis(QualitativeAnalysis):
    asset: str
    accumulation_mechanism: str
    controlled_by_product: bool
    reusable_in_later_cases: bool
    asset_source_support: Literal["VERIFIED", "HYPOTHESIS", "UNSUPPORTED"]
    expansion_problem: str
    causal_link: str
    expansion_source_support: Literal["VERIFIED", "HYPOTHESIS", "UNSUPPORTED"]
    rationale: str


WedgeDesignAnalysis = WedgeCandidates
