from __future__ import annotations

import asyncio
import json
import re
import sys
import tempfile
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from shutil import which
from time import perf_counter
from typing import Protocol, TypeVar
from uuid import uuid4

from openai import APIConnectionError, APIStatusError, AsyncOpenAI
from pydantic import BaseModel, ValidationError

from src.config import settings
from src.observability.heartbeat import invocation_context

ModelT = TypeVar("ModelT", bound=BaseModel)


def strict_json_schema(schema: dict) -> dict:
    """Convert Pydantic JSON Schema to the strict object form Codex requires."""
    output = dict(schema)
    if output.get("type") == "object" or "properties" in output:
        properties = output.get("properties", {})
        output["additionalProperties"] = False
        output["required"] = list(properties)
        output["properties"] = {
            key: strict_json_schema(value) for key, value in properties.items()
        }
    for key in ("$defs", "definitions"):
        if key in output:
            output[key] = {
                name: strict_json_schema(value) for name, value in output[key].items()
            }
    for key in ("items", "additionalItems"):
        if isinstance(output.get(key), dict):
            output[key] = strict_json_schema(output[key])
    for key in ("anyOf", "oneOf", "allOf"):
        if key in output:
            output[key] = [strict_json_schema(value) for value in output[key]]
    return output


class LLMError(RuntimeError):
    pass


class TransientLLMError(LLMError):
    pass


class PermanentLLMError(LLMError):
    pass


class SchemaLLMError(LLMError):
    pass


class LLMClient(Protocol):
    provider: str

    async def generate_structured(
        self,
        *,
        task: str,
        input_data: dict,
        output_model: type[ModelT],
        metadata: dict,
    ) -> ModelT: ...


class DeterministicFakeLLM:
    provider = "fake"
    model = "deterministic-fake-v1"

    def __init__(self, responses: dict[str, dict] | None = None):
        self.responses = responses or {}
        self.calls: list[dict] = []

    async def generate_structured(
        self,
        *,
        task: str,
        input_data: dict,
        output_model: type[ModelT],
        metadata: dict,
    ) -> ModelT:
        self.calls.append({"task": task, "input_data": input_data, "metadata": metadata})
        response = self.responses.get(task) or self._default_response(task, input_data)
        return output_model.model_validate(response)

    @staticmethod
    def _default_response(task: str, data: dict) -> dict:
        """Deterministic qualitative judgments for offline graph execution."""
        common = {
            "observed_facts": [
                "quoted repeated behavior is present; workaround requirements depend on the discovery lane"
            ],
            "inferences": [],
            "assumptions": [],
            "unknowns": ["real-world switching and payment behavior"],
            "decision": "CONTINUE",
            "decision_reason": "offline deterministic test path",
        }
        if task == "identify_persona":
            return {
                **common,
                "persona": "person performing the repeated behavior in the quoted originals",
                "situation": "when the quoted repeated task occurs",
                "source_support": "only the quoted originals; identity details remain unknown",
                "confidence": 0.3,
            }
        if task == "analyze_root_problem":
            return {
                **common,
                "root_problem": "the required state and proof remain fragmented, so the observed person repeatedly reconstructs them",
                "rationale": "This is inferred only after clustering quoted repeated behavior; it is not supplied by the input.",
                "confidence": 0.35,
            }
        if task == "analyze_behavior_reframe":
            return {
                **common,
                "behavior_opportunity": "the existing repeated behavior can produce a visible collectible result without requiring pain removal",
                "current_meaning": "the behavior is currently recorded mainly as completion or numeric progress",
                "reframe_axes": ["COLLECTION", "PROGRESSION", "SHARING"],
                "rationale": "The opportunity is inferred from repeated behavior only; delight and sharing remain unvalidated.",
                "confidence": 0.3,
            }
        if task == "analyze_structural_gap":
            count = len(data.get("alternatives", []))
            return {
                **common,
                "structural_gap": data["structural_gap"],
                "why_unsolved": data["why_unsolved"],
                "causal_gap_verified": False,
                "rationale": f"{count} alternatives are observed, but their causal failure mechanism is not directly verified.",
                "confidence": 0.35 if count else 0.0,
            }
        if task in {"design_wedge_candidates", "simplify_wedge_candidate"}:
            persona = data["persona"]
            simplifying = task == "simplify_wedge_candidate"
            return {
                **common,
                "candidates": [{
                    "name": "single-input manual result" if simplifying else "single-case evidence result",
                    "approach_type": "single_case_decision",
                    "target_user": persona,
                    "buyer": "unknown",
                    "user_input": "one current case plus user-provided source material",
                    "core_process": "normalize the supplied evidence and mark unresolved facts",
                    "expected_output": "one sourced next-action result for the current case",
                    "switching_reason": "remove one reconstruction step from the observed workaround",
                    "switching_cost": "supply one case and verify uncertain fields",
                    "time_to_first_value": "first manually produced result",
                    "solo_first_user_value": True,
                    "acquisition_channel": "communities represented by verified original sources",
                    "monetization_hypothesis": "unknown until payment behavior is observed",
                    "required_data": "user-provided case and lawfully accessible evidence",
                    "data_access_feasible": True,
                    "problem_relevance": True,
                    "manual_validation_feasible": True,
                    "behavior_displacement": "REMOVES_STEP",
                    "expected_steps_removed": 1,
                    "external_form_reentry_required": False,
                    "instant_visible_result": True,
                    "repeat_trigger": "the next completed behavior visibly changes the result",
                    "social_loop": "the result can be compared or shared without requiring another user",
                    "ten_second_demo": True,
                    "network_amplification": True,
                    "validation_cost_usd": 100,
                    "complexity": "LOW"
                }],
                "rationale": "The candidate is constrained to one input, one process, and one decision-relevant output.",
            }
        if task == "analyze_asset_expansion":
            return {
                **common,
                "asset": "completed case, cited source, exception, and outcome history",
                "accumulation_mechanism": "completed cases may record source, exception, and outcome",
                "controlled_by_product": False,
                "reusable_in_later_cases": False,
                "expansion_problem": "unknown adjacent problem requiring the same verified case history",
                "causal_link": "not verified by the current source set",
                "asset_source_support": "HYPOTHESIS",
                "expansion_source_support": "UNSUPPORTED",
                "rationale": "Behavior is proven, but asset control, reuse, and expansion are not.",
            }
        if task == "cold_critique":
            return {
                **common,
                "decision": "NO_BLOCKING_FINDING",
                "decision_reason": "deterministic test response",
                "findings": [],
            }
        if task == "exit_challenger":
            return {
                **common,
                "decision": "NO_NEW_BLOCKING_FINDING",
                "decision_reason": "deterministic test response",
                "blocking_finding": None,
            }
        raise PermanentLLMError(f"No deterministic fixture for task={task}")


class OpenAICompatibleLLM:
    provider = "openai"

    def __init__(self) -> None:
        cfg = settings()
        if not cfg.openai_api_key:
            raise PermanentLLMError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        self.model = cfg.openai_model
        self.client = AsyncOpenAI(api_key=cfg.openai_api_key, base_url=cfg.openai_base_url)

    async def generate_structured(
        self,
        *,
        task: str,
        input_data: dict,
        output_model: type[ModelT],
        metadata: dict,
    ) -> ModelT:
        try:
            response = await self.client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": "Return valid JSON only. Never modify quoted source evidence.",
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {"task": task, "input": input_data, "metadata": metadata},
                            ensure_ascii=False,
                        ),
                    },
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": output_model.__name__,
                        "schema": output_model.model_json_schema(),
                        "strict": True,
                    }
                },
            )
            return output_model.model_validate_json(response.output_text)
        except APIConnectionError as exc:
            raise TransientLLMError(str(exc)) from exc
        except APIStatusError as exc:
            if exc.status_code >= 500 or exc.status_code == 429:
                raise TransientLLMError(str(exc)) from exc
            raise PermanentLLMError(str(exc)) from exc
        except ValidationError as exc:
            raise SchemaLLMError(str(exc)) from exc


class CodexLLMClient:
    """Structured GPT calls through an already authenticated local Codex CLI."""

    provider = "codex"

    def __init__(self, *, semaphore: asyncio.Semaphore | None = None) -> None:
        cfg = settings()
        if which(cfg.codex_command) is None:
            raise PermanentLLMError(f"Codex CLI not found: {cfg.codex_command}")
        self.command = cfg.codex_command
        self.model = cfg.codex_model or "codex-cli-default-gpt"
        self.timeout_seconds = cfg.codex_timeout_seconds
        self.heartbeat_seconds = cfg.codex_heartbeat_seconds
        self.calls: list[dict] = []
        self._semaphore = semaphore or asyncio.Semaphore(cfg.codex_max_concurrency)
        self._preflight_lock = asyncio.Lock()
        self._preflight_done = False

    async def _ensure_preflight(self) -> None:
        if self._preflight_done:
            return
        async with self._preflight_lock:
            if self._preflight_done:
                return
            checks = ((["login", "status"], "Logged in"), (["--version"], "codex-cli"))
            for arguments, expected in checks:
                process = await asyncio.create_subprocess_exec(
                    self.command,
                    *arguments,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await process.communicate()
                message = (stdout + stderr).decode(errors="replace")
                if process.returncode != 0 or expected not in message:
                    raise PermanentLLMError(
                        f"Codex CLI preflight failed for {' '.join(arguments)}: "
                        f"exit={process.returncode} output={message[-1000:]}"
                    )
            self._preflight_done = True

    async def generate_structured(
        self,
        *,
        task: str,
        input_data: dict,
        output_model: type[ModelT],
        metadata: dict,
    ) -> ModelT:
        await self._ensure_preflight()
        async with self._semaphore:
            return await self._generate_once(
                task=task,
                input_data=input_data,
                output_model=output_model,
                metadata=metadata,
            )

    async def _generate_once(
        self,
        *,
        task: str,
        input_data: dict,
        output_model: type[ModelT],
        metadata: dict,
    ) -> ModelT:
        prompt = json.dumps(
            {
                "instruction": (
                    "Return only the JSON object required by the output schema. Use only the "
                    "quoted evidence and structured fields below. Do not inspect files, call "
                    "tools, search the web, invent facts or numbers, or treat inference as fact. "
                    "Separate observed_facts, inferences, assumptions, unknowns, decision, and "
                    "decision_reason. Mark unsupported claims unknown."
                ),
                "task": task,
                "input": input_data,
                "metadata": metadata,
            },
            ensure_ascii=False,
        )
        started_at = datetime.now(UTC)
        clock = perf_counter()
        exit_code = -1
        schema_result = "NOT_VALIDATED"
        model_used = self.model
        invocation_id = str(uuid4())
        run_id, candidate_id = invocation_context()
        self._emit_heartbeat(
            run_id, candidate_id, task, invocation_id, "STARTED", 0
        )
        heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(
                run_id, candidate_id, task, invocation_id, clock
            )
        )
        try:
            with tempfile.TemporaryDirectory(prefix="idea-codex-llm-") as temp_dir:
                directory = Path(temp_dir)
                schema_path = directory / "schema.json"
                output_path = directory / "output.json"
                schema_path.write_text(
                    json.dumps(
                        strict_json_schema(output_model.model_json_schema()),
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                command = [
                    self.command,
                    "exec",
                    "--ephemeral",
                    "--skip-git-repo-check",
                    "--ignore-rules",
                    "--sandbox",
                    "read-only",
                    "--color",
                    "never",
                    "--output-schema",
                    str(schema_path),
                    "--output-last-message",
                    str(output_path),
                    "-C",
                    temp_dir,
                ]
                cfg = settings()
                if cfg.codex_model:
                    command.extend(["--model", cfg.codex_model])
                command.append(prompt)
                process: asyncio.subprocess.Process | None = None
                try:
                    process = await asyncio.create_subprocess_exec(
                        *command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(), timeout=self.timeout_seconds
                    )
                    exit_code = process.returncode or 0
                    model_match = re.search(
                        r"(?m)^model:\s*(\S.+?)\s*$", stderr.decode(errors="replace")
                    )
                    if model_match:
                        model_used = model_match.group(1).strip()
                except TimeoutError as exc:
                    if process is not None:
                        process.kill()
                        await process.communicate()
                    raise TransientLLMError("Codex CLI structured call timed out") from exc
                except OSError as exc:
                    raise TransientLLMError(f"Codex CLI launch failed: {exc}") from exc
                if process.returncode != 0:
                    message = (stderr or stdout).decode(errors="replace")[-2000:]
                    if "invalid_json_schema" in message:
                        schema_result = "INVALID_SCHEMA_DECLARATION"
                        raise SchemaLLMError(f"Codex CLI rejected output schema: {message}")
                    error = (
                        PermanentLLMError
                        if process.returncode in {2, 64}
                        else TransientLLMError
                    )
                    raise error(f"Codex CLI failed ({process.returncode}): {message}")
                try:
                    result = output_model.model_validate_json(
                        output_path.read_text(encoding="utf-8")
                    )
                    schema_result = "VALID"
                    return result
                except (OSError, ValidationError) as exc:
                    schema_result = "INVALID"
                    raise SchemaLLMError(
                        f"Codex CLI returned invalid structured output: {exc}"
                    ) from exc
        finally:
            heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task
            self._emit_heartbeat(
                run_id,
                candidate_id,
                task,
                invocation_id,
                "COMPLETED" if exit_code == 0 and schema_result == "VALID" else "FAILED",
                perf_counter() - clock,
            )
            self.calls.append(
                {
                    "provider": "codex",
                    "node": task,
                    "model": model_used,
                    "started_at": started_at,
                    "duration_ms": round((perf_counter() - clock) * 1000),
                    "exit_code": exit_code,
                    "schema_validation_result": schema_result,
                    "retry_count": max(0, int(metadata.get("schema_attempt", 1)) - 1),
                    "ephemeral": True,
                    "sandbox": "read-only",
                    "prior_critique_included": metadata.get("prior_critique_included"),
                    "invocation_id": invocation_id,
                    "skip_git_repo_check_reason": (
                        "each call runs in a non-git temporary directory so the model cannot "
                        "inspect or modify the project workspace"
                    ),
                }
            )

    async def _heartbeat_loop(
        self,
        run_id: str,
        candidate_id: str,
        node: str,
        invocation_id: str,
        clock: float,
    ) -> None:
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            self._emit_heartbeat(
                run_id,
                candidate_id,
                node,
                invocation_id,
                "RUNNING",
                perf_counter() - clock,
            )

    @staticmethod
    def _emit_heartbeat(
        run_id: str,
        candidate_id: str,
        node: str,
        invocation_id: str,
        status: str,
        elapsed_seconds: float,
    ) -> None:
        timestamp = datetime.now(UTC).isoformat(timespec="seconds")
        print(
            f"[{timestamp}] run_id={run_id} candidate_id={candidate_id} "
            f"node={node} invocation_id={invocation_id} status={status} "
            f"elapsed_seconds={elapsed_seconds:.1f}",
            file=sys.stderr,
            flush=True,
        )


CodexCLICompatibleLLM = CodexLLMClient


def create_fresh_llm_client(client: LLMClient) -> LLMClient:
    """Create a new model session without carrying prior generation/critique context."""
    if isinstance(client, CodexLLMClient):
        return CodexLLMClient(semaphore=client._semaphore)
    if isinstance(client, OpenAICompatibleLLM):
        return OpenAICompatibleLLM()
    if isinstance(client, DeterministicFakeLLM):
        return DeterministicFakeLLM(dict(client.responses))
    raise PermanentLLMError(f"fresh sessions unsupported for {type(client).__name__}")


def merge_call_audit(target: LLMClient, fresh: LLMClient) -> None:
    target_calls = getattr(target, "calls", None)
    fresh_calls = getattr(fresh, "calls", None)
    if isinstance(target_calls, list) and isinstance(fresh_calls, list):
        target_calls.extend(fresh_calls)


async def generate_with_schema_retry[ModelT: BaseModel](
    client: LLMClient,
    *,
    task: str,
    input_data: dict,
    output_model: type[ModelT],
    metadata: dict,
    max_schema_retries: int = 1,
) -> ModelT:
    last_error: Exception | None = None
    for attempt in range(max_schema_retries + 1):
        try:
            return await client.generate_structured(
                task=task,
                input_data=input_data,
                output_model=output_model,
                metadata={**metadata, "schema_attempt": attempt + 1},
            )
        except (ValidationError, SchemaLLMError) as exc:
            last_error = exc
    raise SchemaLLMError(
        f"structured output invalid after {max_schema_retries + 1} attempts: {last_error}"
    )


def create_llm_client() -> LLMClient:
    cfg = settings()
    if cfg.llm_provider.lower() == "fake":
        return DeterministicFakeLLM()
    if cfg.llm_provider.lower() == "openai":
        return OpenAICompatibleLLM()
    if cfg.llm_provider.lower() == "codex":
        return CodexLLMClient()
    raise PermanentLLMError(f"unsupported LLM_PROVIDER={cfg.llm_provider}")
