from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.domain.models.discovery import (
    DiscoveryLane,
    DiscoveryMode,
    DiscoveryRequest,
    PublicDocument,
    SearchQuery,
    SearchResult,
)
from src.llm.client import DeterministicFakeLLM, TransientLLMError
from src.services.discovery.market import (
    select_balanced_top_candidates,
    select_distinct_top_candidates,
)
from src.services.discovery.orchestrator import PortfolioDiscoveryGraph
from src.services.discovery.query_plan import build_query_plan
from src.services.discovery.reporting import render_summary
from tests.fixture_collector import FixtureDiscoveryCollector


def test_open_and_focused_query_plans_are_distinct() -> None:
    open_queries = build_query_plan(DiscoveryRequest(mode=DiscoveryMode.OPEN))
    focused_queries = build_query_plan(
        DiscoveryRequest(mode=DiscoveryMode.FOCUSED, focus="dental clinic operations")
    )
    assert len(open_queries) == 12
    assert len(focused_queries) == 6
    assert all("dental clinic operations" in item.query for item in focused_queries)
    assert {item.lane for item in open_queries} == set(DiscoveryLane)
    assert [item.lane for item in open_queries].count(DiscoveryLane.PROBLEM_SOLVER) == 4
    assert [item.lane for item in open_queries].count(DiscoveryLane.BEHAVIOR_REDESIGN) == 5
    assert [item.lane for item in open_queries].count(DiscoveryLane.WILD_BET) == 3


def test_focused_mode_requires_focus() -> None:
    with pytest.raises(ValueError, match="focused discovery requires"):
        DiscoveryRequest(mode=DiscoveryMode.FOCUSED)


@pytest.mark.asyncio
async def test_behavior_redesign_lane_accepts_repeated_behavior_without_pain_workaround() -> None:
    class RunningRitualCollector:
        is_fixture = True
        provider_name = "behavior-redesign-fixture"

        async def search(self, queries, **kwargs):
            del kwargs
            market = any(
                query.discovery_intent.startswith("research existing alternatives")
                or query.discovery_intent.startswith("research why current alternatives")
                for query in queries
            )
            texts = (
                [
                    "기존 러닝 앱은 거리와 페이스 기록, 경로 공유 기능을 제공합니다.",
                    "공식 운동 기록 서비스는 완료한 활동과 GPS 지도를 보여줍니다.",
                ]
                if market
                else [
                    "저는 매일 같은 동네를 달리고 GPS 경로를 기록합니다.",
                    "나는 매일 산책한 경로를 사진으로 남겨 친구에게 공유한다.",
                ]
            )
            query = queries[0]
            results = []
            documents = []
            for index, text in enumerate(texts, 1):
                result = SearchResult(
                    title=f"fixture {index}",
                    url=f"https://fixture.invalid/redesign/{'market' if market else 'behavior'}/{index}",
                    description="fixture",
                    provider=self.provider_name,
                    query=query.query,
                    rank=index,
                    author_key=f"runner-{index}",
                    is_fixture=True,
                )
                results.append(result)
                documents.append(
                    PublicDocument(
                        search_result=result,
                        access_level="ORIGINAL_VERIFIED",
                        accessed_at=datetime(2026, 8, 1, tzinfo=UTC),
                        status_code=200,
                        content_type="text/html",
                        extracted_text=text,
                    )
                )
            return results, documents

    query = SearchQuery(
        query="매일 달리기 경로 기록 공유 습관 후기",
        theme="running-ritual",
        lane=DiscoveryLane.BEHAVIOR_REDESIGN,
    )
    portfolio = await PortfolioDiscoveryGraph(
        RunningRitualCollector(),  # type: ignore[arg-type]
        allow_test_fixture=True,
        query_plan=[query],
    ).run(DiscoveryRequest(mode=DiscoveryMode.OPEN))

    assert len(portfolio.candidates) == 1
    candidate = portfolio.candidates[0]
    assert candidate.cluster.lane == DiscoveryLane.BEHAVIOR_REDESIGN
    assert all(item.workaround_observed is None for item in candidate.cluster.independent_evidence)
    assert candidate.thesis.verdict == "VALIDATE_DELIGHT"
    assert candidate.thesis.visible_result
    assert any(event.node.endswith("analyze_behavior_opportunity") for event in portfolio.events)


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
    assert first.candidates[0].thesis.verdict == "VALIDATE_PROBLEM"
    assert first.candidate_quality_audits[0].execution_status == "REPORT_COMPLETE"
    assert first.candidate_quality_audits[0].candidate_verdict == first.candidates[0].thesis.verdict
    assert first.source_audit
    assert all(item.access_level == "ORIGINAL_VERIFIED" for item in first.source_audit)
    assert len(first.candidates[0].thesis.evidence) == 2
    assert all(
        item.access_level == "ORIGINAL_VERIFIED" for item in first.candidates[0].thesis.evidence
    )
    nodes = [event.node for event in first.events]
    assert nodes[:6] == [
        "plan_queries",
        "collect_behavior_sources",
        "normalize_evidence",
        "extract_social_behavior_memes",
        "inspect_social_comment_participation",
        "verify_social_accounts_and_platforms",
    ]
    assert set(nodes[6:9]) == {
        "evaluate_social_archetype_pain_removal",
        "evaluate_social_archetype_behavior_gamification",
        "evaluate_social_archetype_social_competition_collection",
    }
    assert nodes[9:14] == [
        "merge_social_archetypes_for_one_week_validation",
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
    assert nodes[-1] == "select_balanced_up_to_five_candidates"
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
async def test_generated_idea_name_comes_from_wedge_not_internal_query_theme() -> None:
    portfolio = await PortfolioDiscoveryGraph(
        FixtureDiscoveryCollector(), allow_test_fixture=True
    ).run(DiscoveryRequest(mode=DiscoveryMode.OPEN))

    assert portfolio.candidates
    assert "raw-query" not in portfolio.candidates[0].thesis.idea_name
    assert portfolio.candidates[0].thesis.wedge_statement[:24] in portfolio.candidates[0].thesis.idea_name


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
async def test_final_selection_enforces_two_two_one_lane_portfolio_without_padding() -> None:
    portfolio = await PortfolioDiscoveryGraph(
        FixtureDiscoveryCollector(), allow_test_fixture=True
    ).run(DiscoveryRequest(mode=DiscoveryMode.OPEN))
    original = portfolio.candidates[0]
    pool = []
    specifications = [
        (DiscoveryLane.PROBLEM_SOLVER, 3),
        (DiscoveryLane.BEHAVIOR_REDESIGN, 3),
        (DiscoveryLane.WILD_BET, 2),
    ]
    serial = 0
    labels = [
        "orchid",
        "volcano",
        "harbor",
        "comet",
        "lantern",
        "meadow",
        "quartz",
        "tundra",
    ]
    for lane, count in specifications:
        for _ in range(count):
            serial += 1
            label = labels[serial - 1]
            candidate = original.model_copy(deep=True)
            observations = [
                item.model_copy(
                    update={
                        "lane": lane,
                        "repeated_behavior": label,
                        "workaround": f"{label}-method",
                    }
                )
                for item in candidate.cluster.observations
            ]
            candidate.cluster = candidate.cluster.model_copy(
                update={
                    "cluster_id": f"cluster-{serial}",
                    "lane": lane,
                    "root_problem": label,
                    "observations": observations,
                }
            )
            candidate.thesis = candidate.thesis.model_copy(
                update={
                    "discovery_lane": lane,
                    "idea_name": label,
                    "root_problem": label,
                    "repeated_behavior": label,
                    "current_workaround": f"{label}-method",
                    "core_user_action": f"{label}-input → {label}-process → {label}-output",
                    "total_score": 100 - serial,
                }
            )
            pool.append(candidate)

    selected = select_balanced_top_candidates(pool, 5)
    lanes = [candidate.cluster.lane for candidate in selected]

    assert len(selected) == 5
    assert lanes.count(DiscoveryLane.PROBLEM_SOLVER) == 2
    assert lanes.count(DiscoveryLane.BEHAVIOR_REDESIGN) == 2
    assert lanes.count(DiscoveryLane.WILD_BET) == 1


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
