from datetime import UTC, datetime

from src.domain.models.discovery import PublicDocument, SearchQuery, SearchResult
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
