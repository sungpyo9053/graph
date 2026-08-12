from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.domain.models.url_input import VerifiedUrlEntry, VerifiedUrlInput
from src.services.discovery.query_plan import infer_lane_from_query


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
    assert set(query.model_dump()) == {"query", "theme", "lane", "discovery_intent"}
    assert query.lane == "PROBLEM_SOLVER"
    assert "root_problem" not in query.model_dump_json()
    assert "wedge" not in query.model_dump_json()


def test_search_intent_routes_behavior_redesign_without_accepting_solution_hints() -> None:
    assert infer_lane_from_query("매일 달리기 경로 기록 공유 습관 후기") == "BEHAVIOR_REDESIGN"
    assert infer_lane_from_query("이상한 습관을 매일 반복하는 놀이 후기") == "WILD_BET"
    assert infer_lane_from_query("이상하지만 매일 반복하는 습관 기록 놀이 후기") == "WILD_BET"
    assert infer_lane_from_query("여러 업체 견적 일일이 비교 불편") == "PROBLEM_SOLVER"
    assert (
        infer_lane_from_query("세입자가 수리 요청 사진 견적 영수증 카톡 기록을 모으는 행동")
        == "PROBLEM_SOLVER"
    )
