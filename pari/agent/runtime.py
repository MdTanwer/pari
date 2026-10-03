"""PARI Layer 4: Agent Runtime State and Dispatcher.

Coordinates session state, tool definitions, undo tracking, and communication with the model.
Executes the full turn lifecycle:
    User Prompt -> Context Assembly -> Provider Completion -> Tool Execution -> Diff Review -> Response
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class AgentRuntime:
    """Central runtime controller for a live PARI session."""

    def __init__(self, workspace: Path, session_file: Optional[Path] = None):
        self.workspace = workspace.resolve()
        # TODO: Initialize logger, undo manager, tool registry, and provider

    def start_session(self) -> str:
        """Initialize session and emit start event."""
        raise NotImplementedError

    def add_pinned_file(self, rel_path: str) -> bool:
        """Pin reference file into active context."""
        raise NotImplementedError

    async def execute_turn(
        self,
        prompt: str,
        on_tool_call: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        on_diff: Optional[Callable[[str, str], None]] = None,
    ) -> str:
        """Execute conversational turn with autonomous tool execution."""
        raise NotImplementedError
