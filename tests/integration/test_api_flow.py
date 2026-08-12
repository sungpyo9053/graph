from __future__ import annotations

import pytest

from src.config import settings
from src.domain.models.discovery import DiscoveryMode, DiscoveryRequest
from src.services.discovery.orchestrator import PortfolioDiscoveryGraph
from src.services.discovery.reporting import write_portfolio
from tests.fixture_collector import FixtureDiscoveryCollector


@pytest.mark.asyncio
async def test_result_and_graph_are_queryable_from_api(client, tmp_path, monkeypatch) -> None:
    output = tmp_path / "output"
    monkeypatch.setenv("DISCOVERY_OUTPUT_DIR", str(output))
    settings.cache_clear()
    portfolio = await PortfolioDiscoveryGraph(
        FixtureDiscoveryCollector(), allow_test_fixture=True
    ).run(DiscoveryRequest(mode=DiscoveryMode.OPEN))
    write_portfolio(portfolio, output)

    listing = client.get("/api/v1/discoveries")
    assert listing.status_code == 200
    assert listing.json()[0]["run_id"] == portfolio.run_id
    detail = client.get(f"/api/v1/discoveries/{portfolio.run_id}")
    assert detail.status_code == 200
    assert detail.json()["data_origin"] == "TEST_FIXTURE"
    graph = client.get(f"/api/v1/runs/{portfolio.run_id}/graph")
    assert graph.status_code == 200
    assert graph.json()["timeline"][-1]["node"] == "select_balanced_up_to_five_candidates"
    report = client.get(f"/api/v1/reports/{portfolio.run_id}")
    assert report.status_code == 200
    assert len(report.json()["problem_wedge_expansion_theses"]) == 1

    settings.cache_clear()
