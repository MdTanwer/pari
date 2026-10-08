"""PARI Layer 4: Double-While Execution Loop.

Outer loop: one model call per autonomous turn, up to the turn ceiling.
Inner step: one provider completion. A length stop drops that completion's
tool calls. Tool results, lint failures, and daemon notices become the next
prompt. The turn ends when the model stops asking for tools.
"""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from pari.agent.guards import (
    LENGTH_TRUNCATION_NOTICE,
    MAX_TURNS,
    TURN_WARNING,
    format_daemon_notice,
    is_length_stop,
)
from pari.agent.reflection import ReflectionManager
from pari.context.chunks import ContextChunk, ContextTier, assemble_context
from pari.context.compaction import compact_context
from pari.providers.base import ModelResponse, ToolCall
from pari.session.logger import SessionLogger


class ToolExecutor(Protocol):
    async def execute(self, name: str, arguments: dict[str, Any]) -> Any: ...


@dataclass
class TurnResult:
    response_text: str
    tool_calls_executed: int
    tokens_used: int
    requires_user_input: bool


_TURN_LIMIT = "Turn limit reached. Continue (+10 turns) | Revert | Stop?"


class AgentExecutionLoop:
    """Runs autonomous tool turns until the model stops or a guard fires."""

    def __init__(
        self,
        max_autonomous_turns: int = MAX_TURNS,
        *,
        registry: ToolExecutor | None = None,
        reflection: ReflectionManager | None = None,
        logger: SessionLogger | None = None,
        on_tool_call: Callable[[str, dict[str, Any]], None] | None = None,
    ):
        self.max_autonomous_turns = max_autonomous_turns
        self.registry = registry
        self.reflection = reflection or ReflectionManager()
        self.logger = logger
        self.on_tool_call = on_tool_call

    async def run_turn(
        self,
        prompt: str,
        step_fn: Callable[[str, int], Any],
        is_length_truncated: Callable[[Any], bool],
        active_files: list[tuple[str, str]] | None = None,
    ) -> TurnResult:
        """Execute autonomous steps for one user prompt.

        step_fn(context, turn) returns a ModelResponse or a plain string.
        A length stop is not executed: the tool payload may be cut off.
        """
        self.reflection.reset("turn")
        if self.logger is not None:
            self.logger.append_event("USER_TURN", {"prompt": prompt})
        pending = prompt
        history = ""
        executed = 0
        tokens = 0
        response_text = ""
        for turn in range(1, self.max_autonomous_turns + 1):
            if turn == TURN_WARNING:
                pending = f"Turn {turn} of {self.max_autonomous_turns}.\n{pending}"
            context = _render_context(pending, history, active_files or [])
            step = await _resolve(step_fn(context, turn))
            tokens += _tokens(step)
            response_text = _text(step)
            # A truncated tool call is discarded. The file is left untouched.
            if _truncated(step, is_length_truncated):
                history = _append(history, response_text)
                pending = LENGTH_TRUNCATION_NOTICE
                continue
            calls = _calls(step)
            if not calls:
                self._log_assistant(response_text)
                return TurnResult(response_text, executed, tokens, False)
            feedback, executed, halt = await self._run_calls(calls, executed)
            if halt is not None:
                self._log_assistant(halt)
                return TurnResult(halt, executed, tokens, True)
            history = _append(history, response_text)
            pending = feedback
        self._log_assistant(_TURN_LIMIT)
        return TurnResult(_TURN_LIMIT, executed, tokens, True)

    async def _run_calls(
        self, calls: list[ToolCall], executed: int
    ) -> tuple[str, int, str | None]:
        """Run the calls in order. A failure stops the rest of this batch."""
        notes: list[str] = []
        for call in calls:
            try:
                notes.append(await self._execute_call(call))
            except Exception as exc:
                note = self.reflection.record_failure(
                    "turn", type(exc).__name__, str(exc)
                )
                if not self.reflection.should_retry("turn"):
                    return note, executed, note
                return note, executed, None
            executed += 1
        return "\n".join(notes), executed, None

    async def _execute_call(self, call: ToolCall) -> str:
        if self.registry is None:
            raise RuntimeError(f"No tool registry configured for {call.name}")
        if self.on_tool_call is not None:
            self.on_tool_call(call.name, call.arguments)
        if self.logger is not None:
            self.logger.append_event(
                "TOOL_CALL", {"tool": call.name, "arguments": call.arguments}
            )
        result = await self.registry.execute(call.name, call.arguments)
        text = _render_result(call, result)
        if self.logger is not None:
            self.logger.append_event("TOOL_RESULT", {"tool": call.name, "output": text})
        return text

    def _log_assistant(self, text: str) -> None:
        if self.logger is None:
            return
        self.logger.append_event("ASSISTANT_TURN", {"text": text})


def _render_context(
    prompt: str, history: str, active_files: list[tuple[str, str]]
) -> str:
    chunks: list[ContextChunk] = []
    if active_files:
        body = "\n".join(f"# {name}\n{content}" for name, content in active_files)
        chunks.append(ContextChunk(ContextTier.ACTIVE_FILES, body, "files"))
    if history:
        chunks.append(ContextChunk(ContextTier.TURN_HISTORY, history, "history"))
    chunks.append(ContextChunk(ContextTier.CURRENT_TURN, prompt, "turn"))
    packed = assemble_context(compact_context(chunks))
    return "\n".join(str(item["content"]) for item in packed)


def _append(history: str, text: str) -> str:
    if not history:
        return text
    return f"{history}\n{text}"


async def _resolve(step: Any) -> Any:
    if isinstance(step, Awaitable):
        return await step
    return step


def _truncated(step: Any, is_length_truncated: Callable[[Any], bool]) -> bool:
    if is_length_truncated(step):
        return True
    if isinstance(step, ModelResponse):
        return is_length_stop(step.stop_reason)
    return False


def _calls(step: Any) -> list[ToolCall]:
    if isinstance(step, ModelResponse):
        return list(step.tool_calls)
    return []


def _text(step: Any) -> str:
    if isinstance(step, ModelResponse):
        return step.text
    if isinstance(step, str):
        return step
    raise TypeError("step_fn must return a string or ModelResponse")


def _tokens(step: Any) -> int:
    if isinstance(step, ModelResponse):
        return step.tokens_in + step.tokens_out
    return 0


def _render_result(call: ToolCall, result: Any) -> str:
    timed_out = False
    if isinstance(result, str):
        text = result
    elif isinstance(result, dict):
        timed_out = bool(result.get("timed_out"))
        text = json.dumps(result)
    else:
        text = str(result)
    if not timed_out:
        return text
    command = str(call.arguments.get("command", call.name))
    return format_daemon_notice(command) + "\n" + text
