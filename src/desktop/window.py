from __future__ import annotations

import asyncio
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDesktopServices,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.collectors.public_web import PublicPageFetcher
from src.collectors.verified_urls import VerifiedUrlCollector
from src.config import Settings
from src.desktop.resources import default_output_path, default_verified_urls_path
from src.desktop.topology import EDGES, NODES, EdgeSpec, normalize_runtime_node
from src.domain.models.discovery import DiscoveryMode, DiscoveryRequest
from src.domain.models.url_input import VerifiedUrlInput
from src.observability.heartbeat import reset_runtime_observer, set_runtime_observer
from src.services.discovery.orchestrator import PortfolioDiscoveryGraph
from src.services.discovery.reporting import write_portfolio

COLORS = {
    "IDLE": QColor("#243247"),
    "RUNNING": QColor("#f4b942"),
    "COMPLETED": QColor("#24b47e"),
    "REVISED": QColor("#ee8b35"),
    "FAILED": QColor("#dc5a68"),
    "HOLD": QColor("#a67ee5"),
}


class DiscoveryWorker(QThread):
    runtime_event = Signal(dict)
    run_completed = Signal(str, int)
    run_failed = Signal(str)

    def __init__(self, input_path: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.input_path = input_path

    def run(self) -> None:
        try:
            asyncio.run(self._execute())
        except Exception as exc:  # noqa: BLE001 - worker boundary reports the failure to the UI
            self.run_failed.emit(f"{type(exc).__name__}: {exc}")

    async def _execute(self) -> None:
        config = Settings()
        if config.llm_provider.lower() == "fake":
            raise ValueError("GUI live 실행은 fake LLM을 허용하지 않습니다")
        source = VerifiedUrlInput.model_validate_json(
            self.input_path.read_text(encoding="utf-8")
        )
        request = DiscoveryRequest(
            mode=DiscoveryMode.FOCUSED,
            focus=source.label,
            max_candidates=5,
            country=source.market,
            search_lang=source.language,
            lookback_days=3650,
            results_per_query=20,
            max_original_pages=30,
        )
        observer_token = set_runtime_observer(self.runtime_event.emit)
        try:
            collector = VerifiedUrlCollector(source, PublicPageFetcher())
            portfolio = await PortfolioDiscoveryGraph(
                collector,
                query_plan=source.query_plan(),
            ).run(request)
            run_dir = write_portfolio(
                portfolio,
                default_output_path(config.discovery_output_dir),
            )
            self.run_completed.emit(str(run_dir.resolve()), len(portfolio.candidates))
        finally:
            reset_runtime_observer(observer_token)


class GraphNodeItem(QGraphicsRectItem):
    WIDTH = 178
    HEIGHT = 58

    def __init__(self, name: str, label: str, x: float, y: float) -> None:
        super().__init__(0, 0, self.WIDTH, self.HEIGHT)
        self.name = name
        self.state = "IDLE"
        self.setPos(x, y)
        self.setBrush(QBrush(COLORS["IDLE"]))
        self.setPen(QPen(QColor("#53657d"), 1.5))
        self.setZValue(2)

        text = QGraphicsSimpleTextItem(label, self)
        text.setBrush(QBrush(QColor("#eef4ff")))
        text.setFont(QFont("Apple SD Gothic Neo", 10, QFont.Weight.DemiBold))
        bounds = text.boundingRect()
        text.setPos((self.WIDTH - bounds.width()) / 2, 11)

        self.status_text = QGraphicsSimpleTextItem("IDLE", self)
        self.status_text.setBrush(QBrush(QColor("#aebdd0")))
        self.status_text.setFont(QFont("Menlo", 8))
        bounds = self.status_text.boundingRect()
        self.status_text.setPos((self.WIDTH - bounds.width()) / 2, 36)

    def center(self) -> QPointF:
        return self.scenePos() + QPointF(self.WIDTH / 2, self.HEIGHT / 2)

    def set_state(self, state: str) -> None:
        self.state = state
        color = COLORS.get(state, COLORS["IDLE"])
        self.setBrush(QBrush(color))
        self.setPen(QPen(color.lighter(145), 2.5 if state == "RUNNING" else 1.5))
        self.status_text.setText(state)
        bounds = self.status_text.boundingRect()
        self.status_text.setPos((self.WIDTH - bounds.width()) / 2, 36)


class GraphEdgeItem(QGraphicsPathItem):
    def __init__(self, spec: EdgeSpec, source: GraphNodeItem, target: GraphNodeItem) -> None:
        super().__init__()
        self.spec = spec
        self.source_node = source
        self.target_node = target
        self.setZValue(1)
        self._idle_pen = QPen(QColor("#46566d"), 1.4)
        self._active_pen = QPen(QColor("#50b7ff"), 3.2)
        self._loop_pen = QPen(QColor("#ee8b35"), 3.2)
        if spec.conditional:
            self._idle_pen.setStyle(Qt.PenStyle.DashLine)
            self._active_pen.setStyle(Qt.PenStyle.DashLine)
            self._loop_pen.setStyle(Qt.PenStyle.DashLine)
        self.setPen(self._idle_pen)
        self.arrow = QGraphicsPolygonItem(self)
        self.arrow.setBrush(QBrush(QColor("#46566d")))
        self.arrow.setPen(QPen(QColor("#46566d")))
        self.label = QGraphicsSimpleTextItem(spec.label, self)
        self.label.setBrush(QBrush(QColor("#8fa6bf")))
        self.label.setFont(QFont("Menlo", 7))
        self._layout()

    def _layout(self) -> None:
        start = self.source_node.center()
        end = self.target_node.center()
        path = QPainterPath(start)
        if self.spec.loop or end.x() <= start.x():
            lift = min(start.y(), end.y()) - 65
            path.cubicTo(start.x() + 80, lift, end.x() - 80, lift, end.x(), end.y())
        else:
            middle = (start.x() + end.x()) / 2
            path.cubicTo(middle, start.y(), middle, end.y(), end.x(), end.y())
        self.setPath(path)
        end_point = path.pointAtPercent(1.0)
        before = path.pointAtPercent(0.965)
        angle_vector = end_point - before
        length = max(1.0, (angle_vector.x() ** 2 + angle_vector.y() ** 2) ** 0.5)
        ux, uy = angle_vector.x() / length, angle_vector.y() / length
        normal = QPointF(-uy, ux)
        back = end_point - QPointF(ux * 11, uy * 11)
        polygon = QPolygonF([end_point, back + normal * 5, back - normal * 5])
        self.arrow.setPolygon(polygon)
        midpoint = path.pointAtPercent(0.5)
        self.label.setPos(midpoint + QPointF(5, -15))

    def set_active(self, active: bool, revised: bool = False) -> None:
        if not active:
            self.setPen(self._idle_pen)
            color = QColor("#46566d")
        else:
            self.setPen(self._loop_pen if revised else self._active_pen)
            color = QColor("#ee8b35" if revised else "#50b7ff")
        self.arrow.setBrush(QBrush(color))
        self.arrow.setPen(QPen(color))


class GraphView(QGraphicsView):
    def wheelEvent(self, event: Any) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)
        event.accept()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Idea Discovery Graph Inspector")
        self.resize(1600, 980)
        self.worker: DiscoveryWorker | None = None
        self.result_dir: Path | None = None
        self.nodes: dict[str, GraphNodeItem] = {}
        self.edges: list[GraphEdgeItem] = []
        self.last_node: dict[str, str] = {}
        self.last_route: dict[str, str] = {}
        self.active_nodes: set[str] = set()
        self.pulse_on = False

        self._build_ui()
        self._build_scene()

        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self._pulse_running_nodes)
        self.pulse_timer.start(550)

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("검증 URL 입력"))
        default_input = default_verified_urls_path()
        self.input_edit = QLineEdit(str(default_input))
        toolbar.addWidget(self.input_edit, 1)
        browse = QPushButton("찾기…")
        browse.clicked.connect(self._browse)
        toolbar.addWidget(browse)
        self.start_button = QPushButton("아이디어 찾기")
        self.start_button.clicked.connect(self.start_discovery)
        toolbar.addWidget(self.start_button)
        self.open_result_button = QPushButton("결과 열기")
        self.open_result_button.setEnabled(False)
        self.open_result_button.clicked.connect(self._open_result)
        toolbar.addWidget(self.open_result_button)
        fit_button = QPushButton("전체 보기")
        fit_button.clicked.connect(self.fit_graph)
        toolbar.addWidget(fit_button)
        layout.addLayout(toolbar)

        splitter = QSplitter()
        self.scene = QGraphicsScene(self)
        self.view = GraphView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setBackgroundBrush(QBrush(QColor("#101722")))
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        splitter.addWidget(self.view)

        inspector = QWidget()
        inspector.setMinimumWidth(330)
        inspector_layout = QVBoxLayout(inspector)
        title = QLabel("실행 상태")
        title.setStyleSheet("font-size: 18px; font-weight: 700")
        inspector_layout.addWidget(title)
        self.run_label = QLabel("run_id: -")
        self.candidate_label = QLabel("candidate_id: -")
        self.node_label = QLabel("node: -")
        self.invocation_label = QLabel("invocation_id: -")
        self.status_label = QLabel("status: IDLE")
        self.elapsed_label = QLabel("elapsed_seconds: 0")
        for label in (
            self.run_label,
            self.candidate_label,
            self.node_label,
            self.invocation_label,
            self.status_label,
            self.elapsed_label,
        ):
            label.setTextInteractionFlags(label.textInteractionFlags())
            inspector_layout.addWidget(label)
        inspector_layout.addWidget(QLabel("이벤트 타임라인 (원문·모델 응답 미표시)"))
        self.timeline = QListWidget()
        inspector_layout.addWidget(self.timeline, 1)
        splitter.addWidget(inspector)
        splitter.setSizes([1250, 350])
        layout.addWidget(splitter, 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage("준비됨 — 휠로 확대/축소, 드래그로 이동")
        QTimer.singleShot(0, self.fit_graph)

    def _build_scene(self) -> None:
        groups: dict[str, list[Any]] = defaultdict(list)
        for spec in NODES:
            groups[spec.group].append(spec)
        for group, specs in groups.items():
            left = min(item.x for item in specs) - 25
            top = min(item.y for item in specs) - 35
            right = max(item.x for item in specs) + GraphNodeItem.WIDTH + 25
            bottom = max(item.y for item in specs) + GraphNodeItem.HEIGHT + 25
            band = QGraphicsRectItem(QRectF(left, top, right - left, bottom - top))
            band.setBrush(QBrush(QColor(25, 36, 52, 150)))
            band.setPen(QPen(QColor("#34465f"), 1))
            band.setZValue(0)
            self.scene.addItem(band)
            label = QGraphicsSimpleTextItem(group)
            label.setBrush(QBrush(QColor("#7891ad")))
            label.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
            label.setPos(left + 8, top + 7)
            label.setZValue(1)
            self.scene.addItem(label)

        for node_spec in NODES:
            item = GraphNodeItem(
                node_spec.name,
                node_spec.label,
                node_spec.x,
                node_spec.y,
            )
            self.scene.addItem(item)
            self.nodes[node_spec.name] = item
        for edge_spec in EDGES:
            edge = GraphEdgeItem(
                edge_spec,
                self.nodes[edge_spec.source],
                self.nodes[edge_spec.target],
            )
            self.scene.addItem(edge)
            self.edges.append(edge)
        self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-40, -40, 40, 40))

    def _browse(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "검증 URL JSON 선택",
            self.input_edit.text(),
            "JSON (*.json)",
        )
        if filename:
            self.input_edit.setText(filename)

    def start_discovery(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        input_path = Path(self.input_edit.text()).expanduser().resolve()
        if not input_path.is_file():
            QMessageBox.warning(self, "입력 오류", f"파일을 찾을 수 없습니다:\n{input_path}")
            return
        if os.environ.get("LLM_PROVIDER", "fake").lower() == "fake":
            QMessageBox.warning(
                self,
                "실행 차단",
                "실제 탐색 GUI는 fake LLM을 사용하지 않습니다.\nLLM_PROVIDER=codex make gui로 실행하세요.",
            )
            return
        self._reset_runtime_view()
        self.start_button.setEnabled(False)
        self.open_result_button.setEnabled(False)
        self.statusBar().showMessage("그래프 실행 중")
        self.worker = DiscoveryWorker(input_path, self)
        self.worker.runtime_event.connect(self.handle_runtime_event)
        self.worker.run_completed.connect(self._run_completed)
        self.worker.run_failed.connect(self._run_failed)
        self.worker.start()

    def handle_runtime_event(self, event: dict[str, Any]) -> None:
        raw_node = str(event.get("node", "unknown"))
        status = str(event.get("status", "RUNNING")).upper()
        candidate = str(event.get("candidate_id", "unknown"))
        node = normalize_runtime_node(raw_node, candidate)
        run_id = str(event.get("run_id", "unknown"))
        invocation = str(event.get("invocation_id", "-"))
        elapsed = float(event.get("elapsed_seconds", 0.0) or 0.0)

        self.run_label.setText(f"run_id: {run_id}")
        self.candidate_label.setText(f"candidate_id: {candidate}")
        self.node_label.setText(f"node: {raw_node}")
        self.invocation_label.setText(f"invocation_id: {invocation}")
        self.status_label.setText(f"status: {status}")
        self.elapsed_label.setText(f"elapsed_seconds: {elapsed:.1f}")
        timestamp = str(event.get("timestamp", ""))[11:19] or "--:--:--"
        self.timeline.addItem(
            f"[{timestamp}] {candidate} · {raw_node} · {status} · {elapsed:.1f}s"
        )
        self.timeline.scrollToBottom()

        item = self.nodes.get(node)
        if item is None:
            return
        if status in {"STARTED", "RUNNING"}:
            item.set_state("RUNNING")
            self.active_nodes.add(node)
        elif status in {"FAILED", "REJECTED"}:
            item.set_state("FAILED")
            self.active_nodes.discard(node)
        else:
            route = str(event.get("actual_route", "") or "").lower()
            revised = any(word in route for word in ("revise", "collect", "recluster"))
            item.set_state("REVISED" if revised else "COMPLETED")
            self.active_nodes.discard(node)

        previous = self.last_node.get(candidate)
        if previous and previous != node:
            route = self.last_route.get(candidate, "").lower()
            revised = any(word in route for word in ("revise", "collect", "recluster"))
            for edge in self.edges:
                if edge.spec.source == previous and edge.spec.target == node:
                    edge.set_active(True, revised or edge.spec.loop)
        self.last_node[candidate] = node
        self.last_route[candidate] = str(event.get("actual_route", "") or "")
        self.view.centerOn(item)

    def _pulse_running_nodes(self) -> None:
        self.pulse_on = not self.pulse_on
        for name in self.active_nodes:
            item = self.nodes.get(name)
            if item is not None:
                item.setOpacity(0.63 if self.pulse_on else 1.0)

    def _reset_runtime_view(self) -> None:
        self.timeline.clear()
        self.last_node.clear()
        self.last_route.clear()
        self.active_nodes.clear()
        self.result_dir = None
        for node in self.nodes.values():
            node.setOpacity(1.0)
            node.set_state("IDLE")
        for edge in self.edges:
            edge.set_active(False)

    def _run_completed(self, run_dir: str, candidate_count: int) -> None:
        self.result_dir = Path(run_dir)
        self.start_button.setEnabled(True)
        self.open_result_button.setEnabled(True)
        self.statusBar().showMessage(
            f"REPORT_COMPLETE — 후보 {candidate_count}개 · {self.result_dir}"
        )

    def _run_failed(self, message: str) -> None:
        self.start_button.setEnabled(True)
        self.statusBar().showMessage("실행 실패")
        QMessageBox.critical(self, "그래프 실행 실패", message)

    def _open_result(self) -> None:
        if self.result_dir is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.result_dir)))

    def fit_graph(self) -> None:
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


def save_window_screenshot(window: MainWindow, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    window.grab().save(str(destination), "PNG")


def create_application() -> QApplication:
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    return QApplication([])
