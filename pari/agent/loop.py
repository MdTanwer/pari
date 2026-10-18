"""PARI Layer 4: Double-While Execution Loop.

Outer loop: one model call per autonomous turn, up to the turn ceiling.
Inner step: one provider completion. A length stop drops that completion's
tool calls. Tool results, lint failures, and daemon notices become the next
prompt. The turn ends when the model stops asking for tools.
"""

import json
import subprocess
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pari.agent.guards import (
    DAEMON_IDLE_SECONDS,
    LENGTH_TRUNCATION_NOTICE,
    MAX_TURNS,
    TURN_LIMIT_PROMPT,
    TURN_WARNING,
    format_daemon_notice,
    is_length_stop,
)
from pari.agent.lint import lint_python
from pari.agent.reflection import ReflectionManager
from pari.edit.diff import generate_unified_diff
from pari.fs.path import resolve_safe_path
from pari.providers.message import ToolCall
from pari.providers.response import ModelResponse
from pari.sandbox.base import is_package_install
from pari.session.logger import SessionLogger
from pari.session.undo import GuardedUndoManager


class ToolExecutor(Protocol):
    async def execute(self, name: str, arguments: dict[str, Any]) -> Any: ...


@dataclass
class TurnResult:
    response_text: str
    tool_calls_executed: int
    tokens_used: int
    requires_user_input: bool
    warning: str = ""
    diff: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cached_tokens: int = 0


_FILE_TOOLS = frozenset({"write_file", "edit_file"})


class AgentExecutionLoop:
    """Runs autonomous tool turns until the model stops or a guard fires."""

    def __init__(
        self,
        max_autonomous_turns: int = MAX_TURNS,
        *,
        registry: ToolExecutor | None = None,
        reflection: ReflectionManager | None = None,
        logger: SessionLogger | None = None,
        undo: GuardedUndoManager | None = None,
        workspace: Path | None = None,
        on_tool_call: Callable[[str, dict[str, Any]], None] | None = None,
        on_tool_result: Callable[[ToolCall, str], None] | None = None,
        on_diff: Callable[[str, str], None] | None = None,
        on_warning: Callable[[str], None] | None = None,
    ):
        self.max_autonomous_turns = max_autonomous_turns
        self.registry = registry
        self.reflection = reflection or ReflectionManager()
        self.logger = logger
        self.undo = undo
        self.workspace = workspace
        self.on_tool_call = on_tool_call
        self.on_tool_result = on_tool_result
        self.on_diff = on_diff
        self.on_warning = on_warning
        self._warning = ""

    async def run_turn(
        self,
        prompt: str,
        step_fn: Callable[[str, int], Any],
        is_length_truncated: Callable[[Any], bool],
        active_files: list[tuple[str, str]] | None = None,
        repo_map: str = "",
    ) -> TurnResult:
        """Execute autonomous steps for one user prompt.

        step_fn(context, turn) returns a ModelResponse or a plain string.
        A length stop is not executed: the tool payload may be cut off.
        """
        self.reflection.reset("turn")
        if self.undo is not None:
            self.undo.begin_turn()
        if self.logger is not None:
            self.logger.append_event("USER_TURN", {"prompt": prompt})
        pending = prompt
        history = ""
        executed = 0
        tokens_in = 0
        tokens_out = 0
        cached_tokens = 0
        response_text = ""

        def finish(
            text: str, count: int, needs_user: bool, *, capture_diff: bool = False
        ) -> TurnResult:
            return self._finish(
                text,
                count,
                tokens_in + tokens_out,
                needs_user,
                capture_diff=capture_diff,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cached_tokens=cached_tokens,
            )

        for turn in range(1, self.max_autonomous_turns + 1):
            self._note_turn(turn)
            context = _render_context(pending, history, active_files or [], repo_map)
            step = await _resolve(step_fn(context, turn))
            step_in, step_out, step_cached = _usage(step)
            tokens_in += step_in
            tokens_out += step_out
            cached_tokens += step_cached
            response_text = _text(step)
            # A truncated tool call is discarded. The file is left untouched.
            if _truncated(step, is_length_truncated):
                history = _append(history, response_text)
                pending = LENGTH_TRUNCATION_NOTICE
                continue
            calls = _calls(step)
            if not calls:
                return finish(response_text, executed, False)
            feedback, executed, halt = await self._run_calls(calls, executed)
            if halt is not None:
                return finish(halt, executed, True)
            history = _append(history, response_text)
            pending = feedback
        return finish(TURN_LIMIT_PROMPT, executed, True, capture_diff=True)

    async def _run_calls(
        self, calls: list[ToolCall], executed: int
    ) -> tuple[str, int, str | None]:
        """Run the calls in order. A failure stops the rest of this batch."""
        notes: list[str] = []
        for index, call in enumerate(calls):
            path = _file_path(call)
            existed = self._is_file(path) if path is not None else False
            before = self._read_rel(path) if existed else ""
            try:
                text = await self._execute_call(call)
            except Exception as exc:
                self._report_result(call, f"{type(exc).__name__}: {exc}")
                self._skip_rest(calls[index + 1 :])
                return self._fail(type(exc).__name__, str(exc), executed)
            executed += 1
            if path is not None:
                after = self._read_rel(path)
                self._snapshot(path, before, after, existed_before=existed)
                lint = lint_python(path, after)
                if lint is not None:
                    self._report_result(call, lint)
                    self._skip_rest(calls[index + 1 :])
                    return self._fail("LINT ERROR", lint, executed)
            self._report_result(call, text)
            notes.append(text)
        return "\n".join(notes), executed, None

    async def _execute_call(self, call: ToolCall) -> str:
        if self.registry is None:
            raise RuntimeError(f"No tool registry configured for {call.name}")
        if self.on_tool_call is not None:
            self.on_tool_call(call.name, call.arguments)
        if self.logger is not None:
            self.logger.append_event(
                "TOOL_CALL",
                {"tool": call.name, "id": call.id, "arguments": call.arguments},
            )
        result = await self.registry.execute(call.name, call.arguments)
        self._note_package_install(call, result)
        text = _render_result(call, result)
        if self.logger is not None:
            self.logger.append_event("TOOL_RESULT", {"tool": call.name, "output": text})
        return text

    def _note_package_install(self, call: ToolCall, result: Any) -> None:
        """A successful install cannot be undone by restoring files."""
        if self.undo is None or call.name != "bash":
            return
        if not isinstance(result, dict) or result.get("exit_code") != 0:
            return
        command = call.arguments.get("command")
        if isinstance(command, str) and is_package_install(command):
            self.undo.record_side_effect(command)

    def _report_result(self, call: ToolCall, text: str) -> None:
        if self.on_tool_result is not None:
            self.on_tool_result(call, text)

    def _skip_rest(self, calls: list[ToolCall]) -> None:
        for call in calls:
            self._report_result(call, "Skipped because an earlier call failed.")

    def _log_assistant(self, text: str) -> None:
        if self.logger is None:
            return
        self.logger.append_event("ASSISTANT_TURN", {"text": text})

    def _note_turn(self, turn: int) -> None:
        """Warn the user at turn 30. The warning stays out of the model prompt."""
        if turn != TURN_WARNING:
            return
        self._warning = f"Turn {turn} of {self.max_autonomous_turns}."
        if self.on_warning is not None:
            self.on_warning(self._warning)

    def _fail(
        self, kind: str, message: str, executed: int
    ) -> tuple[str, int, str | None]:
        note = self.reflection.record_failure("turn", kind, message)
        if kind == "LINT ERROR":
            shown = message
        else:
            shown = note
        if self.reflection.should_retry("turn"):
            return shown, executed, None
        if kind == "LINT ERROR":
            shown = f"{message}\nReflection limit reached. Stop and ask the user."
        return shown, executed, shown

    def _finish(
        self,
        text: str,
        executed: int,
        tokens: int,
        needs_user: bool,
        *,
        capture_diff: bool = False,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cached_tokens: int = 0,
    ) -> TurnResult:
        diff = ""
        if capture_diff:
            diff = workspace_diff(self.workspace)
            if diff and self.on_diff is not None:
                self.on_diff(".", diff)
        self._log_assistant(text)
        return TurnResult(
            text,
            executed,
            tokens,
            needs_user,
            self._warning,
            diff,
            tokens_in,
            tokens_out,
            cached_tokens,
        )

    def _is_file(self, rel: str) -> bool:
        if self.workspace is None:
            return False
        try:
            path = resolve_safe_path(self.workspace, rel)
        except PermissionError:
            return False
        return path.is_file()

    def _read_rel(self, rel: str) -> str:
        if self.workspace is None:
            return ""
        try:
            path = resolve_safe_path(self.workspace, rel)
        except PermissionError:
            return ""
        if not path.is_file():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ""

    def _snapshot(
        self, rel: str, before: str, after: str, *, existed_before: bool
    ) -> None:
        if existed_before and before == after:
            return
        if not existed_before and not self._is_file(rel):
            return
        if self.undo is not None:
            self.undo.record_snapshot(rel, before, after, existed_before=existed_before)
        if self.logger is not None:
            self.logger.append_event("FILE_SNAPSHOT", {"path": rel})
        if self.on_diff is not None:
            self.on_diff(rel, generate_unified_diff(before, after, rel))


def _render_context(
    prompt: str,
    history: str = "",
    active_files: list[tuple[str, str]] | None = None,
    repo_map: str = "",
) -> str:
    """Return the turn prompt.

    Repo map and pinned files live in the stable system prefix.
    """
    _ = history, active_files, repo_map
    return prompt


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


def _usage(step: Any) -> tuple[int, int, int]:
    if isinstance(step, ModelResponse):
        return step.tokens_in, step.tokens_out, step.cached_tokens
    return 0, 0, 0


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
    seconds = _idle_seconds(result)
    return format_daemon_notice(command, seconds) + "\n" + text


def _file_path(call: ToolCall) -> str | None:
    if call.name not in _FILE_TOOLS:
        return None
    path = call.arguments.get("path")
    if not isinstance(path, str) or not path:
        return None
    return path


def _idle_seconds(result: Any) -> int:
    """Prefer the daemon window over the tool's longer hard timeout."""
    if not isinstance(result, dict):
        return DAEMON_IDLE_SECONDS
    for key in ("idle_seconds", "timeout"):
        raw = result.get(key)
        if isinstance(raw, int | float):
            return int(raw)
    return DAEMON_IDLE_SECONDS


def workspace_diff(workspace: Path | None) -> str:
    """Return the working-tree diff, or an empty string when git cannot run."""
    if workspace is None:
        return ""
    try:
        completed = subprocess.run(
            ["git", "diff", "--no-ext-diff", "--"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout
