from __future__ import annotations

from datetime import UTC, datetime

from src.collectors.social_public import social_source_metadata
from src.domain.models.discovery import (
    DiscoveryLane,
    IdeaArchetype,
    PublicDocument,
    SearchQuery,
    SearchResult,
)
from src.services.discovery.social import extract_social_signals, select_social_archetypes


def _document(url: str, text: str, query: str, *, access: str = "ORIGINAL_VERIFIED") -> PublicDocument:
    result = SearchResult(
        title="public social original",
        url=url,
        description="",
        provider="test-public-fetcher",
        query=query,
        rank=1,
        result_type="social_post",
    )
    return PublicDocument(
        search_result=result,
        access_level=access,  # type: ignore[arg-type]
        accessed_at=datetime(2026, 8, 12, tzinfo=UTC),
        status_code=200 if access == "ORIGINAL_VERIFIED" else None,
        content_type="text/html",
        extracted_text=text,
    )


def test_social_originals_extract_behavior_comments_and_cross_platform_archetype() -> None:
    query = SearchQuery(
        query="challenge",
        theme="social-challenge",
        lane=DiscoveryLane.BEHAVIOR_REDESIGN,
    )
    documents = [
        _document(
            "https://x.com/runner_a/status/100",
            "저는 매일 GPS 경로를 캡처해서 인증샷으로 공유했어요. 댓글: 저도 해봤어요.",
            query.query,
        ),
        _document(
            "https://www.threads.net/@runner_b/post/200",
            "나는 매주 새로운 산책 경로를 모으고 친구와 경쟁했습니다. 나도 해봤다는 댓글이 달렸어요.",
            query.query,
        ),
    ]

    signals, observations = extract_social_signals(documents, [query])
    archetypes = select_social_archetypes(signals)

    assert len({str(item.evidence.source_url) for item in observations}) == 2
    assert all(item.evidence.source_role == "FIRSTHAND_BEHAVIOR" for item in observations)
    assert any(item.comment_participation_excerpts for item in signals)
    social = next(
        item
        for item in archetypes
        if item.archetype == IdeaArchetype.SOCIAL_COMPETITION_COLLECTION
    )
    assert social.cross_source_verified is True
    assert social.platforms == ["threads", "x"]


def test_same_account_posts_do_not_claim_cross_source_confirmation() -> None:
    query = SearchQuery(
        query="challenge",
        theme="same-account",
        lane=DiscoveryLane.BEHAVIOR_REDESIGN,
    )
    documents = [
        _document(
            f"https://x.com/same_runner/status/{item}",
            "저는 매일 결과를 캡처해서 인증샷으로 공유했어요.",
            query.query,
        )
        for item in (1, 2)
    ]
    signals, _ = extract_social_signals(documents, [query])
    archetypes = select_social_archetypes(signals)
    social = next(
        item
        for item in archetypes
        if item.archetype == IdeaArchetype.SOCIAL_COMPETITION_COLLECTION
    )
    assert social.account_keys == ["x:same_runner"]
    assert social.cross_source_verified is False


def test_snippet_only_social_result_never_becomes_behavior_evidence() -> None:
    query = SearchQuery(query="social", theme="snippet")
    document = _document(
        "https://x.com/person/status/1",
        "저는 매일 여러 앱을 조합해 쓰고 있어요. 매번 귀찮아요.",
        query.query,
        access="SEARCH_SNIPPET_ONLY",
    )
    signals, observations = extract_social_signals([document], [query])
    assert signals == []
    assert observations == []


def test_platform_adapters_only_return_accounts_provable_from_url() -> None:
    assert social_source_metadata("https://x.com/alice/status/1") == ("x", "x:alice")
    assert social_source_metadata("https://www.threads.net/@bob/post/2") == (
        "threads",
        "threads:@bob",
    )
    assert social_source_metadata("https://www.youtube.com/watch?v=abc") == (
        "youtube",
        None,
    )
