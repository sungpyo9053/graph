from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.api import routes
from src.config import settings
from src.domain.models.discovery import DiscoveryMode, DiscoveryRequest
from src.services.discovery.jobs import DiscoveryJob
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


def test_board_exposes_operator_triggered_discovery_button(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert 'id="discoverButton"' in response.text
    assert "아이디어 찾기" in response.text


def test_discovery_job_start_and_poll_api(client, monkeypatch) -> None:
    job = DiscoveryJob(
        job_id="11111111-1111-1111-1111-111111111111",
        status="RUNNING",
        llm_provider="codex",
        created_at=datetime(2026, 8, 12, tzinfo=UTC),
        started_at=datetime(2026, 8, 12, tzinfo=UTC),
    )

    class StubJobManager:
        def start_verified_urls(self, input_path, config):
            assert input_path.name == "verified-urls.json"
            del config
            return job

        def get(self, job_id):
            return job if job_id == job.job_id else None

    monkeypatch.setattr(routes, "discovery_job_manager", StubJobManager())

    started = client.post("/api/v1/discovery-jobs")
    assert started.status_code == 202
    assert started.json()["status"] == "RUNNING"
    polled = client.get(f"/api/v1/discovery-jobs/{job.job_id}")
    assert polled.status_code == 200
    assert polled.json()["llm_provider"] == "codex"
    assert client.get("/api/v1/discovery-jobs/missing").status_code == 404
