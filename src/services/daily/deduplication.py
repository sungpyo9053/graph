from __future__ import annotations

import hashlib
import re
from urllib.parse import urlsplit, urlunsplit

from src.domain.models.daily import CandidateRecord
from src.domain.models.discovery import PortfolioCandidate, ProblemCluster
from src.domain.models.schemas import Evidence
from src.domain.policies.duplicates import jaccard


def stable_candidate_id(root_problem: str) -> str:
    normalized = " ".join(sorted(_semantic_tokens(root_problem)))
    return f"candidate-{hashlib.sha256(normalized.encode()).hexdigest()[:16]}"


def candidate_similarity(
    root_problem: str,
    repeated_behavior: str,
    workaround: str,
    existing: CandidateRecord,
) -> float:
    return (
        0.65 * jaccard(root_problem, existing.root_problem)
        + 0.2 * jaccard(repeated_behavior, existing.repeated_behavior)
        + 0.15 * jaccard(workaround, existing.workaround)
    )


def best_historical_match(
    candidate: PortfolioCandidate | ProblemCluster,
    records: list[CandidateRecord],
    *,
    threshold: float = 0.68,
) -> CandidateRecord | None:
    if isinstance(candidate, PortfolioCandidate):
        root = candidate.cluster.root_problem
        repeated = candidate.thesis.repeated_behavior
        workaround = candidate.thesis.current_workaround
    else:
        root = candidate.root_problem
        repeated = " | ".join(item.repeated_behavior for item in candidate.observations)
        workaround = " | ".join(item.workaround for item in candidate.observations)
    ranked = sorted(
        (
            (candidate_similarity(root, repeated, workaround, record), record)
            for record in records
        ),
        key=lambda item: (item[0], item[1].candidate_id),
        reverse=True,
    )
    return ranked[0][1] if ranked and ranked[0][0] >= threshold else None


def merge_independent_evidence(
    existing: list[Evidence], incoming: list[Evidence]
) -> tuple[list[Evidence], int]:
    merged = list(existing)
    added = 0
    for item in incoming:
        if any(evidence_is_duplicate(item, current) for current in merged):
            continue
        merged.append(item)
        added += 1
    return merged, added


def evidence_is_duplicate(left: Evidence, right: Evidence) -> bool:
    left_url = canonical_url(str(left.source_url or ""))
    right_url = canonical_url(str(right.source_url or ""))
    if left_url and left_url == right_url:
        return True
    if _known_author(left.author_key) and left.author_key == right.author_key:
        return True
    if _text_fingerprint(left.original_text) == _text_fingerprint(right.original_text):
        return True
    return jaccard(_normalized_text(left.original_text), _normalized_text(right.original_text)) >= 0.9


def canonical_url(value: str) -> str:
    if not value:
        return ""
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    port = f":{parsed.port}" if parsed.port else ""
    path = re.sub(r"/+", "/", parsed.path).rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), host + port, path, "", ""))


def _known_author(value: str) -> bool:
    return bool(value and not value.startswith("unknown-author:"))


def _text_fingerprint(value: str) -> str:
    return hashlib.sha256(_normalized_text(value).encode()).hexdigest()


def _normalized_text(value: str) -> str:
    return " ".join(re.findall(r"[0-9A-Za-z가-힣]+", value.lower()))


def _semantic_tokens(value: str) -> set[str]:
    ignored = {"app", "application", "platform", "software", "ai", "ui", "tool", "서비스", "앱"}
    return {
        token
        for token in re.findall(r"[0-9A-Za-z가-힣]+", value.lower())
        if len(token) > 1 and token not in ignored
    }
