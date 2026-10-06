"""PARI Layer 4: Agent Runtime State and Dispatcher.

Coordinates session state, tool definitions, undo tracking, and communication with the model.
Executes the full turn lifecycle:
    User Prompt -> Context Assembly -> Provider Completion -> Tool Execution -> Diff Review -> Response
"""

import json
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from pari.providers.base import LLMProvider, ProviderMessage
from pari.providers.mock import MockOfflineProvider
from pari.session.undo import GuardedUndoManager


class AgentRuntime:
    """Central runtime controller for a live PARI session."""

    def __init__(
        self,
        workspace: Path,
        session_file: Optional[Path] = None,
        provider: Optional[LLMProvider] = None,
    ):
        self.workspace = workspace.resolve()
        self.session_file = session_file or (self.workspace / ".pari" / "session.jsonl")
        self.provider = provider or MockOfflineProvider()
        self.undo_manager = GuardedUndoManager(self.workspace)
        self.pinned_files: List[str] = []
        self.session_id: Optional[str] = None
        self.messages: List[ProviderMessage] = []

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
        on_tool_call: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        on_diff: Optional[Callable[[str, str], None]] = None,
    ) -> str:
        """Execute conversational turn with autonomous tool execution."""
        if not self.session_id:
            self.start_session()

        user_msg = ProviderMessage(role="user", content=prompt)
        self.messages.append(user_msg)

        resp = await self.provider.complete(self.messages)
        assistant_msg = ProviderMessage(role="assistant", content=resp.text)
        self.messages.append(assistant_msg)

        # Log turn event
        turn_record = {
            "event": "turn_complete",
            "session_id": self.session_id,
            "user_prompt": prompt,
            "response": resp.text,
            "tokens_in": resp.tokens_in,
            "tokens_out": resp.tokens_out,
            "timestamp": time.time(),
        }
        with open(self.session_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(turn_record) + "\n")

        return resp.text

