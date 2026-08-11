from datetime import UTC, datetime

from src.domain.models.schemas import EvidenceGrade, IdeaState, RiskLevel, Signal, WedgeCandidate
from src.domain.policies.duplicates import (
    DeterministicTokenEmbedding,
    behavior_solution_signature,
    jaccard,
    problem_similarity,
    same_behavior_solution_archetype,
    wedge_similarity,
)
from src.domain.policies.evidence import evidence_from_signal, independent_qualifying_evidence
from src.domain.policies.risk import assess_risk
from src.domain.scoring.scoring import evaluate_problem_scores


def signal(author: str, item: str) -> Signal:
    return Signal(
        source_type="community",
        source_name="fixture",
        author_key=author,
        original_item_key=item,
        text="매일 가격 확인 후 엑셀 기록",
        published_at=datetime.now(UTC),
        is_fixture=True,
    )


def wedge() -> WedgeCandidate:
    return WedgeCandidate(
        name="w",
        approach_type="digest",
        target_user="판매자",
        buyer="판매자",
        user_input="URL",
        core_process="변화 비교",
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


def test_evidence_independence_and_workaround_weight() -> None:
    first = evidence_from_signal(signal("same", "post"), EvidenceGrade.B, "반복", workaround="엑셀")
    derived = evidence_from_signal(
        signal("same", "post"), EvidenceGrade.C, "파생", workaround="엑셀"
    )
    other = evidence_from_signal(
        signal("other", "review"), EvidenceGrade.C, "불만", workaround="수동 재확인"
    )
    assert len(independent_qualifying_evidence([first, derived, other])) == 2
    state = IdeaState(
        candidate_id="c", run_id="r", evidence=[first, derived, other], frequency="매일"
    )
    evaluate_problem_scores(state)
    assert state.workaround_score.value == 15
    assert state.problem_strength_score.rationale


def test_no_evidence_means_zero_unknown_not_midpoint() -> None:
    state = IdeaState(candidate_id="c", run_id="r")
    evaluate_problem_scores(state)
    assert state.problem_strength_score.value == 0
    assert state.problem_strength_score.unknown is True


def test_problem_and_wedge_duplicate_logic_is_deterministic() -> None:
    fields = {
        "persona": "온라인 판매자",
        "situation": "가격 확인",
        "repeated_behavior": "매일 확인",
        "pain": "시간",
        "current_workaround": "엑셀",
        "root_problem": "파편화",
    }
    assert problem_similarity(fields, fields) == 1
    assert wedge_similarity(wedge(), wedge()) == 1
    assert jaccard("가격 가격 확인", "가격 확인") == 1
    assert DeterministicTokenEmbedding().embed("같은 입력") == DeterministicTokenEmbedding().embed(
        "같은 입력"
    )


def test_risk_policy_precedence() -> None:
    assert assess_risk("무단 계정 탈취 후 개인정보 크롤링")[0] == RiskLevel.BLOCKED
    assert assess_risk("공개 페이지 크롤링")[0] == RiskLevel.MEDIUM
    assert assess_risk("반복 작업 정리")[0] == RiskLevel.LOW


def test_korean_paraphrase_maps_to_same_behavior_solution_archetype() -> None:
    left = behavior_solution_signature(
        repeated_behavior="여러 약국에 직접 전화한다",
        workaround="약국에 일일이 전화",
        wedge_input="처방약 이름 입력",
        wedge_output="확인 가능한 약국 결과",
        solution_archetype="단일 결과",
    )
    right = behavior_solution_signature(
        repeated_behavior="약국마다 재고 문의 전화를 돌린다",
        workaround="재고 문의 전화",
        wedge_input="처방약 이름 입력",
        wedge_output="확인 가능한 약국 결과",
        solution_archetype="결과 리포트",
    )
    assert same_behavior_solution_archetype(left, right) is True


def test_same_domain_with_different_behavior_and_solution_is_preserved() -> None:
    stock_call = behavior_solution_signature(
        repeated_behavior="약국마다 재고 문의 전화를 돌린다",
        workaround="전화 문의",
        wedge_input="약 이름",
        wedge_output="재고 확인 결과",
        solution_archetype="단일 결과",
    )
    prescription_handoff = behavior_solution_signature(
        repeated_behavior="약국에 처방전 사진을 보낸다",
        workaround="카톡 메시지 전송",
        wedge_input="처방전 사진",
        wedge_output="조제 요청 기록",
        solution_archetype="기록 이력",
    )
    assert same_behavior_solution_archetype(stock_call, prescription_handoff) is False
