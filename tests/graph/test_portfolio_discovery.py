from __future__ import annotations

import pytest

from src.domain.models.discovery import DiscoveryMode, DiscoveryRequest
from src.llm.client import DeterministicFakeLLM, TransientLLMError
from src.services.discovery.market import select_distinct_top_candidates
from src.services.discovery.orchestrator import PortfolioDiscoveryGraph
from src.services.discovery.query_plan import build_query_plan
from src.services.discovery.reporting import render_summary
from tests.fixture_collector import FixtureDiscoveryCollector


def test_open_and_focused_query_plans_are_distinct() -> None:
    open_queries = build_query_plan(DiscoveryRequest(mode=DiscoveryMode.OPEN))
    focused_queries = build_query_plan(
        DiscoveryRequest(mode=DiscoveryMode.FOCUSED, focus="dental clinic operations")
    )
    assert len(open_queries) == 8
    assert len(focused_queries) == 4
    assert all("dental clinic operations" in item.query for item in focused_queries)


def test_focused_mode_requires_focus() -> None:
    with pytest.raises(ValueError, match="focused discovery requires"):
        DiscoveryRequest(mode=DiscoveryMode.FOCUSED)


def test_fixture_cannot_enter_live_graph() -> None:
    with pytest.raises(ValueError, match="test-only"):
        PortfolioDiscoveryGraph(FixtureDiscoveryCollector())


@pytest.mark.asyncio
async def test_fixture_graph_is_deterministic_does_not_pad_and_reports_scope() -> None:
    request = DiscoveryRequest(mode=DiscoveryMode.OPEN, max_candidates=5)
    first = await PortfolioDiscoveryGraph(FixtureDiscoveryCollector(), allow_test_fixture=True).run(
        request
    )
    second = await PortfolioDiscoveryGraph(
        FixtureDiscoveryCollector(), allow_test_fixture=True
    ).run(request)

    assert first.data_origin == "TEST_FIXTURE"
    assert len(first.candidates) == 1
    assert [item.thesis.model_dump(exclude={"is_fixture"}) for item in first.candidates] == [
        item.thesis.model_dump(exclude={"is_fixture"}) for item in second.candidates
    ]
    assert first.candidates[0].thesis.is_fixture is True
    assert first.candidates[0].thesis.verdict in {"RESEARCH", "INTERVIEW", "VALIDATE"}
    assert first.candidate_quality_audits[0].execution_status == "REPORT_COMPLETE"
    assert first.candidate_quality_audits[0].candidate_verdict == first.candidates[0].thesis.verdict
    assert first.source_audit
    assert all(item.access_level == "ORIGINAL_VERIFIED" for item in first.source_audit)
    assert len(first.candidates[0].thesis.evidence) == 2
    assert all(
        item.access_level == "ORIGINAL_VERIFIED" for item in first.candidates[0].thesis.evidence
    )
    nodes = [event.node for event in first.events]
    assert nodes[:7] == [
        "plan_queries",
        "collect_behavior_sources",
        "normalize_evidence",
        "detect_workarounds",
        "deduplicate_root_problems",
        "review_problem_evidence",
        "orchestrate_candidate_subgraphs",
    ]
    for suffix in (
        "extract_pain",
        "identify_persona",
        "analyze_root_problem",
        "analyze_existing_alternatives",
        "analyze_structural_gap",
        "design_wedge_candidates",
        "evaluate_problem_strength",
        "evaluate_switching_feasibility",
            "evaluate_asset_accumulation",
            "evaluate_expansion_potential",
            "product_quality_gate",
            "design_validation",
            "validation_contract_gate",
        "write_problem_wedge_expansion_thesis",
    ):
        assert any(node.endswith(suffix) for node in nodes)
    assert nodes[-1] == "select_up_to_five_distinct_root_problems"
    assert first.candidates[0].thesis.scores["asset"].unknown is True
    assert first.candidates[0].thesis.scores["expansion"].value == 0
    summary = render_summary(first)
    for label in (
        "실행 모드",
        "탐색 주제와 문제 영역",
        "생성한 검색 쿼리",
        "조사 기간",
        "검색 결과 수",
        "실제 접근·검증한 원문 수",
        "제외된 자료 수",
        "최종 후보 수",
        "조사 한계",
        "검색 결과 요약만 확인한 자료 수",
    ):
        assert label in summary
    assert "전체 시장의 절대 순위가 아니다" in summary


@pytest.mark.asyncio
async def test_insufficient_original_evidence_returns_zero_candidates() -> None:
    class OneOriginalCollector(FixtureDiscoveryCollector):
        async def search(self, *args, **kwargs):
            results, documents = await super().search(*args, **kwargs)
            return results[:1], documents[:1]

    portfolio = await PortfolioDiscoveryGraph(OneOriginalCollector(), allow_test_fixture=True).run(
        DiscoveryRequest(mode=DiscoveryMode.OPEN)
    )
    assert portfolio.candidates == []
    assert portfolio.exclusion_reasons["cluster_below_two_independent_A_to_C_originals"] == 1


@pytest.mark.asyncio
async def test_orchestrator_calls_qualitative_llm_nodes_and_keeps_numeric_gates_in_code() -> None:
    llm = DeterministicFakeLLM()
    graph = PortfolioDiscoveryGraph(
        FixtureDiscoveryCollector(), allow_test_fixture=True, llm=llm
    )
    node_names = set(graph.compiled.get_graph().nodes)
    assert {
        "plan_queries",
        "collect_behavior_sources",
        "review_problem_evidence",
        "orchestrate_candidate_subgraphs",
        "select_distinct_candidates",
        "save_result",
    } <= node_names

    portfolio = await graph.run(DiscoveryRequest(mode=DiscoveryMode.OPEN))
    assert {call["task"] for call in llm.calls} == {
        "analyze_root_problem",
        "identify_persona",
        "analyze_structural_gap",
        "design_wedge_candidates",
        "analyze_asset_expansion",
            "cold_critique",
            "exit_challenger",
        }
    thesis = portfolio.candidates[0].thesis
    assert thesis.scores["problem_strength"].rationale.startswith(
        "verified independent A-C original sources"
    )
    assert thesis.scores["asset"].value == 0
    assert thesis.scores["asset"].unknown is True
    assert portfolio.llm_provider == "fake"


@pytest.mark.asyncio
async def test_configured_codex_provider_is_reported_even_when_gate_prevents_all_calls() -> None:
    class EmptyFixtureCollector:
        is_fixture = True
        provider_name = "empty-test-fixture"

        async def search(self, *args, **kwargs):
            return [], []

    class NoCallCodexStub:
        provider = "codex"
        model = "codex-test-stub"
        calls: list[dict] = []

        async def generate_structured(self, **kwargs):
            raise AssertionError("evidence gate should prevent every LLM call")

    portfolio = await PortfolioDiscoveryGraph(
        EmptyFixtureCollector(),  # type: ignore[arg-type]
        allow_test_fixture=True,
        llm=NoCallCodexStub(),  # type: ignore[arg-type]
    ).run(DiscoveryRequest(mode=DiscoveryMode.OPEN))

    assert portfolio.candidates == []
    assert portfolio.llm_provider == "codex"
    assert portfolio.llm_call_audit == []


@pytest.mark.asyncio
async def test_final_selection_blocks_same_behavior_and_solution_archetype() -> None:
    portfolio = await PortfolioDiscoveryGraph(
        FixtureDiscoveryCollector(), allow_test_fixture=True
    ).run(DiscoveryRequest(mode=DiscoveryMode.OPEN))
    original = portfolio.candidates[0]
    renamed = original.model_copy(deep=True)
    renamed.cluster = renamed.cluster.model_copy(
        update={
            "cluster_id": "renamed-cluster",
            "root_problem": "different words pretending to describe a new market",
        }
    )
    renamed.thesis = renamed.thesis.model_copy(update={"idea_name": "renamed product"})
    assert len(select_distinct_top_candidates([original, renamed], 5)) == 1


@pytest.mark.asyncio
async def test_one_candidate_llm_failure_is_held_and_portfolio_is_still_saved() -> None:
    class FailingWedgeLLM(DeterministicFakeLLM):
        async def generate_structured(self, **kwargs):
            if kwargs["task"] == "design_wedge_candidates":
                raise TransientLLMError("bounded timeout")
            return await super().generate_structured(**kwargs)

    portfolio = await PortfolioDiscoveryGraph(
        FixtureDiscoveryCollector(),
        allow_test_fixture=True,
        llm=FailingWedgeLLM(),
    ).run(DiscoveryRequest(mode=DiscoveryMode.OPEN))
    assert portfolio.candidates == []
    audit = portfolio.candidate_quality_audits[0]
    assert audit.execution_status == "HELD"
    assert audit.candidate_verdict == "HOLD"
    assert audit.error_type == "TransientLLMError"
    assert any(event.status == "FAILED" for event in portfolio.events)
