from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter

from src.agents.atomic import trace
from src.observability.heartbeat import (
    reset_invocation_context,
    reset_runtime_observer,
    set_invocation_context,
    set_runtime_observer,
)


def test_trace_publishes_sanitizable_runtime_event() -> None:
    events: list[dict] = []
    observer_token = set_runtime_observer(events.append)
    invocation_tokens = set_invocation_context("run-1", "candidate-2")
    try:
        record = trace(
            "design_wedge_candidates",
            datetime.now(UTC),
            perf_counter(),
            "internal detail that the native timeline does not display",
            actual_route="DESIGN_VALIDATION",
        )
    finally:
        reset_invocation_context(invocation_tokens)
        reset_runtime_observer(observer_token)

    assert record["node"] == "design_wedge_candidates"
    assert len(events) == 1
    assert events[0] == {
        "kind": "NODE",
        "run_id": "run-1",
        "candidate_id": "candidate-2",
        "node": "design_wedge_candidates",
        "status": "SUCCEEDED",
        "timestamp": record["completed_at"].isoformat(),
        "elapsed_seconds": record["duration_ms"] / 1000,
        "actual_route": "DESIGN_VALIDATION",
        "route_reason": "",
        "detail": "internal detail that the native timeline does not display",
    }
