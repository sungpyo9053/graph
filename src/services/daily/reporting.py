from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from src.domain.models.daily import DailyCandidateChange, DailyRunResult


def write_daily_result(result: DailyRunResult, output_root: Path) -> Path:
    run_dir = output_root / "daily" / result.run_date.isoformat() / result.run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    _write_json(run_dir / "new-candidates.json", result.new_candidates)
    _write_json(run_dir / "updated-candidates.json", result.updated_candidates)
    _write_json(run_dir / "rejected-candidates.json", result.rejected_candidates)
    _write_json(run_dir / "source-audit.json", result.source_audit)
    (run_dir / "graph-run.json").write_text(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "review-packet.md").write_text(
        render_review_packet(result), encoding="utf-8"
    )
    return run_dir


def render_review_packet(result: DailyRunResult) -> str:
    portfolio = result.portfolio
    queries = "\n".join(f"- `{query}`" for query in portfolio.search_queries)
    candidate_sections = "\n\n".join(
        _render_candidate(index, item)
        for index, item in enumerate(result.review_candidates, start=1)
    ) or "근거 gate와 과거 중복 검사를 통과한 신규 또는 갱신 후보가 없습니다."
    limitations = "\n".join(f"- {item}" for item in result.limitations)
    insufficient = len(result.rejected_candidates)
    return f"""# {result.title}

> 전체 시장의 절대 순위가 아닙니다. {result.run_date.isoformat()} 실행의 쿼리·Brave 인덱스·조사 기간·접근 가능한 원문과 전체 과거 후보 비교 범위 안의 결과입니다.

## 오늘 조사 요약

- 실행 모드: `{portfolio.mode}`
- 시장/언어: `{portfolio.country}` / `{portfolio.search_language}`
- 조사 기간: {portfolio.investigation_period_start.isoformat()} ~ {portfolio.investigation_period_end.isoformat()}
- 검색 결과 수: {portfolio.result_count}
- 실제 확인한 원문 수: {portfolio.original_pages_verified}
- 검색 결과 요약만 확인한 자료 수: {portfolio.snippet_only_count}
- 신규 후보 수: {len(result.new_candidates)}
- 갱신·재개 후보 수: {len(result.updated_candidates)}
- 중복 제외 수: {len(result.duplicate_candidates)}
- 근거 부족 제외 수: {insufficient}
- 오늘 검토할 후보 수: {len(result.review_candidates)} / 최대 5개

## 오늘 생성한 검색 쿼리

{queries}

## 오늘 검토할 후보 최대 5개

{candidate_sections}

## 조사 한계

{limitations}
"""


def _render_candidate(index: int, change: DailyCandidateChange) -> str:
    record = change.candidate
    thesis = record.thesis
    urls = "\n".join(
        f"- {evidence.source_url} ([{evidence.grade}] {evidence.source_name})"
        for evidence in record.evidence
    ) or "- 없음"
    score_delta = _delta(record.score, change.previous_score)
    evidence_before = len(record.evidence) - change.evidence_added
    status_before = change.previous_status or "없음"
    objection = thesis.strongest_objection if thesis else "논제 미생성"
    next_action = thesis.next_action if thesis else "추가 독립 원문 근거를 수집한다"
    return f"""### {index}. [{change.classification}] {record.candidate_id}

- 근본 문제: {record.root_problem}
- 사용자: {record.persona}
- 반복 행동: {record.repeated_behavior}
- 우회 행동: {record.workaround}
- 전날/직전 저장값 대비 점수: {change.previous_score if change.previous_score is not None else '신규'} → {record.score} ({score_delta})
- 전날/직전 저장값 대비 근거: {evidence_before} → {len(record.evidence)} (+{change.evidence_added})
- 전날/직전 저장값 대비 상태: {status_before} → {record.status}
- 분류 이유: {change.reason}
- 가장 강한 반론: {objection}
- 다음 행동: {next_action}

실제 출처 URL:

{urls}"""


def _delta(current: int, previous: int | None) -> str:
    if previous is None:
        return "신규"
    difference = current - previous
    return f"{difference:+d}"


def _write_json(path: Path, values: Sequence[object]) -> None:
    payload = [
        value.model_dump(mode="json") if hasattr(value, "model_dump") else value
        for value in values
    ]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
