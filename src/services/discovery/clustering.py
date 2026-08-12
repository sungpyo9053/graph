from __future__ import annotations

import hashlib
from collections import defaultdict

from src.domain.models.discovery import (
    BehaviorObservation,
    DiscoveryLane,
    ProblemCluster,
    SearchQuery,
)
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
        # Search context is not a behavioral identity. Every observation starts
        # separate and only joins a cluster when its meaning-compatible facets do.
        target = f"{observation.theme}:{observation.evidence.signal_id}"
        for existing_theme, existing in grouped.items():
            if not existing:
                continue
            if existing[0].lane != observation.lane:
                continue
            if behavior_cluster_compatible(existing[0], observation):
                target = existing_theme
                break
        grouped[target].append(observation)

    clusters: list[ProblemCluster] = []
    for _group_key, items in grouped.items():
        evidence = independent_qualifying_evidence(item.evidence for item in items)
        if not evidence:
            continue
        query = query_by_theme.get(items[0].theme)
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
        if query.lane == DiscoveryLane.PROBLEM_SOLVER:
            workaround = grounded_score(
                min(15, workaround_count * 5),
                15,
                f"verified originals showing an active workaround: {workaround_count}",
                min(1, workaround_count / 3),
            )
        else:
            workaround = grounded_score(
                min(15, len(evidence) * 5),
                15,
                f"verified existing-behavior substrate sources: {len(evidence)}; workaround is not required for {query.lane}",
                min(1, len(evidence) / 3),
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
                lane=query.lane,
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


def behavior_cluster_compatible(
    left: BehaviorObservation,
    right: BehaviorObservation,
) -> bool:
    """Require shared behavioral meaning, not just a shared verb such as 'record'."""
    left_text = f"{left.repeated_behavior} {left.workaround}"
    right_text = f"{right.repeated_behavior} {right.workaround}"
    surface_similarity = jaccard(left_text, right_text)

    motivation_overlap = bool(set(left.motivations) & set(right.motivations))
    target_overlap = bool(set(left.target_objects) & set(right.target_objects))
    reward_overlap = bool(set(left.expected_rewards) & set(right.expected_rewards))
    specific_trigger_overlap = bool(
        (set(left.repeat_triggers) - {"daily_routine"})
        & (set(right.repeat_triggers) - {"daily_routine"})
    )

    # Conflicting concrete targets outweigh generic surface verbs like taking a
    # photo, posting, or recording every day.
    if left.target_objects and right.target_objects and not target_overlap:
        return False

    # Surface similarity is supporting evidence only. It must never bypass
    # concrete target/motivation conflicts or manufacture identity when the
    # semantic facets are unknown.
    if surface_similarity >= 0.62:
        if left.target_objects or right.target_objects:
            return target_overlap and (
                motivation_overlap or reward_overlap or specific_trigger_overlap
            )
        return motivation_overlap and (reward_overlap or specific_trigger_overlap)

    # Unknown facets never justify a merge. With known facets, target identity
    # plus at least one matching motivation, reward, or trigger is required.
    return target_overlap and (
        motivation_overlap or reward_overlap or specific_trigger_overlap
    )


def has_minimum_strong_evidence(
    cluster: ProblemCluster,
    minimum: int | None = None,
    *,
    allow_fixture: bool = False,
) -> bool:
    qualifying: list[Evidence] = [
        item
        for item in independent_qualifying_evidence(cluster.independent_evidence)
        if item.grade in {EvidenceGrade.A, EvidenceGrade.B, EvidenceGrade.C}
        and item.access_level == "ORIGINAL_VERIFIED"
        and (allow_fixture or not item.is_fixture)
    ]
    required = (
        minimum
        if minimum is not None
        else 1
        if cluster.lane == DiscoveryLane.WILD_BET
        else 2
    )
    return len(qualifying) >= required
