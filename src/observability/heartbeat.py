from __future__ import annotations

from contextvars import ContextVar, Token

_run_id: ContextVar[str] = ContextVar("discovery_run_id", default="unknown")
_candidate_id: ContextVar[str] = ContextVar("discovery_candidate_id", default="unknown")


def set_invocation_context(run_id: str, candidate_id: str) -> tuple[Token[str], Token[str]]:
    return _run_id.set(run_id), _candidate_id.set(candidate_id)


def reset_invocation_context(tokens: tuple[Token[str], Token[str]]) -> None:
    run_token, candidate_token = tokens
    _run_id.reset(run_token)
    _candidate_id.reset(candidate_token)


def invocation_context() -> tuple[str, str]:
    return _run_id.get(), _candidate_id.get()
