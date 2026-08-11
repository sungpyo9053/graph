from collections.abc import Iterable
from datetime import UTC, datetime

from src.domain.models.schemas import Evidence, EvidenceGrade, EvidenceSourceRole, Signal

QUALIFYING_GRADES = {EvidenceGrade.A, EvidenceGrade.B, EvidenceGrade.C}


def freshness_score(published_at: datetime | None, now: datetime | None = None) -> float:
    if published_at is None:
        return 0.4
    now = now or datetime.now(UTC)
    age_days = max(0, (now - published_at).days)
    if age_days <= 180:
        return 1.0
    if age_days <= 365:
        return 0.8
    if age_days <= 730:
        return 0.5
    return 0.2


def independence_key(signal: Signal) -> str:
    return f"{signal.author_key.strip().lower()}::{signal.original_item_key.strip().lower()}"


def evidence_from_signal(
    signal: Signal,
    grade: EvidenceGrade,
    claim: str,
    *,
    workaround: str | None = None,
) -> Evidence:
    return Evidence(
        signal_id=signal.id,
        grade=grade,
        claim=claim,
        behavior_observed=signal.text,
        workaround_observed=workaround,
        source_type=signal.source_type,
        source_name=signal.source_name,
        author_key=signal.author_key,
        original_item_key=signal.original_item_key,
        original_text=signal.text,
        source_url=signal.source_url,
        published_at=signal.published_at,
        collected_at=signal.collected_at,
        independence_key=independence_key(signal),
        freshness_score=freshness_score(signal.published_at),
        is_fixture=signal.is_fixture,
        source_role=EvidenceSourceRole.FIRSTHAND_BEHAVIOR,
        behavior_claim_verified=True,
    )


def independent_qualifying_evidence(items: Iterable[Evidence]) -> list[Evidence]:
    selected: dict[str, Evidence] = {}
    for item in items:
        if (
            item.grade not in QUALIFYING_GRADES
            or item.source_role != EvidenceSourceRole.FIRSTHAND_BEHAVIOR
            or not item.behavior_claim_verified
        ):
            continue
        previous = selected.get(item.independence_key)
        if previous is None or item.grade < previous.grade:
            selected[item.independence_key] = item
    return list(selected.values())
