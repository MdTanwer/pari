"""Slash-command completion for the prompt.

Suggestions appear for a leading ``/`` and when Tab is pressed on an empty
line. Once the user has typed a space, the command name is finished and the
menu stays closed.
"""

from collections.abc import Iterable

from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document


COMMAND_METADATA = [
    ("/help", "Show available slash commands and help"),
    ("/diff", "Preview pending or latest unified diffs"),
    ("/undo", "Revert the most recent file change"),
    ("/clear", "Clear terminal screen"),
    ("/model", "Inspect or switch active LLM"),
    ("/add", "Pin reference file or glob into context"),
    ("/snapshot", "Save a named restore point"),
    ("/cost", "Show token and cost totals"),
    ("/reset", "Clear the conversation"),
    ("/login", "Sign in with an account or an API key"),
    ("/logout", "Remove a saved sign-in"),
    ("/exit", "End interactive session"),
    ("/quit", "End interactive session"),
]


_LIMIT_CHOICES = (
    ("Continue", "Run 10 more turns"),
    ("Revert", "Undo the file changes from this turn"),
    ("Stop", "Keep the files and stop"),
)


class LimitChoiceCompleter(Completer):
    """Continue, Revert, and Stop. An empty line lists all three."""

    def get_completions(
        self, document: Document, _complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        text = document.text_before_cursor
        query = text.strip().lower()
        if " " in query:
            return
        for label, desc in _LIMIT_CHOICES:
            if label.lower().startswith(query):
                yield Completion(
                    text=label,
                    start_position=-len(text),
                    display=label,
                    display_meta=desc,
                )


class SlashCommandCompleter(Completer):
    """Prefix match against ``COMMAND_METADATA``, with the description beside it."""

    def __init__(self, commands: list[tuple[str, str]] | None = None):
        self.commands = commands or COMMAND_METADATA

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        text = document.text_before_cursor.lstrip()
        if " " in text:
            return
        # Tab on an empty line should still offer the command list.
        completion = complete_event.completion_requested and not text
        if not text.startswith("/") and not completion:
            return
        query = text.lower()
        for cmd, desc in self.commands:
            if cmd.lower().startswith(query):
                yield Completion(
                    text=cmd,
                    start_position=-len(text),
                    display=cmd,
                    display_meta=desc,
                )
