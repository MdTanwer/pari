"""PARI Layer 9: Interactive Terminal Application & REPL.

Orchestrates prompt_toolkit command-line inputs, Rich differential rendering,
live tool execution feedback, unified diff inspection, and slash commands.
"""

from pathlib import Path


class TerminalApp:
    """Manages developer interactions in the terminal REPL."""

    def __init__(self, workspace: Path):
        self.workspace = workspace.resolve()

    def print_welcome(self):
        """Display startup banner."""
        raise NotImplementedError

    async def run_repl(self):
        """Main interactive terminal read-eval-print loop."""
        raise NotImplementedError
