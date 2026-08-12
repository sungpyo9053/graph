from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from pydantic import BaseModel

from src.graphs.candidate import (
    build_candidate_finalization_graph,
    build_candidate_research_graph,
)
from src.graphs.discovery.graph import build_discovery_graph
from src.graphs.problem.graph import build_problem_graph
from src.graphs.product.graph import build_product_graph
from src.graphs.quality.graph import build_quality_graph
from src.graphs.social.graph import build_social_discovery_graph
from src.graphs.state import DiscoveryCollector
from src.graphs.validation.graph import build_validation_graph
from src.llm.client import LLMClient


@dataclass(frozen=True)
class NodeSpec:
    name: str
    label: str
    group: str
    x: int
    y: int


@dataclass(frozen=True)
class EdgeSpec:
    source: str
    target: str
    label: str = ""
    conditional: bool = False
    loop: bool = False


@dataclass(frozen=True)
class CompiledGraphSnapshot:
    name: str
    nodes: tuple[str, ...]
    edges: tuple[tuple[str, str, str, bool], ...]


class _TopologyOnlyCollector:
    """Satisfies graph construction without providing fixture or live data."""

    is_fixture = False
    provider_name = "topology-only"

    async def search(self, *_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("topology collector must never execute")


class _TopologyOnlyLLM:
    """Satisfies graph construction and fails if a model call is attempted."""

    provider = "topology-only"

    async def generate_structured(
        self,
        *,
        task: str,
        input_data: dict,
        output_model: type[BaseModel],
        metadata: dict,
    ) -> BaseModel:
        del task, input_data, output_model, metadata
        raise RuntimeError("topology LLM must never execute")


GRAPH_ORDER = (
    "portfolio",
    "social",
    "candidate_research",
    "problem",
    "product",
    "candidate_finalization",
    "validation",
    "quality",
)


def compile_runtime_graphs() -> dict[str, Any]:
    """Build the same compiled LangGraphs used by the runtime, without executing them."""
    collector = cast(DiscoveryCollector, _TopologyOnlyCollector())
    llm = cast(LLMClient, _TopologyOnlyLLM())
    return {
        "portfolio": build_discovery_graph(collector, llm),
        "social": build_social_discovery_graph(),
        "candidate_research": build_candidate_research_graph(collector, llm),
        "problem": build_problem_graph(llm),
        "product": build_product_graph(collector, llm),
        "candidate_finalization": build_candidate_finalization_graph(collector, llm),
        "validation": build_validation_graph(llm),
        "quality": build_quality_graph(collector, llm),
    }


def snapshot_compiled_graphs(graphs: dict[str, Any] | None = None) -> tuple[CompiledGraphSnapshot, ...]:
    compiled = graphs or compile_runtime_graphs()
    snapshots: list[CompiledGraphSnapshot] = []
    for graph_name in GRAPH_ORDER:
        graph = compiled[graph_name].get_graph()
        nodes = tuple(graph.nodes)
        edges = tuple(
            (
                edge.source,
                edge.target,
                str(edge.data or ""),
                bool(edge.conditional),
            )
            for edge in graph.edges
        )
        snapshots.append(CompiledGraphSnapshot(graph_name, nodes, edges))
    return tuple(snapshots)


def build_display_topology(
    snapshots: tuple[CompiledGraphSnapshot, ...] | None = None,
) -> tuple[tuple[NodeSpec, ...], tuple[EdgeSpec, ...]]:
    """Lay out qualified nodes and edges extracted from compiled LangGraph objects."""
    source = snapshots or snapshot_compiled_graphs()
    nodes: list[NodeSpec] = []
    edges: list[EdgeSpec] = []
    y_offset = 30
    for snapshot in source:
        positions = {name: index for index, name in enumerate(snapshot.nodes)}
        levels: dict[str, int] = {}
        rows_by_level: dict[int, int] = {}
        for name in snapshot.nodes:
            predecessors = [
                edge[0]
                for edge in snapshot.edges
                if edge[1] == name and positions[edge[0]] < positions[name]
            ]
            level = max((levels[item] + 1 for item in predecessors), default=0)
            row = rows_by_level.get(level, 0)
            rows_by_level[level] = row + 1
            levels[name] = level
            nodes.append(
                NodeSpec(
                    name=_qualified(snapshot.name, name),
                    label=_display_label(name),
                    group=snapshot.name.upper(),
                    x=40 + level * 215,
                    y=y_offset + 35 + row * 72,
                )
            )
        group_rows = max(rows_by_level.values(), default=1)
        y_offset += max(150, group_rows * 72 + 100)
        for source_name, target_name, label, conditional in snapshot.edges:
            edges.append(
                EdgeSpec(
                    source=_qualified(snapshot.name, source_name),
                    target=_qualified(snapshot.name, target_name),
                    label=label,
                    conditional=conditional,
                    loop=(
                        positions[target_name] <= positions[source_name]
                        and target_name not in {"__end__"}
                    ),
                )
            )
    return tuple(nodes), tuple(edges)


def _qualified(graph_name: str, node_name: str) -> str:
    return f"{graph_name}:{node_name}"


def _display_label(name: str) -> str:
    if name == "__start__":
        return "START"
    if name == "__end__":
        return "END"
    return name.replace("_", " ")


SNAPSHOTS = snapshot_compiled_graphs()
NODES, EDGES = build_display_topology(SNAPSHOTS)
_NODES_BY_GROUP = {item.name: set(item.nodes) for item in SNAPSHOTS}


def normalize_runtime_node(raw: str, candidate_id: str | None = None) -> str:
    node = raw.rsplit(":", 1)[-1]
    if candidate_id == "portfolio" and node in _NODES_BY_GROUP["portfolio"]:
        return _qualified("portfolio", node)
    if node in _NODES_BY_GROUP["social"]:
        return _qualified("social", node)
    if node in _NODES_BY_GROUP["quality"]:
        return _qualified("quality", node)
    if node in _NODES_BY_GROUP["validation"]:
        return _qualified("validation", node)
    if node in _NODES_BY_GROUP["product"]:
        return _qualified("product", node)
    if node in _NODES_BY_GROUP["problem"]:
        return _qualified("problem", node)
    if node in _NODES_BY_GROUP["portfolio"]:
        return _qualified("portfolio", node)
    if node == "write_problem_wedge_expansion_thesis":
        return _qualified("candidate_finalization", node)
    return node
