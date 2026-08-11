from __future__ import annotations

import json
from pathlib import Path

from src.domain.models.discovery import DiscoveryPortfolio, PortfolioCandidate


def write_portfolio(portfolio: DiscoveryPortfolio, output_dir: Path) -> Path:
    run_dir = output_dir / portfolio.run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "portfolio.json").write_text(
        json.dumps(portfolio.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "summary.md").write_text(render_summary(portfolio), encoding="utf-8")
    (run_dir / "source-audit.json").write_text(
        json.dumps(
            [item.model_dump(mode="json") for item in portfolio.source_audit],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    for candidate in portfolio.candidates:
        (run_dir / f"candidate-{candidate.rank}.md").write_text(
            render_candidate(candidate),
            encoding="utf-8",
        )
    return run_dir


def render_summary(portfolio: DiscoveryPortfolio) -> str:
    query_lines = "\n".join(f"- `{query}`" for query in portfolio.search_queries)
    exclusion_lines = (
        "\n".join(f"- {reason}: {count}" for reason, count in portfolio.exclusion_reasons.items())
        or "- 없음"
    )
    candidate_lines = (
        "\n".join(
            f"- {item.rank}. {item.thesis.idea_name} — {item.thesis.total_score}/100, "
            f"{item.thesis.verdict}, verified evidence {len(item.thesis.evidence)}"
            for item in portfolio.candidates
        )
        or "- 근거 gate를 통과한 후보 없음"
    )
    warnings = "\n".join(f"- {warning}" for warning in portfolio.warnings)
    return f"""# 조사 범위 및 근거 기반 상위 후보

> 이 결과는 전체 시장의 절대 순위가 아니다. 이번 실행의 쿼리·출처·기간 범위에서 선정한 근거 기반 상위 후보 최대 {portfolio.candidate_limit}개다.

## 조사 범위

- 실행 모드: `{portfolio.mode}`
- 탐색 주제와 문제 영역: `{portfolio.focus or "open exploration"}` / `{", ".join(portfolio.exploration_areas)}`
- 조사 기간: {portfolio.investigation_period_start.isoformat()} ~ {portfolio.investigation_period_end.isoformat()}
- 검색 공급자: `{portfolio.provider}`
- 정성 평가 LLM 공급자: `{portfolio.llm_provider}`
- 구조화 LLM 호출 수: {len(portfolio.llm_call_audit)}
- 검색 결과 수: {portfolio.result_count}
- 실제 접근·검증한 원문 수: {portfolio.original_pages_verified}
- 검색 결과 요약만 확인한 자료 수: {portfolio.snippet_only_count}
- 원문 접근 시도 수: {portfolio.original_pages_attempted}
- 제외된 자료 수: {portfolio.excluded_count}
- 최종 후보 수: {len(portfolio.candidates)}

## 생성한 검색 쿼리

{query_lines}

## 제외된 자료와 이유

{exclusion_lines}

## 근거 기반 상위 후보 최대 {portfolio.candidate_limit}개

{candidate_lines}

## 조사 한계

{warnings}
"""


def render_candidate(candidate: PortfolioCandidate) -> str:
    thesis = candidate.thesis
    evidence = "\n".join(
        f"- [{item.grade}] {item.original_text}\n"
        f"  - source: {item.source}\n"
        f"  - URL: {item.url}\n"
        f"  - published: {item.date or 'unknown'}\n"
        f"  - accessed: {item.accessed_at or 'unknown'}\n"
        f"  - access: {item.access_level}\n"
        f"  - source role: {item.source_role}\n"
        f"  - independence: {item.independence_key}"
        for item in thesis.evidence
    )
    alternatives = (
        "\n".join(
            f"- {item.name} — {item.source or 'source unknown'}; unresolved: {', '.join(item.unresolved_reasons)}"
            for item in thesis.existing_alternatives
        )
        or "- verified alternative original unavailable"
    )
    assets = "\n".join(
        f"- {item.asset}: {item.accumulation_mechanism} ({item.evidence_status})"
        for item in thesis.accumulating_assets
    )
    expansion = "\n".join(
        f"- {item.stage}. {item.problem} ← {item.asset_used}: {item.adjacency_reason} ({item.evidence_status})"
        for item in thesis.expansion_paths
    )
    scores = "\n".join(
        f"- {name}: {score.value}/{score.max_points} — {score.rationale}; confidence={score.confidence}"
        for name, score in thesis.scores.items()
    )
    validation = thesis.validation
    return f"""# Problem–Wedge–Expansion Thesis

## 1. 아이디어 이름
{thesis.idea_name}

## 2. 한 줄 논제
{thesis.one_line_thesis}

## 3. 실제 반복 행동
- 행동: {thesis.repeated_behavior}
- 빈도: {thesis.frequency}
- 시간·비용: {thesis.measurable_loss}
- 우회: {thesis.current_workaround}

## 4. 근본 문제
- 표면 불편: {thesis.surface_pain}
- 근본 원인: {thesis.root_problem}
- 사용자: {thesis.persona}

## 5. 실제 근거
{evidence}

## 6. 현재 대안
{alternatives}

## 7. 구조적 공백
{thesis.structural_gap}

## 8. 진입 해결책
{thesis.wedge_statement}

## 9. 핵심 사용자 행동
{thesis.core_user_action}

## 10. 행동 전환 이유
- 이유: {thesis.switching_reason}
- 비용: {thesis.switching_cost}
- 첫 가치: {thesis.time_to_first_value}

## 11. 축적되는 자산
{assets}

## 12. 확장 경로
{expansion}

## 13. 시장과 수익 가설
{thesis.market_and_revenue_hypothesis}

## 14. 첫 사용자 접근 경로
{thesis.first_user_access}

## 15. 가장 강한 반론
{thesis.strongest_objection}

## 16. 기각 조건
{chr(10).join(f"- {item}" for item in thesis.kill_conditions)}

## 17. 가장 저렴한 검증
- 가설: {validation.hypothesis}
- 대상: {validation.target_user}
- 방법: {validation.method}
- 기간: {validation.duration_days}일
- 성공: {validation.success_criterion}
- 실패: {validation.failure_criterion}
- 예상 비용: ${validation.estimated_cost_usd}
- 성공 후: {validation.next_action_if_pass}
- 실패 후: {validation.next_action_if_fail}

## 18. 평가 결과
{scores}
- 총점: {thesis.total_score}/100
- 확신도: {thesis.confidence}

## 19. 최종 판정
{thesis.verdict}
{"VALIDATE는 검증 완료가 아니라 Wedge 행동 실험을 실행할 가치가 있다는 뜻이다." if str(thesis.verdict) == "VALIDATE" else ""}

## 20. 다음 행동 하나
{thesis.next_action}
"""
