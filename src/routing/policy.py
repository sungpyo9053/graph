from datetime import UTC, datetime

from src.config import Limits, QualityGates
from src.domain.models.schemas import IdeaState, RiskLevel, Route
from src.domain.policies.evidence import independent_qualifying_evidence


def choose(state: IdeaState, actual: Route, reason: str, suggested: Route | None = None) -> Route:
    state.suggested_next_route = suggested
    state.actual_next_route = actual
    if suggested is not None and suggested != actual:
        state.route_reason = f"제안 {suggested} 대신 코드 정책 적용: {reason}"
    else:
        state.route_reason = reason
    return actual


def global_guard(state: IdeaState, cfg: Limits) -> tuple[Route, str] | None:
    if state.risk_level == RiskLevel.BLOCKED:
        return Route.REJECT, "치명적인 정책·데이터 위험은 점수와 무관하게 기각"
    elapsed = (datetime.now(UTC) - state.started_at).total_seconds() / 60
    if state.estimated_cost >= cfg.max_estimated_cost_usd:
        return Route.HOLD, "예상 비용 한도 도달"
    if state.total_model_calls >= cfg.max_total_model_calls:
        return Route.HUMAN_REVIEW, "모델 호출 한도 도달"
    if elapsed >= cfg.max_elapsed_minutes:
        return Route.HOLD, "실행 시간 한도 도달"
    if state.total_node_count >= cfg.max_total_nodes:
        return Route.HOLD, "전체 노드 실행 한도 도달"
    return None


def route_problem_review(
    state: IdeaState,
    cfg: Limits,
    quality: QualityGates,
    suggested: Route | None = None,
) -> Route:
    guard = global_guard(state, cfg)
    if guard:
        return choose(state, *guard, suggested=suggested)
    if state.duplicate_candidate_id:
        return choose(state, Route.MERGE_EXISTING, "기존 문제와 중복 임계값 초과", suggested)
    independent = len(independent_qualifying_evidence(state.evidence))
    workaround_count = sum(
        bool(item.workaround_observed) for item in independent_qualifying_evidence(state.evidence)
    )
    evidence_points = (
        state.problem_strength_score.value
        + state.repetition_score.value
        + state.workaround_score.value
    )
    missing = [
        field for field in quality.problem_gate.required_fields if not getattr(state, field, None)
    ]
    state.missing_fields = missing
    if (
        independent < quality.problem_gate.minimum_independent_sources
        or workaround_count == 0
        or evidence_points < quality.problem_gate.minimum_problem_evidence_points
    ):
        if state.retry_counts.evidence < cfg.max_evidence_retries:
            state.retry_counts.evidence += 1
            return choose(
                state,
                Route.COLLECT_MORE,
                f"행동 근거 게이트 미충족: 독립 {independent}, 우회 {workaround_count}, 근거 점수 {evidence_points}",
                suggested,
            )
        return choose(
            state, Route.HOLD, "추가 수집 한도 후에도 독립 행동·우회 근거 부족", suggested
        )
    surface_only = not state.root_problem or state.root_problem.strip() == state.pain.strip()
    if missing or surface_only:
        if state.retry_counts.root_problem < cfg.max_root_problem_retries:
            state.retry_counts.root_problem += 1
            return choose(
                state,
                Route.REVISE_ROOT_PROBLEM,
                f"근본 문제 필드 미충족 또는 표면 불편과 동일: {missing}",
                suggested,
            )
        return choose(state, Route.HOLD, "근본 문제 재분석 한도 도달", suggested)
    if state.risk_level in {RiskLevel.MEDIUM, RiskLevel.HIGH}:
        return choose(
            state, Route.HUMAN_REVIEW, f"{state.risk_level} 위험은 사람 검토 필요", suggested
        )
    return choose(
        state,
        Route.ANALYZE_MARKET_STRUCTURE,
        "독립 행동·우회 근거와 근본 문제 게이트 통과",
        suggested,
    )
