from src.domain.models.schemas import IdeaState, Score, unknown_score
from src.domain.policies.evidence import independent_qualifying_evidence


def grounded_score(value: int, maximum: int, rationale: str, confidence: float) -> Score:
    if not rationale.strip():
        return unknown_score(maximum, "근거 문자열이 없어 0점 처리")
    return Score(
        value=min(value, maximum), max_points=maximum, rationale=rationale, confidence=confidence
    )


def evaluate_problem_scores(state: IdeaState) -> None:
    evidence = independent_qualifying_evidence(state.evidence)
    behavior_count = sum(bool(item.behavior_observed) for item in evidence)
    workaround_count = sum(bool(item.workaround_observed) for item in evidence)
    if not evidence:
        state.problem_strength_score = unknown_score(15, "독립 A~C 근거 없음")
        state.repetition_score = unknown_score(15, "반복성 근거 없음")
        state.workaround_score = unknown_score(15, "우회 행동 근거 없음")
        return
    state.problem_strength_score = grounded_score(
        min(15, 5 + 5 * len(evidence)),
        15,
        f"독립 A~C 근거 {len(evidence)}개가 구체적 불편을 관찰",
        min(1, len(evidence) / 3),
    )
    state.repetition_score = grounded_score(
        min(15, behavior_count * 7),
        15,
        f"반복 행동이 명시된 독립 근거 {behavior_count}개; 빈도 표현: {state.frequency or 'unknown'}",
        min(1, behavior_count / 2),
    )
    state.workaround_score = grounded_score(
        min(15, workaround_count * 8),
        15,
        f"실제 우회 행동이 명시된 독립 근거 {workaround_count}개",
        min(1, workaround_count / 2),
    )


def evaluate_thesis_scores(state: IdeaState) -> None:
    evaluate_problem_scores(state)
    if state.structural_gap:
        state.structural_gap_score = grounded_score(
            8, 10, f"대안 분석에서 확인된 공백: {state.structural_gap}", 0.6
        )
    if state.selected_wedge:
        simple = (
            state.selected_wedge.complexity == "LOW" and state.selected_wedge.solo_first_user_value
        )
        state.wedge_simplicity_score = grounded_score(
            9 if simple else 3,
            10,
            f"복잡도 {state.selected_wedge.complexity}; 첫 사용자 단독 가치 {state.selected_wedge.solo_first_user_value}",
            0.8,
        )
        state.switching_score = grounded_score(
            7 if state.selected_wedge.solo_first_user_value else 2,
            10,
            f"전환 이유: {state.switching_reason}; 전환 비용: {state.switching_cost}",
            0.6,
        )
    if state.accumulating_assets:
        grounded = [
            asset for asset in state.accumulating_assets if asset.evidence_status != "UNSUPPORTED"
        ]
        state.asset_score = grounded_score(
            min(10, len(grounded) * 4), 10, f"축적 메커니즘이 있는 자산 {len(grounded)}개", 0.5
        )
    if state.expansion_paths:
        paths = [path for path in state.expansion_paths if path.evidence_status != "UNSUPPORTED"]
        state.expansion_score = grounded_score(
            min(10, len(paths) * 4), 10, f"축적 자산과 연결된 인접 경로 {len(paths)}개", 0.4
        )
    state.founder_fit_score = grounded_score(
        5,
        5,
        "Python·백엔드·SRE·관측성·운영 자동화 경험과 변화 감지 문제의 직접 연관",
        0.9,
    )
