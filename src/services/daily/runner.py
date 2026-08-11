from __future__ import annotations

from copy import deepcopy
from datetime import UTC, date, datetime

from src.domain.models.daily import (
    CandidateRecord,
    CandidateRegistry,
    CandidateStatus,
    DailyCandidateChange,
    DailyClassification,
    DailyRunResult,
)
from src.domain.models.discovery import DiscoveryPortfolio, PortfolioCandidate, ProblemCluster
from src.services.daily.deduplication import (
    best_historical_match,
    merge_independent_evidence,
    stable_candidate_id,
)
from src.services.daily.registry import CandidateRegistryStore


class DailyDiscoveryProcessor:
    def __init__(self, store: CandidateRegistryStore) -> None:
        self.store = store

    def process(self, portfolio: DiscoveryPortfolio, *, run_date: date | None = None) -> DailyRunResult:
        day = run_date or datetime.now(UTC).date()
        self._validate_origin(portfolio)
        registry = self.store.load(data_origin=portfolio.data_origin)
        previous_records = deepcopy(registry.candidates)
        changes: list[DailyCandidateChange] = []
        action_count = 0
        pool = portfolio.evaluated_candidates or portfolio.candidates
        for candidate in pool:
            match = best_historical_match(candidate, registry.candidates)
            if match is None:
                if action_count >= 5:
                    continue
                record = _record_from_candidate(candidate, portfolio.data_origin, day)
                registry.candidates.append(record)
                changes.append(DailyCandidateChange(
                    classification=DailyClassification.NEW,
                    candidate=record,
                    evidence_added=len(record.evidence),
                    reason="no semantically matching root problem in the complete candidate registry",
                ))
                action_count += 1
                continue
            previous = deepcopy(match)
            merged, added = merge_independent_evidence(
                match.evidence, candidate.cluster.independent_evidence
            )
            if added == 0:
                changes.append(_change(
                    DailyClassification.DUPLICATE,
                    match,
                    previous,
                    0,
                    "same problem with no new independent URL, author, or original content",
                ))
                continue
            if action_count >= 5:
                continue
            match.evidence = merged
            match.latest_evidence_at = day
            match.last_evaluated_at = day
            match.score = candidate.thesis.total_score
            match.confidence = candidate.thesis.confidence
            match.persona = candidate.thesis.persona
            match.repeated_behavior = candidate.thesis.repeated_behavior
            match.workaround = candidate.thesis.current_workaround
            match.thesis = candidate.thesis
            classification = DailyClassification.UPDATED
            match.status = CandidateStatus.UPDATED
            reason = f"{added} new independent original evidence item(s)"
            if previous.status == CandidateStatus.REJECTED:
                classification = DailyClassification.REOPEN
                match.status = CandidateStatus.REOPENED
                match.rejection_reasons = []
                reason = f"{added} new independent item(s) now satisfy the prior evidence rejection"
            changes.append(_change(classification, match, previous, added, reason))
            action_count += 1

        rejected_changes = self._record_rejected_clusters(
            portfolio.rejected_clusters,
            registry,
            portfolio.data_origin,
            day,
        )
        changes.extend(rejected_changes)
        self.store.save(registry)

        new = [item for item in changes if item.classification == DailyClassification.NEW]
        updated = [
            item
            for item in changes
            if item.classification in {DailyClassification.UPDATED, DailyClassification.REOPEN}
        ]
        duplicate = [
            item for item in changes if item.classification == DailyClassification.DUPLICATE
        ]
        rejected = [
            item for item in changes if item.classification == DailyClassification.REJECTED
        ]
        review = sorted(
            [*new, *updated],
            key=lambda item: (
                item.candidate.score,
                len(item.candidate.evidence),
                item.candidate.candidate_id,
            ),
            reverse=True,
        )[:5]
        limitations = [
            *portfolio.warnings,
            "Historical matching is deterministic lexical similarity; semantic paraphrases may need human merge review.",
            "Mirror detection uses canonical URL, known author, exact fingerprint, and high text overlap.",
        ]
        del previous_records
        return DailyRunResult(
            run_id=portfolio.run_id,
            run_date=day,
            portfolio=portfolio,
            new_candidates=new,
            updated_candidates=updated,
            duplicate_candidates=duplicate,
            rejected_candidates=rejected,
            review_candidates=review,
            source_audit=portfolio.source_audit,
            limitations=limitations,
            completed_at=datetime.now(UTC),
        )

    @staticmethod
    def _record_rejected_clusters(
        clusters: list[ProblemCluster],
        registry: CandidateRegistry,
        data_origin: str,
        day: date,
    ) -> list[DailyCandidateChange]:
        changes: list[DailyCandidateChange] = []
        for cluster in clusters:
            match = best_historical_match(cluster, registry.candidates)
            reason = "fewer than two independent A-C verified original sources"
            if match is None:
                record = _record_from_rejected(cluster, data_origin, day, reason)
                registry.candidates.append(record)
            else:
                record = match
                merged, added = merge_independent_evidence(
                    record.evidence, cluster.independent_evidence
                )
                if record.status == CandidateStatus.REJECTED:
                    record.evidence = merged
                    if added:
                        record.latest_evidence_at = day
                    record.last_evaluated_at = day
                    record.rejection_reasons = [reason]
                else:
                    reason = "current run was below gate; historical accepted state was not downgraded"
            changes.append(DailyCandidateChange(
                classification=DailyClassification.REJECTED,
                candidate=record,
                evidence_added=0,
                reason=reason,
            ))
        return changes

    @staticmethod
    def _validate_origin(portfolio: DiscoveryPortfolio) -> None:
        fixture_flags = {
            evidence.is_fixture
            for candidate in portfolio.evaluated_candidates or portfolio.candidates
            for evidence in candidate.cluster.independent_evidence
        }
        expected_fixture = portfolio.data_origin == "TEST_FIXTURE"
        if fixture_flags and fixture_flags != {expected_fixture}:
            raise ValueError("fixture and live evidence cannot be mixed in a daily run")


def _record_from_candidate(
    candidate: PortfolioCandidate,
    data_origin: str,
    day: date,
) -> CandidateRecord:
    thesis = candidate.thesis
    return CandidateRecord(
        candidate_id=stable_candidate_id(candidate.cluster.root_problem),
        data_origin=data_origin,
        root_problem=candidate.cluster.root_problem,
        persona=thesis.persona,
        repeated_behavior=thesis.repeated_behavior,
        workaround=thesis.current_workaround,
        evidence=candidate.cluster.independent_evidence,
        first_discovered_at=day,
        latest_evidence_at=day,
        last_evaluated_at=day,
        score=thesis.total_score,
        confidence=thesis.confidence,
        status=CandidateStatus.PENDING_REVIEW,
        thesis=thesis,
    )


def _record_from_rejected(
    cluster: ProblemCluster,
    data_origin: str,
    day: date,
    reason: str,
) -> CandidateRecord:
    return CandidateRecord(
        candidate_id=stable_candidate_id(cluster.root_problem),
        data_origin=data_origin,
        root_problem=cluster.root_problem,
        persona=cluster.persona,
        repeated_behavior=" | ".join(item.repeated_behavior for item in cluster.observations),
        workaround=" | ".join(item.workaround for item in cluster.observations),
        evidence=cluster.independent_evidence,
        first_discovered_at=day,
        latest_evidence_at=day,
        last_evaluated_at=day,
        score=cluster.preliminary_score,
        confidence=min(
            cluster.problem_strength.confidence,
            cluster.repetition.confidence,
            cluster.workaround_strength.confidence,
        ),
        status=CandidateStatus.REJECTED,
        rejection_reasons=[reason],
    )


def _change(
    classification: DailyClassification,
    current: CandidateRecord,
    previous: CandidateRecord,
    evidence_added: int,
    reason: str,
) -> DailyCandidateChange:
    return DailyCandidateChange(
        classification=classification,
        candidate=current,
        previous_score=previous.score,
        previous_confidence=previous.confidence,
        previous_status=previous.status,
        evidence_added=evidence_added,
        reason=reason,
    )
