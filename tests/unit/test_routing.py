from src.config import gates, limits
from src.domain.models.schemas import (
    EvidenceGrade,
    IdeaState,
    RiskLevel,
    Route,
    Score,
    Signal,
    WedgeCandidate,
)
from src.domain.policies.evidence import evidence_from_signal
from src.routing.policy import global_guard, route_problem_review


def score(value: int, maximum: int) -> Score:
    return Score(value=value, max_points=maximum, rationale="fixture grounded", confidence=0.8)


def wedge(**changes) -> WedgeCandidate:
    data = dict(
        name="w",
        approach_type="digest",
        target_user="판매자",
        buyer="판매자",
        user_input="URL",
        core_process="비교",
        expected_output="변화",
        switching_reason="반복 제거",
        switching_cost="URL 등록",
        time_to_first_value="하루",
        solo_first_user_value=True,
        acquisition_channel="셀러 커뮤니티",
        monetization_hypothesis="구독 가설",
        required_data="공개 URL",
        data_access_feasible=True,
        complexity="LOW",
    )
    data.update(changes)
    return WedgeCandidate(**data)


def ready_state() -> IdeaState:
    state = IdeaState(
        candidate_id="c",
        run_id="r",
        persona="판매자",
        situation="가격 확인",
        repeated_behavior="매일 확인",
        pain="시간 손실",
        frequency="매일",
        current_workaround="엑셀",
        root_problem="파편화",
        structural_gap="비표준 상태와 유지비",
        selected_wedge=wedge(),
        switching_reason="반복 제거",
        switching_cost="URL 등록",
        strongest_objection="오탐",
        kill_conditions=["전환 없음"],
    )
    state.problem_strength_score = score(15, 15)
    state.repetition_score = score(15, 15)
    state.workaround_score = score(15, 15)
    state.structural_gap_score = score(8, 10)
    state.wedge_simplicity_score = score(9, 10)
    state.switching_score = score(7, 10)
    state.asset_score = score(8, 10)
    state.expansion_score = score(8, 10)
    state.founder_fit_score = score(5, 5)
    return state


def add_evidence(state: IdeaState, count: int) -> None:
    for idx in range(count):
        signal = Signal(
            source_type="community",
            source_name="fixture",
            author_key=f"a{idx}",
            original_item_key=f"p{idx}",
            text="매일 확인 후 엑셀",
            is_fixture=True,
        )
        state.evidence.append(
            evidence_from_signal(signal, EvidenceGrade.B, "반복", workaround="엑셀")
        )


def test_problem_router_code_overrides_suggestion_and_holds_after_retry() -> None:
    state = ready_state()
    add_evidence(state, 1)
    assert (
        route_problem_review(state, limits(), gates(), Route.ANALYZE_MARKET_STRUCTURE)
        == Route.COLLECT_MORE
    )
    assert "대신 코드 정책" in state.route_reason
    state.retry_counts.evidence = limits().max_evidence_retries
    assert route_problem_review(state, limits(), gates()) == Route.HOLD


def test_global_safety_cost_and_node_guards() -> None:
    state = ready_state()
    state.risk_level = RiskLevel.BLOCKED
    state.estimated_cost = 99
    assert global_guard(state, limits())[0] == Route.REJECT
    state.risk_level = RiskLevel.LOW
    assert global_guard(state, limits())[0] == Route.HOLD
    state.estimated_cost = 0
    state.total_node_count = limits().max_total_nodes
    assert global_guard(state, limits())[0] == Route.HOLD
