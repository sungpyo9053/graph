from __future__ import annotations

import asyncio

import pytest

from src.config import Settings
from src.services.discovery.jobs import DiscoveryJobManager


def test_ui_job_refuses_fake_llm(tmp_path) -> None:
    input_path = tmp_path / "verified-urls.json"
    input_path.write_text("{}", encoding="utf-8")
    manager = DiscoveryJobManager()

    with pytest.raises(ValueError, match="refuses fake LLM"):
        manager.start_verified_urls(input_path, Settings(llm_provider="fake"))


@pytest.mark.asyncio
async def test_ui_job_reuses_the_single_active_run(tmp_path, monkeypatch) -> None:
    input_path = tmp_path / "verified-urls.json"
    input_path.write_text("{}", encoding="utf-8")
    manager = DiscoveryJobManager()
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_run(job_id, source_path, config) -> None:
        del source_path, config
        manager._jobs[job_id].status = "RUNNING"
        started.set()
        await release.wait()

    monkeypatch.setattr(manager, "_run_verified_urls", slow_run)
    config = Settings(llm_provider="codex")

    first = manager.start_verified_urls(input_path, config)
    await started.wait()
    second = manager.start_verified_urls(input_path, config)
    release.set()
    await asyncio.sleep(0)

    assert first.job_id == second.job_id
    assert second.status == "RUNNING"
