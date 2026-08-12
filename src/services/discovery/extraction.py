from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime
from urllib.parse import urlparse

from src.domain.models.discovery import (
    BehaviorObservation,
    DiscoveryLane,
    PublicDocument,
    SearchQuery,
)
from src.domain.models.schemas import Evidence, EvidenceGrade, EvidenceSourceRole
from src.domain.policies.evidence import freshness_score

BEHAVIOR_TERMS = re.compile(
    r"(manually|manual|every day|every week|every month|daily|weekly|repeatedly|"
    r"copy(?:ing)? and paste|copy-paste|check multiple|called multiple|spreadsheet|excel|"
    r"수동|매일|매주|매월|매번|매번마다|반복|계속|항상|하루에도|몇 번씩|여러 번|"
    r"일일이|직접|엑셀|여러 곳|여러 군데|돌아다니|뒤지|찾아보|확인하|기록하|메모하|"
    r"달리|뛰|걷|산책|연습|공부|독서|인증|수집|공유하|사진을 찍)",
    re.IGNORECASE,
)
WORKAROUND_TERMS = re.compile(
    r"(spreadsheet|excel|manual|manually|copy|paste|call|phone|email|message|"
    r"workaround|double.?check|track|수동|엑셀|전화|문자|메시지|카톡|나와의 채팅|"
    r"메모|사진|캡처|영수증|보증서|견적|링크|검색|문의|보관|재확인)",
    re.IGNORECASE,
)
PAYMENT_TERMS = re.compile(
    r"(paid|paying|hired|contractor|bought|purchased|built|outsourced|고용|결제|구매|"
    r"외주|지불|수리비|비용|돈을 들|유상)",
    re.IGNORECASE,
)
COMPLAINT_TERMS = re.compile(
    r"(frustrat|pain|annoy|looking for|alternative|doesn.t work|workaround|불편|대안|"
    r"곤란|막상 필요한|찾기 어렵|누락|분쟁)",
    re.IGNORECASE,
)
FREQUENCY = re.compile(
    r"(every\s+(?:day|week|month)|daily|weekly|monthly|\d+\s+times?\s+(?:a|per)\s+\w+|"
    r"매일|매주|매월|매번|항상|계속|하루에도\s*(?:\d+|몇)\s*번(?:씩)?|몇\s*번(?:이나|씩)?)",
    re.IGNORECASE,
)
LOSS = re.compile(
    r"\b(?:about\s+|roughly\s+)?\d+(?:\.\d+)?\s*(?:hours?|hrs?|minutes?|mins?|days?|시간|분|일)\b",
    re.IGNORECASE,
)
FIRSTHAND_MARKERS = re.compile(
    r"(?:\b(?:i|we|my|our)\b|i['’]?ve|i\s+(?:had to|keep|kept|called|paid|bought|"
    r"recorded|checked|used)|(?<![가-힣])(?:저는|제가|나는|내가|우리는|우리가)(?![가-힣])|"
    r"(?:했어요|했습니다|했다|했는데|해봤|걸렸어요|걸렸다|연락했|전화했|"
    r"기록했|쓰고\s*있|사용\s*중)|나중에는|경험상)",
    re.IGNORECASE,
)
PROCEDURAL_MARKERS = re.compile(
    r"(?:how\s+to|steps?\s+to|you\s+(?:should|must|need to)|is required|guide|"
    r"방법|절차|가이드|준비(?:물|해야)|해야\s*(?:합니다|한다|됩니다)|하세요|하십시오|"
    r"제출(?:해야|합니다)|접수(?:해야|방법|절차)|필요(?:합니다|하다)|경우에는)",
    re.IGNORECASE,
)
OFFICIAL_SOURCE_TYPES = {"official", "company", "product", "government", "policy"}
SECONDARY_SOURCE_TYPES = {"news", "report", "research", "article"}


def extract_observations(
    documents: list[PublicDocument],
    queries: list[SearchQuery],
) -> tuple[list[BehaviorObservation], Counter[str]]:
    query_map = {item.query: item for item in queries}
    observations: list[BehaviorObservation] = []
    exclusions: Counter[str] = Counter()
    seen_urls: set[str] = set()
    for document in documents:
        result = document.search_result
        url = str(result.url)
        if document.access_level != "ORIGINAL_VERIFIED" or not document.extracted_text:
            exclusions[f"snippet_only:{document.error_reason or 'not_fetched'}"] += 1
            continue
        if url in seen_urls:
            exclusions["duplicate_url"] += 1
            continue
        seen_urls.add(url)
        excerpt = _behavior_excerpt(document.extracted_text)
        if excerpt is None:
            exclusions["verified_original_without_repeated_behavior"] += 1
            continue
        query = query_map.get(result.query)
        if query is None:
            exclusions["query_metadata_missing"] += 1
            continue
        if (
            query.lane == DiscoveryLane.PROBLEM_SOLVER
            and not WORKAROUND_TERMS.search(excerpt)
        ):
            exclusions["verified_original_without_workaround"] += 1
            continue
        source_role = classify_source_role(result.result_type, excerpt)
        if source_role != EvidenceSourceRole.FIRSTHAND_BEHAVIOR:
            exclusions[f"not_firsthand_behavior:{source_role.value.lower()}"] += 1
            continue
        grade = _grade(excerpt, source_role, query.lane)
        workaround = (
            excerpt
            if query.lane == DiscoveryLane.PROBLEM_SOLVER
            and WORKAROUND_TERMS.search(excerpt)
            else None
        )
        host = (urlparse(url).hostname or "unknown").lower()
        item_key = url.split("#", 1)[0]
        published = result.published_at
        evidence = Evidence(
            signal_id=f"live:{item_key}",
            grade=grade,
            claim=excerpt,
            behavior_observed=excerpt,
            workaround_observed=workaround,
            source_type="public_web_original",
            source_name=f"{result.provider}:{host}",
            author_key=result.author_key or f"unknown-author:{item_key}",
            original_item_key=item_key,
            original_text=excerpt,
            source_url=result.url,
            published_at=published,
            collected_at=document.accessed_at or datetime.now(UTC),
            independence_key=f"{host}::{item_key.lower()}",
            freshness_score=freshness_score(published),
            is_fixture=result.is_fixture,
            access_level=document.access_level,
            accessed_at=document.accessed_at,
            source_role=source_role,
            behavior_claim_verified=True,
        )
        observations.append(
            BehaviorObservation(
                theme=query.theme,
                lane=query.lane,
                persona="unknown: derive from quoted original",
                repeated_behavior=excerpt,
                pain=_pain(excerpt),
                frequency=_match_or_unknown(FREQUENCY, excerpt),
                measurable_loss=_match_or_unknown(LOSS, excerpt),
                workaround=(
                    excerpt
                    if workaround
                    else "not applicable: existing behavior is the creative substrate"
                ),
                evidence=evidence,
            )
        )
    return observations, exclusions


def _behavior_excerpt(text: str) -> str | None:
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    candidates: list[tuple[int, int, str]] = []
    for index, sentence in enumerate(sentences):
        if not BEHAVIOR_TERMS.search(sentence):
            continue
        start = max(0, index - 1)
        end = min(len(sentences), index + 2)
        excerpt = " ".join(sentences[start:end])[:900]
        score = 1
        score += 12 if FIRSTHAND_MARKERS.search(excerpt) else 0
        score += 6 if FREQUENCY.search(excerpt) else 0
        score += min(4, len(BEHAVIOR_TERMS.findall(excerpt)))
        score += 2 if WORKAROUND_TERMS.search(excerpt) else 0
        if PROCEDURAL_MARKERS.search(excerpt) and not FIRSTHAND_MARKERS.search(excerpt):
            score -= 8
        # Prefer richer first-person passages over navigation/title fragments on pages
        # whose HTML has been flattened to one line.
        candidates.append((score, len(excerpt), excerpt))
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def classify_source_role(source_type: str, text: str) -> EvidenceSourceRole:
    normalized_type = source_type.strip().lower()
    firsthand = bool(FIRSTHAND_MARKERS.search(text))
    procedural = bool(PROCEDURAL_MARKERS.search(text))
    if normalized_type in OFFICIAL_SOURCE_TYPES:
        return EvidenceSourceRole.OFFICIAL_PROCESS
    if firsthand:
        return EvidenceSourceRole.FIRSTHAND_BEHAVIOR
    if procedural:
        return EvidenceSourceRole.PROCEDURAL_GUIDE
    if normalized_type in SECONDARY_SOURCE_TYPES:
        return EvidenceSourceRole.SECONDARY_REPORT
    return EvidenceSourceRole.UNCLASSIFIED


def _grade(
    text: str,
    source_role: EvidenceSourceRole,
    lane: DiscoveryLane,
) -> EvidenceGrade:
    if source_role != EvidenceSourceRole.FIRSTHAND_BEHAVIOR:
        return EvidenceGrade.D
    if PAYMENT_TERMS.search(text):
        return EvidenceGrade.A
    if lane != DiscoveryLane.PROBLEM_SOLVER and BEHAVIOR_TERMS.search(text):
        return EvidenceGrade.B
    if BEHAVIOR_TERMS.search(text) and WORKAROUND_TERMS.search(text):
        return EvidenceGrade.B
    if COMPLAINT_TERMS.search(text):
        return EvidenceGrade.C
    return EvidenceGrade.D


def _pain(text: str) -> str:
    loss = LOSS.search(text)
    if loss:
        return f"verified original mentions measurable effort: {loss.group(0)}"
    if re.search(r"risk|error|miss|late|wrong|불안|오류|누락", text, re.IGNORECASE):
        return "verified original describes error, delay, or missed-state risk"
    return "verified original shows repeated manual effort; exact loss remains unknown"


def _match_or_unknown(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return match.group(0) if match else "unknown"
