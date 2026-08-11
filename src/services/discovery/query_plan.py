from __future__ import annotations

import re

from src.domain.models.discovery import DiscoveryMode, DiscoveryRequest, SearchQuery

# These lanes describe observable behavior only. They intentionally contain no persona,
# root-problem, product, asset, or expansion answer.
OPEN_BEHAVIOR_QUERIES = [
    ("self_saved_information", '"나와의 채팅" 메모 하루에도 몇 번 불편'),
    ("family_handoff", '가족 돌봄 교대 카톡 메모 인수인계 반복'),
    ("purchase_proof", '영수증 보증서 매번 찾기 직접 보관 불편'),
    ("service_dispute", '수리 견적 사진 문자 카톡 기록 분쟁 반복'),
    ("availability_checking", '여러 곳 전화 직접 확인 재고 예약 반복'),
    ("document_reentry", '같은 정보 여러 사이트 일일이 입력 반복'),
    ("local_coordination", '동네 사람 여러 곳 게시 문의 직접 찾기 반복'),
    ("comparison_workaround", '여러 업체 견적 일일이 비교 엑셀 메모'),
]


def build_query_plan(request: DiscoveryRequest) -> list[SearchQuery]:
    if request.mode == DiscoveryMode.OPEN:
        return [
            SearchQuery(query=query, theme=theme)
            for theme, query in OPEN_BEHAVIOR_QUERIES
        ]

    focus = (request.focus or "").strip()
    slug = re.sub(r"[^0-9a-zA-Z가-힣]+", "-", focus).strip("-").lower()[:40] or "focused"
    patterns = [
        ("repeat", f'{focus} "매번" 직접 반복 불편 후기'),
        ("workaround", f'{focus} "카톡" "엑셀" 메모 우회 방법'),
        ("checking", f'{focus} 여러 곳 일일이 확인 전화 검색'),
        ("payment", f'{focus} 대신 비용 지불 외주 수작업 경험'),
    ]
    return [
        SearchQuery(query=query, theme=f"{slug}:{kind}")
        for kind, query in patterns
    ]
