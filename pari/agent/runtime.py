"""PARI Layer 4: Agent Runtime State and Dispatcher.

Coordinates session state, tool definitions, undo tracking, and communication with the
model.
Executes the full turn lifecycle:
    User Prompt -> Context Assembly -> Provider Completion -> Tool Execution -> Diff
    Review -> Response
"""

import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pari.agent.guards import (
    MAX_TURNS,
    TURN_EXTENSION,
    TURN_LIMIT_PROMPT,
    is_length_stop,
)
from pari.agent.loop import AgentExecutionLoop, TurnResult
from pari.agent.prompt import system_prompt
from pari.agent.reflection import ReflectionManager
from pari.context.compaction import (
    DEFAULT_COMPACTION_THRESHOLD,
    DEFAULT_MAX_TOKENS,
    compact_messages,
)
from pari.intelligence.repomap import RepoMapGenerator
from pari.providers import get_provider
from pari.providers.base import LLMProvider
from pari.providers.exceptions import ProviderError
from pari.providers.message import ProviderMessage, ToolCall
from pari.providers.response import ModelResponse
from pari.routing.router import DualModelRouter, router_for
from pari.session.checkpoint import CheckpointManager, restore_transcript
from pari.session.events import SessionEventType
from pari.session.logger import SessionLogger
from pari.session.paths import default_session_dir
from pari.session.undo import GuardedUndoManager
from pari.tools.registry import get_default_registry


class AgentRuntime:
    """Central runtime controller for a live PARI session."""

    def __init__(
        self,
        workspace: Path,
        session_file: Path | None = None,
        provider: LLMProvider | None = None,
        model_name: str = "pari-core",
        edit_fallback: str = "none",
        repomap: str = "off",
        router: DualModelRouter | None = None,
        sandbox_mode: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        compaction_threshold: float = DEFAULT_COMPACTION_THRESHOLD,
    ):
        self.workspace = workspace.resolve()
        if session_file is not None:
            self.session_file = session_file
            self.session_dir = session_file.parent
        else:
            self.session_dir = default_session_dir(self.workspace)
            self.session_file = self.session_dir / "session.jsonl"
        self.model_name = model_name
        self.edit_fallback = edit_fallback
        self.repomap = repomap
        self.max_tokens = max_tokens
        self.compaction_threshold = compaction_threshold
        # An explicit provider wins. Otherwise the model name selects one.
        self.provider = provider if provider is not None else get_provider(model_name)
        # A caller-supplied router is kept. Otherwise Haiku pairs with Sonnet.
        self._owns_router = router is None
        self.router = router if router is not None else router_for(self.provider)
        self.undo_manager = GuardedUndoManager(self.workspace)
        self.tools = get_default_registry(
            self.workspace,
            edit_fallback=edit_fallback,
            sandbox_mode=sandbox_mode,
        )
        self.awaiting_limit = False
        self.last_result: TurnResult | None = None
        self._tool_followup = False
        self.pinned_files: list[str] = []
        self.session_id: str | None = None
        self._logger: SessionLogger | None = None
        self._checkpoints: CheckpointManager | None = None
        self.messages: list[ProviderMessage] = []
        self.turn_warning = ""
        self.tokens_in = 0
        self.tokens_out = 0
        self.cached_tokens = 0

    def set_model(self, model_name: str) -> None:
        """Switch provider. The old model stays in place if selection fails."""
        provider = get_provider(model_name)
        self.provider = provider
        self.model_name = model_name
        if self._owns_router:
            self.router = router_for(provider)

    def save_snapshot(self, name: str) -> str:
        """Write a named restore tag on the session DAG. Files are not copied."""
        label = name.strip() or "manual"
        logger = self._ensure_logger()
        logger.append_event(SessionEventType.SNAPSHOT.value, {"name": label})
        return label

    def reset_conversation(self) -> str:
        """Clear the chat and start a new DAG root. Pinned files stay."""
        self.messages.clear()
        self.turn_warning = ""
        self.session_id = None
        self._logger = None
        self._checkpoints = None
        return self.start_session()

    def resume(self, session_id: str | None = None) -> str:
        """Load a session DAG into ``messages``. Omit the id to use the latest."""
        path = self._resolve_dag(session_id)
        logger = SessionLogger(path)
        payloads, turns = restore_transcript(
            logger.read_events(), logger.session_file.parent
        )
        self.session_id = path.stem
        self.session_file = path
        self._logger = logger
        self._checkpoints = CheckpointManager(logger)
        self._checkpoints.restore_turns(turns)
        self.messages = [
            message
            for message in (_message_from_payload(item) for item in payloads)
            if message is not None
        ]
        return self.session_id

    def _dag_file(self, session_id: str | None = None) -> Path:
        sid = session_id or self.session_id or "default"
        return self.session_dir / "dags" / f"{sid}.jsonl"

    def _resolve_dag(self, session_id: str | None) -> Path:
        directory = self.session_dir / "dags"
        if session_id:
            path = directory / f"{session_id}.jsonl"
            if not path.is_file():
                raise FileNotFoundError(f"Session not found: {session_id}")
            return path
        if not directory.is_dir():
            raise FileNotFoundError("No session to resume.")
        files = [path for path in directory.glob("*.jsonl") if path.is_file()]
        if not files:
            raise FileNotFoundError("No session to resume.")
        return max(files, key=lambda path: path.stat().st_mtime)

    def _ensure_logger(self) -> SessionLogger:
        if not self.session_id:
            self.start_session()
        logger = self._logger
        if logger is None:
            logger = SessionLogger(self._dag_file())
            self._logger = logger
            self._checkpoints = CheckpointManager(logger)
        return logger

    def start_session(self) -> str:
        """Open a new checksummed session DAG. The plain session.jsonl is not used."""
        self.session_id = f"pari_sess_{uuid.uuid4().hex[:12]}"
        self._logger = SessionLogger(self._dag_file())
        self._checkpoints = CheckpointManager(self._logger)
        self.session_file = self._logger.session_file
        self._logger.append_event(
            SessionEventType.SESSION_START.value,
            {"session_id": self.session_id, "workspace": str(self.workspace)},
        )
        return self.session_id

    def add_pinned_file(self, rel_path: str) -> bool:
        """Pin reference file into active context."""
        file_path = (self.workspace / rel_path).resolve()
        if not file_path.is_file():
            return False
        try:
            clean_rel = str(file_path.relative_to(self.workspace))
        except ValueError:
            return False
        if clean_rel not in self.pinned_files:
            self.pinned_files.append(clean_rel)
            if self.messages and self.messages[0].role == "system":
                self._sync_system_message()
        return True

    async def continue_turn(
        self,
        on_tool_call: Callable[[str, dict[str, Any]], None] | None = None,
        on_diff: Callable[[str, str], None] | None = None,
        on_tool_result: Callable[[ToolCall, str], None] | None = None,
        on_step_text: Callable[[str], None] | None = None,
        on_delta: Callable[[str], None] | None = None,
    ) -> str:
        """Run another block of turns after the user chooses Continue."""
        return await self.execute_turn(
            "Continue.",
            on_tool_call=on_tool_call,
            on_diff=on_diff,
            on_tool_result=on_tool_result,
            on_step_text=on_step_text,
            on_delta=on_delta,
            max_turns=TURN_EXTENSION,
        )

    async def execute_turn(
        self,
        prompt: str,
        on_tool_call: Callable[[str, dict[str, Any]], None] | None = None,
        on_diff: Callable[[str, str], None] | None = None,
        on_tool_result: Callable[[ToolCall, str], None] | None = None,
        on_step_text: Callable[[str], None] | None = None,
        on_delta: Callable[[str], None] | None = None,
        *,
        max_turns: int | None = None,
    ) -> str:
        """Execute conversational turn with autonomous tool execution."""
        self.on_tool_call = on_tool_call
        self.on_diff = on_diff
        self.turn_warning = ""
        self._tool_followup = False
        if not self.session_id:
            self.start_session()
        self.router.begin_turn()

        schemas = self.tools.get_schemas()

        async def step(context: str, _turn: int) -> ModelResponse:
            self._sync_system_message()
            self._maybe_compact()
            if not self._tool_followup:
                self.messages.append(ProviderMessage(role="user", content=context))
            self._tool_followup = False
            self._maybe_compact()
            resp = await self.router.complete(
                self.messages,
                schemas,
                prompt=prompt,
                active_files=self.pinned_files,
                on_delta=on_delta,
            )
            self.tokens_in = resp.tokens_in
            calls = [] if is_length_stop(resp.stop_reason) else list(resp.tool_calls)
            for index, call in enumerate(calls):
                if not call.id:
                    call.id = f"call_{index}"
            self._tool_followup = bool(calls)
            if (
                calls
                and resp.text.strip()
                and on_step_text is not None
                and on_delta is None
            ):
                on_step_text(resp.text)
            self.messages.append(
                ProviderMessage(
                    role="assistant",
                    content=resp.text,
                    tool_calls=calls or None,
                )
            )
            self._maybe_compact()
            return resp

        def remember_result(call: ToolCall, text: str) -> None:
            self.messages.append(
                ProviderMessage(role="tool", content=text, tool_call_id=call.id)
            )
            if on_tool_result is not None:
                on_tool_result(call, text)

        logger = self._ensure_logger()

        def remember_warning(text: str) -> None:
            self.turn_warning = text

        loop = AgentExecutionLoop(
            max_turns if max_turns is not None else MAX_TURNS,
            registry=self.tools,
            reflection=ReflectionManager(),
            logger=logger,
            undo=self.undo_manager,
            workspace=self.workspace,
            on_tool_call=on_tool_call,
            on_tool_result=remember_result,
            on_diff=on_diff,
            on_warning=remember_warning,
        )
        sent = len(self.messages)
        try:
            result = await loop.run_turn(
                prompt,
                step,
                lambda response: is_length_stop(response.stop_reason),
            )
        except ProviderError:
            self._tool_followup = False
            added = self.messages[sent:]
            if added and all(item.role in {"system", "user"} for item in added):
                del self.messages[sent:]
            raise
        self.tokens_in = result.tokens_in
        self.tokens_out = result.tokens_out
        self.cached_tokens = result.cached_tokens
        self.last_result = result
        self.awaiting_limit = result.response_text == TURN_LIMIT_PROMPT
        self._maybe_compact()
        checkpoints = self._checkpoints
        if checkpoints is not None:
            checkpoints.record_turn(
                {"messages": [_message_payload(item) for item in self.messages]}
            )
        return result.response_text

    def _build_system_prompt(self) -> str:
        parts = [system_prompt(self.workspace)]
        repo_map = self._repo_map()
        if repo_map:
            parts.append(repo_map)
        pinned = self._pinned_contents()
        if pinned:
            body = "\n".join(f"# {name}\n{content}" for name, content in pinned)
            parts.append(body)
        return "\n\n".join(parts)

    def _sync_system_message(self) -> None:
        content = self._build_system_prompt()
        if not self.messages:
            self.messages.append(
                ProviderMessage(
                    role="system",
                    content=content,
                    cache_control=True,
                )
            )
        elif self.messages[0].role == "system":
            self.messages[0].content = content
            self.messages[0].cache_control = True
        else:
            self.messages.insert(
                0,
                ProviderMessage(
                    role="system",
                    content=content,
                    cache_control=True,
                ),
            )

    def _maybe_compact(self) -> None:
        self.messages = compact_messages(
            self.messages,
            tokens_in=self.tokens_in,
            max_tokens=self.max_tokens,
            compaction_threshold=self.compaction_threshold,
        )

    def _repo_map(self) -> str:
        """Tier 3 map. ``off`` leaves search tools as the only navigation."""
        if self.repomap != "ppr":
            return ""
        return RepoMapGenerator(self.workspace).generate(self.pinned_files)

    def _pinned_contents(self) -> list[tuple[str, str]]:
        files: list[tuple[str, str]] = []
        for rel in self.pinned_files:
            path = self.workspace / rel
            try:
                files.append((rel, path.read_text(encoding="utf-8")))
            except (OSError, UnicodeDecodeError):
                continue
        return files


def _message_payload(message: ProviderMessage) -> dict[str, Any]:
    payload: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.tool_calls:
        payload["tool_calls"] = [
            {"id": call.id, "name": call.name, "arguments": call.arguments}
            for call in message.tool_calls
        ]
    if message.tool_call_id:
        payload["tool_call_id"] = message.tool_call_id
    return payload


def _message_from_payload(payload: dict[str, Any]) -> ProviderMessage | None:
    role = payload.get("role")
    if role not in {"system", "user", "assistant", "tool"}:
        return None
    raw_calls = payload.get("tool_calls")
    calls = None
    if isinstance(raw_calls, list):
        calls = []
        for item in raw_calls:
            if not isinstance(item, dict):
                continue
            arguments = item.get("arguments")
            calls.append(
                ToolCall(
                    id=str(item.get("id", "")),
                    name=str(item.get("name", "")),
                    arguments=arguments if isinstance(arguments, dict) else {},
                )
            )
    tool_call_id = payload.get("tool_call_id")
    return ProviderMessage(
        role=role,
        content=str(payload.get("content", "")),
        tool_calls=calls or None,
        tool_call_id=tool_call_id if isinstance(tool_call_id, str) else None,
    )
