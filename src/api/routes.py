from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from src.config import settings
from src.domain.models.discovery import DiscoveryPortfolio

api = APIRouter(prefix="/api/v1")
ui = APIRouter()
templates = Jinja2Templates(directory="src/ui/templates")


def _output_root() -> Path:
    return Path(settings().discovery_output_dir)


def _load_portfolio(run_id: str) -> DiscoveryPortfolio:
    if not run_id or any(character not in "0123456789abcdef-" for character in run_id.lower()):
        raise HTTPException(404, "discovery run not found")
    path = _output_root() / run_id / "portfolio.json"
    try:
        return DiscoveryPortfolio.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise HTTPException(404, "discovery run not found") from exc


def _list_portfolios() -> list[DiscoveryPortfolio]:
    root = _output_root()
    if not root.exists():
        return []
    portfolios: list[DiscoveryPortfolio] = []
    for path in root.glob("*/portfolio.json"):
        try:
            portfolios.append(
                DiscoveryPortfolio.model_validate_json(path.read_text(encoding="utf-8"))
            )
        except (OSError, ValidationError):
            continue
    return sorted(portfolios, key=lambda item: item.completed_at, reverse=True)


@api.get("/discoveries")
def list_discoveries() -> list[dict]:
    return [item.model_dump(mode="json") for item in _list_portfolios()]


@api.get("/discoveries/{run_id}")
def get_discovery(run_id: str) -> dict:
    return _load_portfolio(run_id).model_dump(mode="json")


@api.get("/runs/{run_id}/graph")
def get_graph(run_id: str) -> dict:
    portfolio = _load_portfolio(run_id)
    return {
        "run_id": portfolio.run_id,
        "mode": portfolio.mode,
        "provider": portfolio.provider,
        "data_origin": portfolio.data_origin,
        "timeline": [item.model_dump(mode="json") for item in portfolio.events],
    }


@api.get("/reports/{run_id}")
def get_report(run_id: str) -> dict:
    portfolio = _load_portfolio(run_id)
    return {
        "scope": {
            "mode": portfolio.mode,
            "focus": portfolio.focus,
            "queries": portfolio.search_queries,
            "exploration_areas": portfolio.exploration_areas,
            "period": [
                portfolio.investigation_period_start,
                portfolio.investigation_period_end,
            ],
            "provider": portfolio.provider,
            "verified_originals": portfolio.original_pages_verified,
            "snippet_only": portfolio.snippet_only_count,
            "limitations": portfolio.warnings,
        },
        "problem_wedge_expansion_theses": [
            item.thesis.model_dump(mode="json") for item in portfolio.candidates
        ],
    }


@api.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "purpose": "graph-based evidence discovery, not app generation",
        "live_provider": settings().search_provider,
        "fixture_policy": "test-only",
    }


@ui.get("/", response_class=HTMLResponse)
def board(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "board.html", {"runs": _list_portfolios()})


@ui.get("/discoveries/{run_id}", response_class=HTMLResponse)
def discovery_page(request: Request, run_id: str) -> HTMLResponse:
    portfolio = _load_portfolio(run_id)
    return templates.TemplateResponse(
        request,
        "detail.html",
        {
            "portfolio": portfolio,
            "raw_json": json.dumps(portfolio.model_dump(mode="json"), ensure_ascii=False, indent=2),
        },
    )


@ui.get("/runs/{run_id}/view", response_class=HTMLResponse)
def graph_page(request: Request, run_id: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "graph.html",
        {"portfolio": _load_portfolio(run_id)},
    )
