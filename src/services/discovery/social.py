from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import UTC, datetime

from src.collectors.social_public import social_source_metadata
from src.domain.models.discovery import (
    BehaviorObservation,
    DiscoveryLane,
    IdeaArchetype,
    PublicDocument,
    SearchQuery,
    SocialArchetypeCandidate,
    SocialSignal,
    SocialSignalType,
)
from src.domain.models.schemas import Evidence, EvidenceGrade, EvidenceSourceRole
from src.domain.policies.evidence import freshness_score
from src.services.discovery.extraction import infer_behavior_facets

SIGNAL_PATTERNS: tuple[tuple[SocialSignalType, re.Pattern[str]], ...] = (
    (SocialSignalType.RISING_BEHAVIOR, re.compile(r"갑자기|요즘 다들|유행|뜨고 있|많이 시작|챌린지", re.I)),
    (SocialSignalType.CHALLENGE_OR_PLAY, re.compile(r"챌린지|도전|놀이|미션|연속 기록|streak", re.I)),
    (SocialSignalType.APP_STACK_HACK, re.compile(r"앱.{0,20}(같이|조합|번갈)|카톡.{0,20}엑셀|단축어|생활 해킹|꿀팁", re.I)),
    (SocialSignalType.REPEATED_FRICTION, re.compile(r"매번.{0,30}귀찮|계속.{0,30}불편|일일이|반복해서", re.I)),
    (SocialSignalType.BUILD_REQUEST, re.compile(r"누가.{0,30}(만들|해줬)|이런 앱|있으면 좋겠|제발.{0,20}기능", re.I)),
    (SocialSignalType.COMMENT_EXTENSION, re.compile(r"댓글.{0,30}(추가|요구|기능)|저도 해봤|나도 해봤|따라 해봤|해볼게", re.I)),
    (SocialSignalType.SHAREABLE_RESULT, re.compile(r"캡처|스크린샷|인증샷|결과.{0,20}공유|자랑", re.I)),
    (SocialSignalType.ORGANIC_COMPETITION_COLLECTION, re.compile(r"경쟁|랭킹|순위|수집|모으|점령|빙고|스탬프", re.I)),
)
FIRSTHAND = re.compile(
    r"(?:저는|제가|나는|내가|우리는|우리가)(?:\s|[,，])|"
    r"했어요|했습니다|해봤|쓰고 있|사용 중|시작했|모으고|공유했|찍었",
    re.I,
)
FREQUENCY = re.compile(r"매일|매주|매번|계속|반복|하루에도|\d+일|\d+주", re.I)
ENGAGEMENT = re.compile(r"(?:댓글|comments?|좋아요|likes?|조회)\s*[:：]?\s*([\d,]+)", re.I)
COMMENT_MIMICRY = re.compile(r"저도 해봤|나도 해봤|따라 해봤|해볼게|같이 하|어디서 하", re.I)


def extract_social_signals(
    documents: list[PublicDocument], queries: list[SearchQuery]
) -> tuple[list[SocialSignal], list[BehaviorObservation]]:
    query_map = {item.query: item for item in queries}
    signals: list[SocialSignal] = []
    observations: list[BehaviorObservation] = []
    for document in documents:
        result = document.search_result
        metadata = social_source_metadata(str(result.url))
        explicitly_social = result.result_type.lower() in {
            "social",
            "social_post",
            "social_thread",
            "social_comment",
        }
        if metadata is None and not explicitly_social:
            continue
        if document.access_level != "ORIGINAL_VERIFIED" or not document.extracted_text:
            continue
        query = query_map.get(result.query)
        if query is None:
            continue
        platform, account_key = metadata or ("public-social", result.author_key)
        account_key = result.author_key or account_key
        excerpts = _matching_excerpts(document.extracted_text)
        for signal_type, excerpt in excerpts:
            digest = hashlib.sha256(
                f"{result.url}:{signal_type}:{excerpt[:120]}".encode()
            ).hexdigest()[:16]
            mimicry = _comment_mimicry_excerpts(document.extracted_text)
            engagement = _engagement_count(document.extracted_text)
            signal = SocialSignal(
                signal_id=f"social:{digest}",
                theme=query.theme,
                lane=query.lane,
                signal_type=signal_type,
                platform=platform,
                source_url=result.url,
                account_key=account_key,
                excerpt=excerpt,
                observed_behavior=excerpt,
                comment_participation_excerpts=mimicry,
                engagement_count=engagement,
                published_at=result.published_at,
            )
            signals.append(signal)
            observation = _to_observation(signal, document, query)
            if observation is not None:
                observations.append(observation)
    return _deduplicate_signals(signals), _deduplicate_observations(observations)


def select_social_archetypes(signals: list[SocialSignal]) -> list[SocialArchetypeCandidate]:
    grouped: dict[IdeaArchetype, list[SocialSignal]] = defaultdict(list)
    for signal in signals:
        for archetype in _archetypes_for(signal.signal_type):
            grouped[archetype].append(signal)
    selected: list[SocialArchetypeCandidate] = []
    for archetype, items in grouped.items():
        platforms = sorted({item.platform for item in items})
        accounts = sorted({item.account_key for item in items if item.account_key})
        verified = len(accounts) >= 2 or len(platforms) >= 2
        selected.append(
            SocialArchetypeCandidate(
                archetype=archetype,
                signal_ids=sorted({item.signal_id for item in items}),
                platforms=platforms,
                account_keys=accounts,
                cross_source_verified=verified,
                rationale=(
                    f"signals={len(items)} accounts={len(accounts)} platforms={len(platforms)}; "
                    "same-account posts do not increase cross-source confidence"
                ),
            )
        )
    return sorted(selected, key=lambda item: (item.cross_source_verified, len(item.signal_ids)), reverse=True)


def _matching_excerpts(text: str) -> list[tuple[SocialSignalType, str]]:
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    found: list[tuple[SocialSignalType, str]] = []
    for index, sentence in enumerate(sentences):
        for signal_type, pattern in SIGNAL_PATTERNS:
            if not pattern.search(sentence):
                continue
            start, end = max(0, index - 1), min(len(sentences), index + 2)
            found.append((signal_type, " ".join(sentences[start:end])[:700]))
    return found


def _to_observation(
    signal: SocialSignal, document: PublicDocument, query: SearchQuery
) -> BehaviorObservation | None:
    if not FIRSTHAND.search(signal.excerpt):
        return None
    result = document.search_result
    item_key = str(result.url).split("#", 1)[0]
    # Unknown authors from the same platform share one key, preventing them from
    # masquerading as independent accounts until author metadata is verifiable.
    author_key = signal.account_key or f"unverified-account:{signal.platform}"
    evidence = Evidence(
        signal_id=signal.signal_id,
        grade=EvidenceGrade.B,
        claim=signal.excerpt,
        behavior_observed=signal.observed_behavior,
        workaround_observed=(
            signal.excerpt
            if query.lane == DiscoveryLane.PROBLEM_SOLVER
            and signal.signal_type
            in {SocialSignalType.REPEATED_FRICTION, SocialSignalType.APP_STACK_HACK}
            else None
        ),
        source_type="public_social_original",
        source_name=f"{result.provider}:{signal.platform}",
        author_key=author_key,
        original_item_key=item_key,
        original_text=signal.excerpt,
        source_url=result.url,
        published_at=result.published_at,
        collected_at=document.accessed_at or datetime.now(UTC),
        independence_key=f"{author_key.lower()}::{item_key.lower()}",
        freshness_score=freshness_score(result.published_at),
        is_fixture=result.is_fixture,
        access_level=document.access_level,
        accessed_at=document.accessed_at,
        source_role=EvidenceSourceRole.FIRSTHAND_BEHAVIOR,
        behavior_claim_verified=True,
    )
    frequency = FREQUENCY.search(signal.excerpt)
    workaround = evidence.workaround_observed
    return BehaviorObservation(
        theme=query.theme,
        lane=query.lane,
        persona="unknown: derive from public social original",
        repeated_behavior=signal.observed_behavior,
        pain=(
            "verified social post describes repeated friction"
            if signal.signal_type == SocialSignalType.REPEATED_FRICTION
            else "not required: observed social behavior is the creative substrate"
        ),
        frequency=frequency.group(0) if frequency else "unknown",
        measurable_loss="unknown",
        workaround=workaround or "not applicable: existing behavior is the creative substrate",
        **infer_behavior_facets(signal.excerpt),
        evidence=evidence,
    )


def _archetypes_for(signal_type: SocialSignalType) -> tuple[IdeaArchetype, ...]:
    if signal_type in {
        SocialSignalType.REPEATED_FRICTION,
        SocialSignalType.APP_STACK_HACK,
        SocialSignalType.BUILD_REQUEST,
    }:
        return (IdeaArchetype.PAIN_REMOVAL,)
    if signal_type in {SocialSignalType.RISING_BEHAVIOR, SocialSignalType.CHALLENGE_OR_PLAY}:
        return (IdeaArchetype.BEHAVIOR_GAMIFICATION,)
    if signal_type in {
        SocialSignalType.COMMENT_EXTENSION,
        SocialSignalType.SHAREABLE_RESULT,
        SocialSignalType.ORGANIC_COMPETITION_COLLECTION,
    }:
        return (IdeaArchetype.SOCIAL_COMPETITION_COLLECTION,)
    return ()


def _comment_mimicry_excerpts(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [item[:300] for item in sentences if COMMENT_MIMICRY.search(item)][:5]


def _engagement_count(text: str) -> int | None:
    values = [int(item.replace(",", "")) for item in ENGAGEMENT.findall(text)]
    return max(values) if values else None


def _deduplicate_signals(signals: list[SocialSignal]) -> list[SocialSignal]:
    unique: dict[tuple[str, SocialSignalType, str | None], SocialSignal] = {}
    for signal in signals:
        key = (str(signal.source_url), signal.signal_type, signal.account_key)
        unique.setdefault(key, signal)
    return list(unique.values())


def _deduplicate_observations(items: list[BehaviorObservation]) -> list[BehaviorObservation]:
    unique: dict[str, BehaviorObservation] = {}
    for item in items:
        unique.setdefault(item.evidence.signal_id, item)
    return list(unique.values())
