from __future__ import annotations

from datetime import UTC, datetime

from src.domain.models.discovery import (
    BehaviorObservation,
    DiscoveryLane,
    SearchQuery,
)
from src.domain.models.schemas import (
    Evidence,
    EvidenceGrade,
    EvidenceSourceRole,
)
from src.services.discovery.clustering import (
    behavior_cluster_compatible,
    cluster_observations,
    has_minimum_strong_evidence,
)
from src.services.discovery.extraction import infer_behavior_facets


def _observation(index: int, text: str) -> BehaviorObservation:
    evidence = Evidence(
        signal_id=f"signal-{index}",
        grade=EvidenceGrade.B,
        claim=text,
        behavior_observed=text,
        source_type="community",
        source_name=f"source-{index}",
        author_key=f"author-{index}",
        original_item_key=f"item-{index}",
        original_text=text,
        source_url=f"https://example.com/{index}",
        collected_at=datetime(2026, 8, 12, tzinfo=UTC),
        independence_key=f"independent-{index}",
        freshness_score=1,
        access_level="ORIGINAL_VERIFIED",
        accessed_at=datetime(2026, 8, 12, tzinfo=UTC),
        source_role=EvidenceSourceRole.FIRSTHAND_BEHAVIOR,
        behavior_claim_verified=True,
    )
    return BehaviorObservation(
        theme="daily-photo",
        lane=DiscoveryLane.BEHAVIOR_REDESIGN,
        persona="unknown",
        repeated_behavior=text,
        pain="unknown",
        frequency="매일",
        measurable_loss="unknown",
        workaround="not applicable: existing behavior is the creative substrate",
        **infer_behavior_facets(text),
        evidence=evidence,
    )


def test_same_search_query_does_not_merge_different_photo_motivations() -> None:
    observations = [
        _observation(
            1,
            "저는 매일 받은 음식과 선물을 사진으로 찍고 고맙다는 문구를 게시판에 올렸어요.",
        ),
        _observation(
            2,
            "나는 10년 동안 매일 하늘과 구름을 찍어 연말 달력으로 모았습니다.",
        ),
        _observation(
            3,
            "저는 그림을 끝까지 완성하고 마무리할 때마다 작품 사진을 찍었습니다.",
        ),
    ]
    query = SearchQuery(
        query="매일 사진 기록 인증 공유 습관 후기",
        theme="daily-photo",
        lane=DiscoveryLane.BEHAVIOR_REDESIGN,
    )

    clusters = cluster_observations(observations, [query])

    assert sorted(len(item.observations) for item in clusters) == [1, 1, 1]
    assert not any(has_minimum_strong_evidence(item) for item in clusters)


def test_semantically_equivalent_korean_gratitude_phrasing_still_merges() -> None:
    left = _observation(
        1,
        "저는 매일 고마운 선물을 사진으로 찍어 감사 기록을 게시판에 올렸어요.",
    )
    right = _observation(
        2,
        "나는 선물받은 음식 사진에 고맙다는 문구를 붙여 매일 공유했습니다.",
    )
    query = SearchQuery(
        query="매일 사진 기록 인증 공유 습관 후기",
        theme="daily-photo",
        lane=DiscoveryLane.BEHAVIOR_REDESIGN,
    )

    assert behavior_cluster_compatible(left, right) is True
    clusters = cluster_observations([left, right], [query])
    assert len(clusters) == 1
    assert len(clusters[0].independent_evidence) == 2
    assert has_minimum_strong_evidence(clusters[0]) is True


def test_daily_surface_trigger_alone_never_causes_a_merge() -> None:
    gratitude = _observation(
        1,
        "저는 매일 감사한 음식 사진을 찍고 고맙다는 글을 남겼어요.",
    )
    sky = _observation(
        2,
        "나는 매일 하늘과 구름 사진을 찍어 일 년 달력으로 모았습니다.",
    )

    assert set(gratitude.repeat_triggers) & set(sky.repeat_triggers) == {"daily_routine"}
    assert behavior_cluster_compatible(gratitude, sky) is False


def test_high_surface_similarity_never_bypasses_target_and_motivation_conflict() -> None:
    gratitude = _observation(
        1,
        "저는 매일 사진을 찍고 게시판에 올려 기록했습니다 감사한 선물 사진입니다.",
    )
    bread = _observation(
        2,
        "저는 매일 사진을 찍고 게시판에 올려 기록했습니다 직접 구운 빵 사진입니다.",
    )

    assert set(gratitude.target_objects) == {"gratitude_moment"}
    assert "gratitude_moment" not in bread.target_objects
    assert behavior_cluster_compatible(gratitude, bread) is False


def test_plain_meal_and_bread_are_not_inferred_as_gratitude() -> None:
    meal = infer_behavior_facets("저는 매일 밥 사진을 찍어 식사 기록을 남겼어요.")
    bread = infer_behavior_facets("나는 매주 직접 만든 빵 사진을 게시판에 올렸습니다.")

    assert "gratitude" not in meal["motivations"]
    assert "gratitude_moment" not in meal["target_objects"]
    assert "gratitude" not in bread["motivations"]
    assert "gratitude_moment" not in bread["target_objects"]
