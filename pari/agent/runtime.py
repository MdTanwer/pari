"""PARI Layer 4: Agent Runtime State and Dispatcher.

Coordinates session state, tool definitions, undo tracking, and communication with the model.
Executes the full turn lifecycle:
    User Prompt -> Context Assembly -> Provider Completion -> Tool Execution -> Diff Review -> Response
"""

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from pari.providers import LLMProvider, ProviderMessage, get_provider
from pari.tools.registry import ToolRegistry, get_default_registry
from pari.session.events import SessionEventType
from pari.session.logger import SessionLogger
from pari.session.undo import GuardedUndoManager
from pari.context.epoch import ContextEpoch
from pari.intelligence.repomap import RepoMapGenerator
from pari.fs.atomic import read_file
from pari.fs.path import resolve_safe_path


class AgentRuntime:
    """Central runtime controller for a live PARI session."""

    def __init__(
        self,
        workspace: Path,
        session_file: Optional[Path] = None,
        provider: Optional[LLMProvider] = None,
        tool_registry: Optional[ToolRegistry] = None,
    ):
        self.workspace = workspace.resolve()
        log_path = session_file or (self.workspace / ".pari" / "session.jsonl")
        self.logger = SessionLogger(log_path)
        self.undo_manager = GuardedUndoManager(self.workspace)
        self.tools = tool_registry or get_default_registry(self.workspace)
        self.provider = provider or get_provider()
        self.repomap = RepoMapGenerator(self.workspace)
        self.pinned_files: List[Path] = []
        self.turn_index = 0
        self.history: List[ProviderMessage] = []

    def start_session(self) -> str:
        event = self.logger.log(
            SessionEventType.SESSION_START,
            payload={"workspace": str(self.workspace), "model": self.provider.model_name},
        )
        return event.id

    def add_pinned_file(self, rel_path: str) -> bool:
        safe_path = resolve_safe_path(self.workspace, rel_path)
        if safe_path.exists() and safe_path not in self.pinned_files:
            self.pinned_files.append(safe_path)
            return True
        return False

    def _build_system_prompt(self) -> str:
        rules_file = self.workspace / ".pari" / "rules"
        custom_rules = rules_file.read_text() if rules_file.exists() else ""

        system = (
            "You are PARI, a state-of-the-art terminal coding agent.\n"
            "You edit files with surgical exactness using edit_file with single-match Stop-on-Ambiguity.\n"
            "All bash commands run inside a secure sandbox.\n"
            "Execute commands directly when needed, report results clearly, and avoid unnecessary chat.\n"
        )
        if custom_rules:
            system += f"\nProject Rules:\n{custom_rules}\n"
        return system

    def assemble_messages(self, current_prompt: str) -> List[ProviderMessage]:
        messages: List[ProviderMessage] = []

        # Tier 1: System prompt & static repomap
        repomap_content = self.repomap.generate()
        system_content = f"{self._build_system_prompt()}\n{repomap_content}"
        messages.append(ProviderMessage(role="system", content=system_content, cache_control=True))

        # Tier 5: Pinned active files
        for p in self.pinned_files:
            try:
                rel = p.relative_to(self.workspace)
                content = read_file(p)
                file_msg = f"# Active File: {rel}\n```\n{content}\n```"
                messages.append(ProviderMessage(role="user", content=file_msg))
                messages.append(ProviderMessage(role="assistant", content=f"Loaded {rel} into active context."))
            except Exception:
                continue

        # Tier 6: Recent history (last 10 turns)
        messages.extend(self.history[-10:])

        # Tier 7: Current user turn
        messages.append(ProviderMessage(role="user", content=current_prompt))
        return messages

    async def execute_turn(
        self,
        prompt: str,
        on_tool_call: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        on_diff: Optional[Callable[[str, str], None]] = None,
    ) -> str:
        """Executes a single conversational turn with autonomous tool execution."""
        self.turn_index += 1
        self.logger.log(
            SessionEventType.USER_PROMPT,
            payload={"turn": self.turn_index, "prompt": prompt},
        )

        messages = self.assemble_messages(prompt)
        tool_schemas = self.tools.get_schemas()

        max_steps = 15
        step = 0
        final_text = ""

        while step < max_steps:
            step += 1
            response = await self.provider.complete(messages, tools=tool_schemas)

            if response.text:
                final_text = response.text

            if not response.has_tool_calls:
                # Turn complete, record assistant response
                self.history.append(ProviderMessage(role="user", content=prompt))
                self.history.append(ProviderMessage(role="assistant", content=final_text))
                self.logger.log(
                    SessionEventType.ASSISTANT_RESPONSE,
                    payload={"turn": self.turn_index, "response": final_text},
                )
                return final_text

            # Execute tool calls
            for tool_call in response.tool_calls:
                self.logger.log(
                    SessionEventType.TOOL_CALL,
                    payload={"tool": tool_call.name, "args": tool_call.arguments},
                )
                if on_tool_call:
                    on_tool_call(tool_call.name, tool_call.arguments)

                # If modifying files, capture snapshot for /undo
                if tool_call.name in ("edit_file", "write_file"):
                    target_file = tool_call.arguments.get("path")
                    if target_file:
                        try:
                            safe_p = resolve_safe_path(self.workspace, target_file)
                            pre_content = read_file(safe_p) if safe_p.exists() else ""
                        except Exception:
                            pre_content = ""

                try:
                    tool_output = await self.tools.execute(tool_call.name, tool_call.arguments)
                except Exception as e:
                    tool_output = f"Error executing {tool_call.name}: {e}"

                # Check if edit tool produced a diff to review
                if isinstance(tool_output, dict) and "diff" in tool_output and on_diff:
                    on_diff(tool_call.arguments.get("path", ""), tool_output["diff"])

                # If file was modified, record post-snapshot in undo manager
                if tool_call.name in ("edit_file", "write_file") and target_file:
                    try:
                        safe_p = resolve_safe_path(self.workspace, target_file)
                        post_content = read_file(safe_p) if safe_p.exists() else ""
                        self.undo_manager.record_snapshot(target_file, pre_content, post_content)
                    except Exception:
                        pass

                self.logger.log(
                    SessionEventType.TOOL_RESULT,
                    payload={"tool": tool_call.name, "output": str(tool_output)},
                )

                # Append tool result to context for next step
                result_str = json.dumps(tool_output) if isinstance(tool_output, (dict, list)) else str(tool_output)
                messages.append(ProviderMessage(role="assistant", content=f"Ran tool: {tool_call.name}"))
                messages.append(ProviderMessage(role="user", content=f"Tool result for {tool_call.name}:\n{result_str}"))

        return final_text
