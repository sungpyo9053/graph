from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.desktop.topology import EDGES, NODES  # noqa: E402
from src.desktop.window import MainWindow, create_application  # noqa: E402


def test_native_window_renders_graph_and_animates_runtime_edge() -> None:
    app = create_application()
    window = MainWindow()
    try:
        assert len(window.nodes) == len(NODES)
        assert len(window.edges) == len(EDGES)
        window.handle_runtime_event(
            {
                "timestamp": "2026-08-12T12:01:03+00:00",
                "run_id": "run-ui",
                "candidate_id": "portfolio",
                "node": "plan_queries",
                "status": "SUCCEEDED",
                "elapsed_seconds": 0.02,
            }
        )
        window.handle_runtime_event(
            {
                "timestamp": "2026-08-12T12:01:04+00:00",
                "run_id": "run-ui",
                "candidate_id": "portfolio",
                "node": "collect_behavior_sources",
                "invocation_id": "inv-1",
                "status": "STARTED",
                "elapsed_seconds": 0.0,
            }
        )
        app.processEvents()
        assert window.nodes["portfolio:plan_queries"].state == "COMPLETED"
        assert window.nodes["portfolio:collect_behavior_sources"].state == "RUNNING"
        edge = next(
            item
            for item in window.edges
            if item.spec.source == "portfolio:plan_queries"
            and item.spec.target == "portfolio:collect_behavior_sources"
        )
        assert edge.pen().widthF() == pytest.approx(3.2)
        assert "internal detail" not in " ".join(
            window.timeline.item(index).text() for index in range(window.timeline.count())
        )
    finally:
        window.close()
