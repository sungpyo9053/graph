from __future__ import annotations

import re

from src.domain.models.discovery import (
    DiscoveryLane,
    DiscoveryMode,
    DiscoveryRequest,
    SearchQuery,
)

# These lanes describe observable behavior only. They intentionally contain no persona,
# root-problem, product, asset, or expansion answer.
OPEN_BEHAVIOR_QUERIES = [
    (DiscoveryLane.PROBLEM_SOLVER, "self_saved_information", '"나와의 채팅" 메모 하루에도 몇 번 불편'),
    (DiscoveryLane.PROBLEM_SOLVER, "family_handoff", '가족 돌봄 교대 카톡 메모 인수인계 반복'),
    (DiscoveryLane.PROBLEM_SOLVER, "comparison_workaround", '여러 업체 견적 일일이 비교 엑셀 메모'),
    (DiscoveryLane.BEHAVIOR_REDESIGN, "movement_ritual", '매일 걷기 달리기 산책 기록 공유 습관 후기'),
    (DiscoveryLane.BEHAVIOR_REDESIGN, "collection_ritual", '매일 수집 인증 기록 사진 공유 습관 후기'),
    (DiscoveryLane.BEHAVIOR_REDESIGN, "practice_ritual", '매일 연습 공부 독서 기록 인증 챌린지 후기'),
    (DiscoveryLane.WILD_BET, "odd_repeated_ritual", '이상하지만 매일 반복하는 습관 기록 놀이 후기'),
    (DiscoveryLane.WILD_BET, "tiny_social_ritual", '친구끼리 매일 인증 내기 수집 공유하는 행동 후기'),
    (
        DiscoveryLane.PROBLEM_SOLVER,
        "social_app_stack_hack",
        'site:x.com OR site:reddit.com OR site:threads.net "매번 귀찮" 앱 조합 꿀팁',
    ),
    (
        DiscoveryLane.BEHAVIOR_REDESIGN,
        "social_challenge_mimicry",
        "site:youtube.com OR site:tiktok.com OR site:instagram.com 챌린지 따라 해봤 인증 결과 공유",
    ),
    (
        DiscoveryLane.BEHAVIOR_REDESIGN,
        "social_share_compete_collect",
        "site:x.com OR site:threads.net OR site:reddit.com 캡처 자랑 경쟁 수집 인증 놀이",
    ),
    (
        DiscoveryLane.WILD_BET,
        "social_build_request",
        'site:x.com OR site:reddit.com OR site:threads.net "누가 이것 좀 만들어" 댓글',
    ),
]


def infer_lane_from_query(query: str) -> DiscoveryLane:
    lowered = query.lower()
    if any(term in lowered for term in ("이상", "기묘", "odd", "wild bet")):
        return DiscoveryLane.WILD_BET
    delight_terms = ("인증", "수집", "챌린지", "공유", "기록", "습관", "ritual")
    problem_terms = (
        "불편",
        "손실",
        "우회",
        "문제",
        "분쟁",
        "수작업",
        "일일이",
        "견적",
        "영수증",
        "수리 요청",
        "카톡 메모",
        "엑셀",
        "비교",
    )
    if any(term in lowered for term in problem_terms):
        return DiscoveryLane.PROBLEM_SOLVER
    if any(term in lowered for term in delight_terms):
        return DiscoveryLane.BEHAVIOR_REDESIGN
    return DiscoveryLane.PROBLEM_SOLVER


def build_query_plan(request: DiscoveryRequest) -> list[SearchQuery]:
    if request.mode == DiscoveryMode.OPEN:
        return [
            SearchQuery(query=query, theme=theme, lane=lane)
            for lane, theme, query in OPEN_BEHAVIOR_QUERIES
        ]

    focus = (request.focus or "").strip()
    slug = re.sub(r"[^0-9a-zA-Z가-힣]+", "-", focus).strip("-").lower()[:40] or "focused"
    patterns = [
        (DiscoveryLane.PROBLEM_SOLVER, "repeat", f'{focus} "매번" 직접 반복 불편 후기'),
        (DiscoveryLane.PROBLEM_SOLVER, "workaround", f'{focus} "카톡" "엑셀" 메모 우회 방법'),
        (DiscoveryLane.BEHAVIOR_REDESIGN, "ritual", f'{focus} 매일 기록 인증 수집 공유 습관 후기'),
        (DiscoveryLane.BEHAVIOR_REDESIGN, "play", f'{focus} 친구 경쟁 랭킹 꾸미기 챌린지 후기'),
        (DiscoveryLane.WILD_BET, "odd", f'{focus} 이상한 습관 매일 반복 놀이 후기'),
        (
            DiscoveryLane.BEHAVIOR_REDESIGN,
            "social",
            f"site:youtube.com OR site:tiktok.com OR site:x.com {focus} 챌린지 따라 인증 공유",
        ),
    ]
    return [
        SearchQuery(query=query, theme=f"{slug}:{kind}", lane=lane)
        for lane, kind, query in patterns
    ]
