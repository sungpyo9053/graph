from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar, Token
from typing import Any

_run_id: ContextVar[str] = ContextVar("discovery_run_id", default="unknown")
_candidate_id: ContextVar[str] = ContextVar("discovery_candidate_id", default="unknown")
_runtime_observer: ContextVar[Callable[[dict[str, Any]], None] | None] = ContextVar(
    "discovery_runtime_observer", default=None
)


def set_invocation_context(run_id: str, candidate_id: str) -> tuple[Token[str], Token[str]]:
    return _run_id.set(run_id), _candidate_id.set(candidate_id)


def reset_invocation_context(tokens: tuple[Token[str], Token[str]]) -> None:
    run_token, candidate_token = tokens
    _run_id.reset(run_token)
    _candidate_id.reset(candidate_token)


def invocation_context() -> tuple[str, str]:
    return _run_id.get(), _candidate_id.get()


def set_runtime_observer(
    observer: Callable[[dict[str, Any]], None],
) -> Token[Callable[[dict[str, Any]], None] | None]:
    return _runtime_observer.set(observer)


def reset_runtime_observer(token: Token[Callable[[dict[str, Any]], None] | None]) -> None:
    _runtime_observer.reset(token)


def emit_runtime_event(event: dict[str, Any]) -> None:
    observer = _runtime_observer.get()
    if observer is not None:
        observer(event)
