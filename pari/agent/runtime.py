"""PARI Layer 4: Agent Runtime State and Dispatcher.

Coordinates session state, tool definitions, undo tracking, and communication with the
model.
Executes the full turn lifecycle:
    User Prompt -> Context Assembly -> Provider Completion -> Tool Execution -> Diff
    Review -> Response
"""

import json
import time
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
from pari.agent.reflection import ReflectionManager
from pari.intelligence.repomap import RepoMapGenerator
from pari.providers import get_provider
from pari.providers.base import LLMProvider, ModelResponse, ProviderMessage, ToolCall
from pari.providers.errors import ProviderError
from pari.routing.router import DualModelRouter, router_for
from pari.session.events import SessionEventType
from pari.session.logger import SessionLogger
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
    ):
        self.workspace = workspace.resolve()
        self.session_file = session_file or (self.workspace / ".pari" / "session.jsonl")
        self.model_name = model_name
        self.edit_fallback = edit_fallback
        self.repomap = repomap
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
        if not self.session_id:
            self.start_session()
        self._dag_logger().append_event(
            SessionEventType.SNAPSHOT.value, {"name": label}
        )
        return label

    def reset_conversation(self) -> str:
        """Clear the chat and start a new DAG root. Pinned files stay."""
        self.messages.clear()
        self.turn_warning = ""
        self.session_id = None
        session_id = self.start_session()
        self._dag_logger().append_event(
            SessionEventType.SESSION_START.value, {"session_id": session_id}
        )
        return session_id

    def _dag_logger(self) -> SessionLogger:
        dag = self.workspace / ".pari" / "sessions" / f"{self.session_id}.jsonl"
        return SessionLogger(dag)

    def start_session(self) -> str:
        """Initialize session and emit start event to session.jsonl."""
        self.session_id = f"pari_sess_{uuid.uuid4().hex[:12]}"
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        start_record = {
            "event": "session_start",
            "session_id": self.session_id,
            "workspace": str(self.workspace),
            "timestamp": time.time(),
        }
        with open(self.session_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(start_record) + "\n")
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
        return True

    async def continue_turn(self) -> str:
        """Run another block of turns after the user chooses Continue."""
        return await self.execute_turn("Continue.", max_turns=TURN_EXTENSION)

    async def execute_turn(
        self,
        prompt: str,
        on_tool_call: Callable[[str, dict[str, Any]], None] | None = None,
        on_diff: Callable[[str, str], None] | None = None,
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
            # After a tool call, the results are already on the transcript.
            # A new user message here would hide them from the model.
            if not self._tool_followup:
                self.messages.append(ProviderMessage(role="user", content=context))
            self._tool_followup = False
            # Wide prompts plan once, with no tools. The editor runs the calls.
            resp = await self.router.complete(
                self.messages,
                schemas,
                prompt=prompt,
                active_files=self.pinned_files,
            )
            # Drop tool calls that were cut off so the next step cannot rerun them.
            calls = [] if is_length_stop(resp.stop_reason) else list(resp.tool_calls)
            for index, call in enumerate(calls):
                if not call.id:
                    call.id = f"call_{index}"
            self._tool_followup = bool(calls)
            self.messages.append(
                ProviderMessage(
                    role="assistant",
                    content=resp.text,
                    tool_calls=calls or None,
                )
            )
            return resp

        def remember_result(call: ToolCall, text: str) -> None:
            self.messages.append(
                ProviderMessage(role="tool", content=text, tool_call_id=call.id)
            )

        dag = self.workspace / ".pari" / "sessions" / f"{self.session_id}.jsonl"

        def remember_warning(text: str) -> None:
            self.turn_warning = text

        loop = AgentExecutionLoop(
            max_turns if max_turns is not None else MAX_TURNS,
            registry=self.tools,
            reflection=ReflectionManager(),
            logger=SessionLogger(dag),
            undo=self.undo_manager,
            workspace=self.workspace,
            on_tool_call=on_tool_call,
            on_tool_result=remember_result,
            on_diff=on_diff,
            on_warning=remember_warning,
        )
        # A failed model call must not leave the prompt sitting on the transcript.
        # The next message would otherwise resend a turn the provider never answered.
        sent = len(self.messages)
        try:
            result = await loop.run_turn(
                prompt,
                step,
                lambda response: is_length_stop(response.stop_reason),
                active_files=self._pinned_contents(),
                repo_map=self._repo_map(),
            )
        except ProviderError:
            self._tool_followup = False
            if len(self.messages) == sent + 1 and self.messages[-1].role == "user":
                self.messages.pop()
            raise
        turn_record = {
            "event": "turn_complete",
            "session_id": self.session_id,
            "user_prompt": prompt,
            "response": result.response_text,
            "tokens": result.tokens_used,
            "tool_calls": result.tool_calls_executed,
            "timestamp": time.time(),
        }
        with open(self.session_file, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(turn_record) + "\n")
        self.tokens_in = result.tokens_in
        self.tokens_out = result.tokens_out
        self.cached_tokens = result.cached_tokens
        self.last_result = result
        self.awaiting_limit = result.response_text == TURN_LIMIT_PROMPT
        return result.response_text

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
