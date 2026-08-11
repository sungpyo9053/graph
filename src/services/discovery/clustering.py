from __future__ import annotations

import hashlib
from collections import defaultdict

from src.domain.models.discovery import BehaviorObservation, ProblemCluster, SearchQuery
from src.domain.models.schemas import Evidence, EvidenceGrade
from src.domain.policies.duplicates import jaccard
from src.domain.policies.evidence import independent_qualifying_evidence
from src.domain.scoring.scoring import grounded_score


def cluster_observations(
    observations: list[BehaviorObservation],
    queries: list[SearchQuery],
) -> list[ProblemCluster]:
    query_by_theme = {item.theme: item for item in queries}
    grouped: dict[str, list[BehaviorObservation]] = defaultdict(list)
    for observation in observations:
        target = observation.theme
        for existing_theme, existing in grouped.items():
            if not existing:
                continue
            if (
                jaccard(
                    f"{existing[0].repeated_behavior} {existing[0].workaround}",
                    f"{observation.repeated_behavior} {observation.workaround}",
                )
                >= 0.62
            ):
                target = existing_theme
                break
        grouped[target].append(observation)

    clusters: list[ProblemCluster] = []
    for theme, items in grouped.items():
        evidence = independent_qualifying_evidence(item.evidence for item in items)
        if not evidence:
            continue
        query = query_by_theme.get(theme) or query_by_theme.get(items[0].theme)
        if query is None:
            continue
        a_count = sum(item.grade == EvidenceGrade.A for item in evidence)
        repeated_count = sum(item.frequency != "unknown" for item in items)
        workaround_count = sum(bool(item.workaround.strip()) for item in items)
        problem = grounded_score(
            min(15, len(evidence) * 5 + a_count * 3),
            15,
            f"verified independent A-C original sources: {len(evidence)}; A-grade: {a_count}",
            min(1, len(evidence) / 4),
        )
        repetition = grounded_score(
            min(15, repeated_count * 6 + max(0, len(evidence) - repeated_count) * 2),
            15,
            f"verified sources with explicit frequency: {repeated_count}/{len(evidence)}",
            min(1, repeated_count / 3),
        )
        workaround = grounded_score(
            min(15, workaround_count * 5),
            15,
            f"verified originals showing an active workaround: {workaround_count}",
            min(1, workaround_count / 3),
        )
        behavior_fingerprint = " ".join(
            sorted({item.repeated_behavior[:180] for item in items})
        )
        digest = hashlib.sha256(f"{query.theme}:{behavior_fingerprint}".encode()).hexdigest()[
            :12
        ]
        clusters.append(
            ProblemCluster(
                cluster_id=digest,
                theme=query.theme,
                observations=items,
                independent_evidence=evidence,
                problem_strength=problem,
                repetition=repetition,
                workaround_strength=workaround,
                preliminary_score=problem.value + repetition.value + workaround.value,
            )
        )
    return sorted(
        clusters,
        key=lambda item: (
            item.preliminary_score,
            len(item.independent_evidence),
            item.cluster_id,
        ),
        reverse=True,
    )


def has_minimum_strong_evidence(
    cluster: ProblemCluster,
    minimum: int = 2,
    *,
    allow_fixture: bool = False,
) -> bool:
    qualifying: list[Evidence] = [
        item
        for item in cluster.independent_evidence
        if item.grade in {EvidenceGrade.A, EvidenceGrade.B, EvidenceGrade.C}
        and item.access_level == "ORIGINAL_VERIFIED"
        and (allow_fixture or not item.is_fixture)
    ]
    return len(qualifying) >= minimum
