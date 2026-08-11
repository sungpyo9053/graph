from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from src.domain.models.discovery import DiscoveryPortfolio, SourceAuditEntry
from src.domain.models.schemas import Evidence, ProblemWedgeExpansionThesis


class DailyClassification(StrEnum):
    NEW = "NEW"
    UPDATED = "UPDATED"
    DUPLICATE = "DUPLICATE"
    REOPEN = "REOPEN"
    REJECTED = "REJECTED"


class CandidateStatus(StrEnum):
    PENDING_REVIEW = "PENDING_REVIEW"
    UPDATED = "UPDATED"
    REOPENED = "REOPENED"
    REJECTED = "REJECTED"
    HOLD = "HOLD"
    ACCEPTED = "ACCEPTED"


class CandidateRecord(BaseModel):
    candidate_id: str
    data_origin: Literal["LIVE_PUBLIC_WEB", "TEST_FIXTURE"]
    root_problem: str
    persona: str
    repeated_behavior: str
    workaround: str
    evidence: list[Evidence] = Field(default_factory=list)
    first_discovered_at: date
    latest_evidence_at: date
    last_evaluated_at: date
    score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    status: CandidateStatus
    rejection_reasons: list[str] = Field(default_factory=list)
    user_review_result: str | None = None
    thesis: ProblemWedgeExpansionThesis | None = None


class CandidateRegistry(BaseModel):
    version: int = 1
    data_origin: Literal["LIVE_PUBLIC_WEB", "TEST_FIXTURE"]
    candidates: list[CandidateRecord] = Field(default_factory=list)


class DailyCandidateChange(BaseModel):
    classification: DailyClassification
    candidate: CandidateRecord
    previous_score: int | None = None
    previous_confidence: float | None = None
    previous_status: CandidateStatus | None = None
    evidence_added: int = Field(default=0, ge=0)
    reason: str


class DailyRunResult(BaseModel):
    run_id: str
    run_date: date
    title: str = "오늘 조사 범위에서 근거가 확인된 신규 또는 갱신 후보 최대 5개"
    portfolio: DiscoveryPortfolio
    new_candidates: list[DailyCandidateChange] = Field(default_factory=list)
    updated_candidates: list[DailyCandidateChange] = Field(default_factory=list)
    duplicate_candidates: list[DailyCandidateChange] = Field(default_factory=list)
    rejected_candidates: list[DailyCandidateChange] = Field(default_factory=list)
    review_candidates: list[DailyCandidateChange] = Field(default_factory=list, max_length=5)
    source_audit: list[SourceAuditEntry] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    completed_at: datetime
