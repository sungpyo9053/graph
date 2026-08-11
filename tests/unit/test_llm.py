import asyncio
from pathlib import Path

import pytest
from pydantic import BaseModel

from src.config import settings
from src.llm.client import (
    CodexLLMClient,
    DeterministicFakeLLM,
    SchemaLLMError,
    create_fresh_llm_client,
    create_llm_client,
    generate_with_schema_retry,
    strict_json_schema,
)


class Output(BaseModel):
    value: int


class FlakyClient:
    def __init__(self, succeed_on: int):
        self.calls = 0
        self.succeed_on = succeed_on

    async def generate_structured(self, **kwargs):
        self.calls += 1
        if self.calls < self.succeed_on:
            Output.model_validate({"value": "invalid"})
        return Output(value=7)


@pytest.mark.asyncio
async def test_schema_error_is_retried_once() -> None:
    client = FlakyClient(2)
    result = await generate_with_schema_retry(
        client, task="x", input_data={}, output_model=Output, metadata={}, max_schema_retries=1
    )
    assert result.value == 7
    assert client.calls == 2


@pytest.mark.asyncio
async def test_schema_error_stops_after_limit() -> None:
    with pytest.raises(SchemaLLMError):
        await generate_with_schema_retry(
            FlakyClient(99),
            task="x",
            input_data={},
            output_model=Output,
            metadata={},
            max_schema_retries=1,
        )


def test_codex_provider_never_constructs_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "codex")
    monkeypatch.setattr("src.llm.client.which", lambda command: f"/usr/bin/{command}")
    settings.cache_clear()
    try:
        client = create_llm_client()
        assert isinstance(client, CodexLLMClient)
        assert not isinstance(client, DeterministicFakeLLM)
        fresh = create_fresh_llm_client(client)
        assert isinstance(fresh, CodexLLMClient)
        assert fresh._semaphore is client._semaphore
    finally:
        settings.cache_clear()


def test_codex_schema_is_strict_for_nested_objects() -> None:
    class Nested(BaseModel):
        label: str

    class Container(BaseModel):
        nested: Nested
        optional: str = "unknown"

    schema = strict_json_schema(Container.model_json_schema())
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"nested", "optional"}
    assert schema["$defs"]["Nested"]["additionalProperties"] is False


@pytest.mark.asyncio
async def test_cold_and_exit_use_distinct_ephemeral_exec_without_resume(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "codex")
    monkeypatch.setattr("src.llm.client.which", lambda command: f"/usr/bin/{command}")
    settings.cache_clear()
    commands: list[tuple[str, ...]] = []

    class Process:
        def __init__(self, args: tuple[str, ...]):
            self.args = args
            self.returncode = 0

        async def communicate(self):
            if self.args[1:3] == ("login", "status"):
                return b"Logged in using ChatGPT", b""
            if self.args[1:] == ("--version",):
                return b"codex-cli test", b""
            output_index = self.args.index("--output-last-message") + 1
            await asyncio.to_thread(
                Path(self.args[output_index]).write_text,
                '{"value": 7}',
                encoding="utf-8",
            )
            return b"", b"model: test-gpt\n"

        def kill(self) -> None:
            self.returncode = -9

    async def create_process(*args, **kwargs):
        del kwargs
        command = tuple(str(item) for item in args)
        commands.append(command)
        return Process(command)

    monkeypatch.setattr(
        "src.llm.client.asyncio.create_subprocess_exec", create_process
    )
    try:
        base = CodexLLMClient()
        cold = create_fresh_llm_client(base)
        challenger = create_fresh_llm_client(base)
        await cold.generate_structured(
            task="cold_critique",
            input_data={"candidate": "current only"},
            output_model=Output,
            metadata={"prior_critique_included": False},
        )
        await challenger.generate_structured(
            task="exit_challenger",
            input_data={"candidate": "current only"},
            output_model=Output,
            metadata={"prior_critique_included": False},
        )
        exec_commands = [item for item in commands if len(item) > 1 and item[1] == "exec"]
        assert len(exec_commands) == 2
        assert all("--ephemeral" in item for item in exec_commands)
        assert all("resume" not in item for item in exec_commands)
        assert all(not any("session" in part.lower() for part in item) for item in exec_commands)
        output_paths = [
            item[item.index("--output-last-message") + 1] for item in exec_commands
        ]
        assert output_paths[0] != output_paths[1]
        assert cold.calls[0]["invocation_id"] != challenger.calls[0]["invocation_id"]
        assert "previous finding" not in exec_commands[1][-1]
        heartbeat = capsys.readouterr().err
        assert "node=cold_critique" in heartbeat
        assert "node=exit_challenger" in heartbeat
        assert "status=STARTED" in heartbeat
        assert "status=COMPLETED" in heartbeat
        assert "candidate=current only" not in heartbeat
        assert '{"value": 7}' not in heartbeat
    finally:
        settings.cache_clear()
