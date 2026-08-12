from datetime import UTC, datetime

from src.domain.models.discovery import PublicDocument, SearchQuery, SearchResult
from src.domain.models.schemas import EvidenceSourceRole
from src.services.discovery.extraction import extract_observations


def test_korean_repeated_behavior_and_workaround_are_extracted() -> None:
    query = SearchQuery(
        query="카톡 나와의 채팅 반복 메모",
        theme="personal_action_inbox",
    )
    result = SearchResult(
        title="직접 사용 후기",
        url="https://example.com/original",
        description="",
        provider="verified-url-input",
        query=query.query,
        rank=1,
    )
    document = PublicDocument(
        search_result=result,
        access_level="ORIGINAL_VERIFIED",
        accessed_at=datetime.now(UTC),
        status_code=200,
        content_type="text/html",
        extracted_text=(
            "급한 링크를 카톡 나와의 채팅에 하루에도 몇 번씩 메모합니다. "
            "나중에는 자료가 섞여서 필요한 내용을 일일이 검색합니다."
        ),
    )

    observations, exclusions = extract_observations([document], [query])

    assert exclusions == {}
    assert len(observations) == 1
    assert observations[0].frequency == "하루에도 몇 번씩"
    assert observations[0].evidence.grade.value == "B"
    assert observations[0].evidence.source_role == EvidenceSourceRole.FIRSTHAND_BEHAVIOR


def _document(text: str, *, source_type: str = "community", suffix: str = "case") -> PublicDocument:
    query = "택배 사고 반복 행동"
    return PublicDocument(
        search_result=SearchResult(
            title="원문",
            url=f"https://example.com/{suffix}",
            description="",
            provider="verified-url-input",
            query=query,
            rank=1,
            result_type=source_type,
        ),
        access_level="ORIGINAL_VERIFIED",
        accessed_at=datetime.now(UTC),
        status_code=200,
        content_type="text/html",
        extracted_text=text,
    )


def test_procedural_shipping_guide_is_not_counted_as_behavior_evidence() -> None:
    query = SearchQuery(query="택배 사고 반복 행동", theme="shipping-claim")
    guide = _document(
        "파손 사고가 나면 매번 사진을 촬영하고 고객센터에 전화해야 합니다. "
        "구매 영수증도 제출해야 합니다.",
        source_type="official",
        suffix="guide",
    )

    observations, exclusions = extract_observations([guide], [query])

    assert observations == []
    assert exclusions["not_firsthand_behavior:official_process"] == 1


def test_firsthand_shipping_account_is_counted_as_behavior_evidence() -> None:
    query = SearchQuery(query="택배 사고 반복 행동", theme="shipping-claim")
    account = _document(
        "지난달 택배가 파손되어 저는 직접 사진을 찍고 고객센터에 여러 번 전화했습니다. "
        "영수증도 따로 보관했습니다.",
        suffix="firsthand",
    )

    observations, exclusions = extract_observations([account], [query])

    assert exclusions == {}
    assert len(observations) == 1
    assert observations[0].evidence.source_role == EvidenceSourceRole.FIRSTHAND_BEHAVIOR


def test_korean_word_fragment_does_not_fake_first_person_evidence() -> None:
    query = SearchQuery(query="택배 사고 반복 행동", theme="shipping-claim")
    guide = _document(
        "물품을 매번 확인하고 문제가 있을 경우 사진을 보관해야 합니다.",
        suffix="word-fragment",
    )

    observations, exclusions = extract_observations([guide], [query])

    assert observations == []
    assert sum(exclusions.values()) == 1


def test_extractor_prefers_firsthand_behavior_over_early_title_match() -> None:
    query = SearchQuery(
        query="매일 걷기 달리기 기록 공유 습관 후기",
        theme="movement-ritual",
        lane="BEHAVIOR_REDESIGN",
    )
    document = _document(
        "매일 달리기 실제 후기. 메뉴와 사이트 소개입니다. "
        "저는 여행 이후 매일 아침 30분씩 달리기 시작했습니다. "
        "두 주 동안 기록을 남기고 친구에게 공유했습니다.",
        suffix="late-firsthand",
    )
    document.search_result.query = query.query

    observations, exclusions = extract_observations([document], [query])

    assert exclusions == {}
    assert len(observations) == 1
    assert "저는 여행 이후" in observations[0].repeated_behavior
