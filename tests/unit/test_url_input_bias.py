from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.domain.models.url_input import VerifiedUrlEntry, VerifiedUrlInput


def _raw_entry(index: int) -> dict[str, object]:
    return {
        "url": f"https://example.com/original-{index}",
        "title": f"original {index}",
        "source_type": "community",
        "discovered_via_query": "반복 수작업 우회 행동",
        "published_at": "2026-01-01T00:00:00Z",
    }


@pytest.mark.parametrize(
    "forbidden",
    [
        "persona",
        "persona_hint",
        "root_problem",
        "root_problem_hint",
        "wedge",
        "wedge_hint",
        "accumulating_asset",
        "asset_hint",
        "expansion_path",
        "expansion_hint",
        "final_evaluation",
    ],
)
def test_url_entry_rejects_precomputed_conclusions(forbidden: str) -> None:
    payload = _raw_entry(1)
    payload[forbidden] = "precomputed answer"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        VerifiedUrlEntry.model_validate(payload)


def test_url_input_builds_only_neutral_query_metadata() -> None:
    source = VerifiedUrlInput(
        label="raw public originals",
        verified_by="operator",
        verified_at=datetime.now(UTC),
        urls=[VerifiedUrlEntry.model_validate(_raw_entry(index)) for index in range(1, 11)],
    )

    query = source.query_plan()[0]
    assert set(query.model_dump()) == {"query", "theme", "discovery_intent"}
    assert "problem" not in query.model_dump_json()
