from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Limits(BaseModel):
    max_evidence_retries: int
    max_root_problem_retries: int
    max_structure_retries: int
    max_wedge_retries: int
    max_validation_retries: int
    max_total_nodes: int
    max_total_model_calls: int
    max_estimated_cost_usd: float
    max_elapsed_minutes: int


class Gate(BaseModel):
    required_fields: list[str]


class ProblemGate(Gate):
    minimum_independent_sources: int
    minimum_problem_evidence_points: int


class ThesisGate(Gate):
    minimum_total_score: int
    blocked_risk_levels: list[str]


class ValidationGate(Gate):
    maximum_duration_days: int


class QualityGates(BaseModel):
    problem_gate: ProblemGate
    thesis_gate: ThesisGate
    validation_gate: ValidationGate


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./idea_graph.db"
    llm_provider: str = "fake"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-5-mini"
    codex_command: str = "codex"
    codex_model: str | None = None
    codex_timeout_seconds: int = 180
    codex_max_concurrency: int = Field(default=1, ge=1, le=2)
    codex_heartbeat_seconds: int = Field(default=15, ge=1, le=60)
    search_provider: str = "brave"
    brave_search_api_key: SecretStr | None = None
    discovery_country: str = "US"
    discovery_search_lang: str = "en"
    discovery_lookback_days: int = 730
    discovery_results_per_query: int = 10
    discovery_max_original_pages: int = 80
    discovery_output_dir: str = "output"
    log_level: str = "INFO"


@lru_cache
def settings() -> Settings:
    return Settings()


@lru_cache
def limits() -> Limits:
    return Limits.model_validate(
        yaml.safe_load((ROOT / "config/graph-limits.yaml").read_text())["limits"]
    )


@lru_cache
def gates() -> QualityGates:
    return QualityGates.model_validate(
        yaml.safe_load((ROOT / "config/quality-gates.yaml").read_text())
    )
