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

from pari.agent.guards import is_length_stop
from pari.agent.loop import AgentExecutionLoop
from pari.agent.reflection import ReflectionManager
from pari.providers.base import LLMProvider, ModelResponse, ProviderMessage
from pari.providers.mock import MockOfflineProvider
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
    ):
        self.workspace = workspace.resolve()
        self.session_file = session_file or (self.workspace / ".pari" / "session.jsonl")
        self.provider = provider or MockOfflineProvider()
        self.undo_manager = GuardedUndoManager(self.workspace)
        self.tools = get_default_registry(self.workspace)
        self.pinned_files: list[str] = []
        self.session_id: str | None = None
        self.messages: list[ProviderMessage] = []

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
        if not file_path.exists():
            return False
        clean_rel = str(file_path.relative_to(self.workspace))
        if clean_rel not in self.pinned_files:
            self.pinned_files.append(clean_rel)
        return True

    async def execute_turn(
        self,
        prompt: str,
        on_tool_call: Callable[[str, dict[str, Any]], None] | None = None,
        on_diff: Callable[[str, str], None] | None = None,
    ) -> str:
        """Execute conversational turn with autonomous tool execution."""
        self.on_tool_call = on_tool_call
        self.on_diff = on_diff
        if not self.session_id:
            self.start_session()

        schemas = self.tools.get_schemas()

        async def step(context: str, _turn: int) -> ModelResponse:
            self.messages.append(ProviderMessage(role="user", content=context))
            resp = await self.provider.complete(self.messages, tools=schemas)
            # Drop tool calls that were cut off so the next step cannot rerun them.
            calls = [] if is_length_stop(resp.stop_reason) else resp.tool_calls
            self.messages.append(
                ProviderMessage(
                    role="assistant",
                    content=resp.text,
                    tool_calls=calls or None,
                )
            )
            return resp

        dag = self.workspace / ".pari" / "sessions" / f"{self.session_id}.jsonl"
        loop = AgentExecutionLoop(
            registry=self.tools,
            reflection=ReflectionManager(),
            logger=SessionLogger(dag),
            on_tool_call=on_tool_call,
        )
        result = await loop.run_turn(
            prompt,
            step,
            lambda response: is_length_stop(response.stop_reason),
            active_files=self._pinned_contents(),
        )
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
        return result.response_text

    def _pinned_contents(self) -> list[tuple[str, str]]:
        files: list[tuple[str, str]] = []
        for rel in self.pinned_files:
            path = self.workspace / rel
            try:
                files.append((rel, path.read_text(encoding="utf-8")))
            except (OSError, UnicodeDecodeError):
                continue
        return files
