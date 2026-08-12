from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel

from src.collectors.public_web import PublicPageFetcher
from src.collectors.verified_urls import VerifiedUrlCollector
from src.config import Settings
from src.domain.models.discovery import DiscoveryMode, DiscoveryRequest
from src.domain.models.url_input import VerifiedUrlInput
from src.services.discovery.orchestrator import PortfolioDiscoveryGraph
from src.services.discovery.reporting import write_portfolio


class DiscoveryJob(BaseModel):
    job_id: str
    status: Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED"]
    source: Literal["verified_urls"] = "verified_urls"
    llm_provider: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result_run_id: str | None = None
    result_url: str | None = None
    error: str | None = None


class DiscoveryJobManager:
    """Run one operator-triggered discovery at a time inside the API process."""

    def __init__(self) -> None:
        self._jobs: dict[str, DiscoveryJob] = {}
        self._tasks: set[asyncio.Task[None]] = set()

    def start_verified_urls(self, input_path: Path, config: Settings) -> DiscoveryJob:
        provider = config.llm_provider.lower()
        if provider == "fake":
            raise ValueError(
                "UI discovery refuses fake LLM; start the server with LLM_PROVIDER=codex"
            )
        if provider not in {"codex", "openai"}:
            raise ValueError(f"unsupported LLM_PROVIDER={config.llm_provider}")
        if not input_path.is_file():
            raise ValueError("verified URL input is unavailable")

        active = next(
            (job for job in self._jobs.values() if job.status in {"QUEUED", "RUNNING"}),
            None,
        )
        if active is not None:
            return active.model_copy(deep=True)

        job = DiscoveryJob(
            job_id=str(uuid4()),
            status="QUEUED",
            llm_provider=provider,
            created_at=datetime.now(UTC),
        )
        self._jobs[job.job_id] = job
        task = asyncio.create_task(self._run_verified_urls(job.job_id, input_path, config))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job.model_copy(deep=True)

    def get(self, job_id: str) -> DiscoveryJob | None:
        job = self._jobs.get(job_id)
        return job.model_copy(deep=True) if job is not None else None

    async def _run_verified_urls(
        self,
        job_id: str,
        input_path: Path,
        config: Settings,
    ) -> None:
        job = self._jobs[job_id]
        job.status = "RUNNING"
        job.started_at = datetime.now(UTC)
        try:
            source = VerifiedUrlInput.model_validate_json(
                await asyncio.to_thread(input_path.read_text, encoding="utf-8")
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
            collector = VerifiedUrlCollector(source, PublicPageFetcher())
            portfolio = await PortfolioDiscoveryGraph(
                collector,
                query_plan=source.query_plan(),
            ).run(request)
            write_portfolio(portfolio, Path(config.discovery_output_dir))
            job.result_run_id = portfolio.run_id
            job.result_url = f"/discoveries/{portfolio.run_id}"
            job.status = "COMPLETED"
        except Exception as exc:  # noqa: BLE001 - persist background failure state
            job.status = "FAILED"
            job.error = _safe_error(exc)
        finally:
            job.completed_at = datetime.now(UTC)


def _safe_error(exc: Exception) -> str:
    message = " ".join(str(exc).split())[:240]
    return f"{type(exc).__name__}: {message}" if message else type(exc).__name__


discovery_job_manager = DiscoveryJobManager()
