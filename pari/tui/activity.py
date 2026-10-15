"""One turn's tool activity.

While a turn runs the screen keeps a few summary rows. Each row is cut to the
terminal width, so the block can always be erased and redrawn in place.
ctrl+o opens every note, command, and output in the transcript view.
"""

import time
from dataclasses import dataclass, field

from rich.text import Text


_RUNNING = {
    "Ran": "Running",
    "Explored": "Exploring",
    "Searched": "Searching",
    "Edited": "Editing",
    "Used": "Using",
}
_KINDS = {
    "bash": ("Ran", "command", "commands"),
    "read_file": ("Explored", "file", "files"),
    "read_tool_output": ("Explored", "file", "files"),
    "find_files": ("Searched", "pattern", "patterns"),
    "grep_search": ("Searched", "pattern", "patterns"),
    "write_file": ("Edited", "file", "files"),
    "edit_file": ("Edited", "file", "files"),
}
_HEAD_GROUPS = 2
_TAIL_GROUPS = 2
_HINT = "  (ctrl+o to expand)"


@dataclass
class Action:
    """One tool call. The body is hidden until the transcript opens."""

    name: str
    summary: str = ""
    body: str = ""
    exit_code: int | None = None

    @property
    def failed(self) -> bool:
        return self.exit_code not in (None, 0)

    @property
    def title(self) -> str:
        if self.name == "bash" and self.exit_code is not None:
            return f"bash  exit {self.exit_code}"
        if self.name == "bash" or not self.summary:
            return self.name
        return f"{self.name}  {self.summary}"


@dataclass
class TurnLog:
    """Notes and tool calls in the order the model produced them."""

    entries: list[Action | str] = field(default_factory=list)
    live: str = ""
    start: int = 0

    @property
    def actions(self) -> list[Action]:
        return [entry for entry in self.entries if isinstance(entry, Action)]

    @property
    def active(self) -> bool:
        """True once a tool has run since the last settled summary."""
        return any(isinstance(entry, Action) for entry in self.entries[self.start :])

    def last_action(self) -> Action | None:
        actions = self.actions
        return actions[-1] if actions else None

    def add_text(self, text: str) -> None:
        self.live += text

    def add_action(self, name: str, summary: str) -> Action:
        self.flush()
        action = Action(name, summary)
        self.entries.append(action)
        return action

    def flush(self) -> None:
        """Move the streaming note into the log."""
        note = self.live.strip()
        if note:
            self.entries.append(note)
        self.live = ""

    def settle(self) -> None:
        """Keep the drawn summary. The next summary covers only later entries."""
        self.flush()
        self.start = len(self.entries)

    def summary_lines(self, width: int) -> list[Text]:
        """Summary rows, each one terminal row wide at most."""
        actions = [e for e in self.entries[self.start :] if isinstance(e, Action)]
        groups = _group(actions)
        rows: list[Text] = []
        if len(groups) > _HEAD_GROUPS + _TAIL_GROUPS + 1:
            hidden = groups[_HEAD_GROUPS:-_TAIL_GROUPS]
            rows.extend(_group_row(group) for group in groups[:_HEAD_GROUPS])
            rows.append(_hidden_row(hidden))
            rows.extend(_group_row(group) for group in groups[-_TAIL_GROUPS:])
        else:
            rows.extend(_group_row(group) for group in groups)
        limit = max(width - 1, 1)
        fitted = [_fit(row, limit) for row in rows]
        note = _last_line(self.live)
        if note:
            fitted.append(_fit(Text(f"○ {note}", style="dim"), limit))
        elif fitted:
            fitted[-1] = _fit(fitted[-1], max(limit - len(_HINT), 1))
            fitted[-1].append(_HINT, style="dim")
        return fitted

    def transcript(self) -> str:
        """Every note, command, and output from this turn."""
        blocks: list[str] = []
        for entry in [*self.entries, self.live.strip()]:
            if isinstance(entry, str):
                if entry:
                    blocks.append(entry)
                continue
            lines = [f"▾ {entry.title}"]
            if entry.name == "bash" and entry.summary:
                lines.append(f"$ {entry.summary}")
            body = entry.body.strip()
            if body:
                lines.append(preview(body, lines=200, chars=20000))
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)


class Elapsed:
    """Spinner text with a seconds counter. Rich redraws it on every tick."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.started = time.monotonic()

    def __rich__(self) -> Text:
        seconds = int(time.monotonic() - self.started)
        return Text(f"{self.label}… {seconds}s", style="dim", no_wrap=True)


def running_label(name: str, summary: str) -> str:
    """What the spinner says while one tool runs."""
    verb = _RUNNING[_kind(name)[0]]
    if not summary:
        return f"{verb} {name}" if verb == "Using" else verb
    if len(summary) > 60:
        summary = summary[:57] + "..."
    return f"{verb} {summary}"


def preview(text: str, *, lines: int = 20, chars: int = 2000) -> str:
    """Keep the start of a tool result. The rest stays in the sidecar."""
    kept = text.splitlines()
    hidden = 0
    if len(kept) > lines:
        hidden = len(kept) - lines
        kept = kept[:lines]
    shown = "\n".join(kept)
    if len(shown) > chars:
        shown = shown[:chars].rstrip()
        hidden = max(hidden, 1)
    if hidden:
        shown += f"\n… {hidden} more lines"
    return shown


def _kind(name: str) -> tuple[str, str, str]:
    return _KINDS.get(name, ("Used", f"{name} call", f"{name} calls"))


def _group(actions: list[Action]) -> list[list[Action]]:
    """Runs of tool calls with the same verb."""
    groups: list[list[Action]] = []
    for action in actions:
        if groups and _kind(groups[-1][0].name)[0] == _kind(action.name)[0]:
            groups[-1].append(action)
        else:
            groups.append([action])
    return groups


def _group_row(group: list[Action]) -> Text:
    verb, one, many = _kind(group[0].name)
    failed = sum(action.failed for action in group)
    row = Text()
    row.append("● ", style="red" if failed else "green")
    row.append(verb, style="bold")
    row.append(f" {len(group)} {one if len(group) == 1 else many}")
    if failed:
        row.append(f", {failed} failed", style="red")
    detail = group[-1].summary
    if detail:
        row.append(f"  ({detail})", style="dim")
    return row


def _hidden_row(groups: list[list[Action]]) -> Text:
    counts: dict[str, int] = {}
    failed = 0
    total = 0
    for group in groups:
        _, _, many = _kind(group[0].name)
        counts[many] = counts.get(many, 0) + len(group)
        failed += sum(action.failed for action in group)
        total += len(group)
    parts = [f"{count} {noun}" for noun, count in counts.items()]
    if failed:
        parts.append(f"{failed} failed")
    return Text(f"… {total} more actions ({', '.join(parts)}) …", style="dim")


def _fit(row: Text, width: int) -> Text:
    fitted = row.copy()
    fitted.truncate(width, overflow="ellipsis")
    return fitted


def _last_line(text: str) -> str:
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    return lines[-1] if lines else ""
