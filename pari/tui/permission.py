"""Boxed permission popup drawn under the activity summary.

It is not full screen. It erases itself when the user picks, so the summary
rows above it can still be redrawn in place.
"""

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.formatted_text.utils import fragment_list_width
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style
from prompt_toolkit.utils import get_cwidth

from pari.permissions.policy import Decision, needs_phrase


CHOICES = (
    ("once", "Run once"),
    ("repo", "Always allow in this repo"),
    ("no", "Skip this command"),
)
_MAX_WIDTH = 78
_FOOTER = (
    ("class:perm.key", "↑↓"),
    ("class:perm.hint", " move   "),
    ("class:perm.key", "enter"),
    ("class:perm.hint", " confirm   "),
    ("class:perm.key", "1-3"),
    ("class:perm.hint", " quick pick   "),
    ("class:perm.key", "esc"),
    ("class:perm.hint", " cancel"),
)
_SHORT_FOOTER = (
    ("class:perm.key", "↑↓ enter 1-3"),
    ("class:perm.hint", " pick  "),
    ("class:perm.key", "esc"),
    ("class:perm.hint", " cancel"),
)

PERMISSION_STYLE = Style.from_dict(
    {
        "perm.border": "fg:#3b82f6",
        "perm.title": "fg:#93c5fd bold",
        "perm.badge": "bg:#3a2a12 fg:#f59e0b",
        "perm.label": "fg:#717882",
        "perm.code": "bg:#1f2937 fg:#f3f4f6 bold",
        "perm.dollar": "bg:#1f2937 fg:#717882",
        "perm.detail": "fg:#9ca3af",
        "perm.question": "fg:#f3f4f6 bold",
        "perm.option": "fg:#e5e7eb",
        "perm.number": "fg:#717882",
        "perm.selected": "bg:#2563eb fg:#ffffff bold",
        "perm.key": "fg:#e5e7eb",
        "perm.hint": "fg:#717882",
    }
)


def badges(decision: Decision) -> list[str]:
    grants = decision.grants
    labels = []
    if grants.network:
        labels.append("uses network")
    if grants.git_write:
        labels.append("writes to git")
    if grants.secrets:
        labels.append("reads secrets")
    if grants.github_token:
        labels.append("uses GitHub token")
    return labels


class PermissionPopup:
    """The box and the highlighted choice."""

    def __init__(self, decision: Decision):
        self.decision = decision
        self.selected = 0

    def move(self, step: int) -> None:
        self.selected = (self.selected + step) % len(CHOICES)

    def choice(self) -> str:
        return CHOICES[self.selected][0]

    def fragments(self, columns: int) -> StyleAndTextTuples:
        width = max(min(columns - 1, _MAX_WIDTH), 40)
        inner = width - 4
        rows: list[StyleAndTextTuples] = [self._title(inner)]
        rows.append([("class:perm.label", "Command")])
        for line in _wrap(self.decision.command, inner - 4):
            rows.append(_code_row(line, inner))
        detail = f"Needs {needs_phrase(self.decision.grants)}."
        for line in _wrap(detail, inner):
            rows.append([("class:perm.detail", line)])
        rows.append([])
        rows.append([("class:perm.question", "Allow this command?")])
        for index, (_, label) in enumerate(CHOICES):
            rows.append(self._option(index, label, inner))
        out: StyleAndTextTuples = []
        out += _edge("╭", "╮", width)
        out += _boxed(rows[0], inner)
        out += _edge("├", "┤", width)
        for row in rows[1:]:
            out += _boxed(row, inner)
        out += _boxed([], inner)
        out += _edge("├", "┤", width)
        footer = list(_FOOTER)
        if fragment_list_width(footer) > inner:
            footer = list(_SHORT_FOOTER)
        out += _boxed(footer, inner)
        out += _edge("╰", "╯", width, newline=False)
        return out

    def _title(self, inner: int) -> StyleAndTextTuples:
        left: StyleAndTextTuples = [("class:perm.title", "◆ Permission needed")]
        badge = " · ".join(badges(self.decision))
        if not badge:
            return left
        right: StyleAndTextTuples = [("class:perm.badge", f" {badge} ")]
        gap = inner - fragment_list_width(left) - fragment_list_width(right)
        if gap < 1:
            return left
        return [*left, ("", " " * gap), *right]

    def _option(self, index: int, label: str, inner: int) -> StyleAndTextTuples:
        number = f"[{index + 1}]"
        selected = index == self.selected
        marker = "▸ " if selected else "  "
        text = f"{marker}{label}"
        gap = max(inner - get_cwidth(text) - len(number), 1)
        if selected:
            return [("class:perm.selected", f"{text}{' ' * gap}{number}")]
        return [
            ("class:perm.option", text),
            ("", " " * gap),
            ("class:perm.number", number),
        ]


def permission_popup(decision: Decision) -> Application[str]:
    """Return once, repo, or no. Escape and ctrl+c are no."""
    popup = PermissionPopup(decision)
    keys = KeyBindings()

    @keys.add("up")
    @keys.add("k")
    @keys.add("s-tab")
    def _up(_event):
        popup.move(-1)

    @keys.add("down")
    @keys.add("j")
    @keys.add("tab")
    def _down(_event):
        popup.move(1)

    @keys.add("enter")
    def _confirm(event):
        event.app.exit(result=popup.choice())

    for index, (value, _) in enumerate(CHOICES):

        @keys.add(str(index + 1))
        def _pick(event, value: str = value):
            event.app.exit(result=value)

    @keys.add("escape", eager=True)
    @keys.add("c-c")
    @keys.add("n")
    def _cancel(event):
        event.app.exit(result="no")

    def _render() -> StyleAndTextTuples:
        return popup.fragments(get_app().output.get_size().columns)

    control = FormattedTextControl(_render, focusable=True, show_cursor=False)
    return Application(
        layout=Layout(Window(control, dont_extend_height=True)),
        key_bindings=keys,
        style=PERMISSION_STYLE,
        full_screen=False,
        erase_when_done=True,
    )


def _edge(
    left: str, right: str, width: int, newline: bool = True
) -> StyleAndTextTuples:
    end = "\n" if newline else ""
    return [("class:perm.border", f"{left}{'─' * (width - 2)}{right}{end}")]


def _boxed(row: StyleAndTextTuples, inner: int) -> StyleAndTextTuples:
    pad = max(inner - fragment_list_width(row), 0)
    return [
        ("class:perm.border", "│ "),
        *row,
        ("", " " * pad),
        ("class:perm.border", " │\n"),
    ]


def _code_row(line: str, inner: int) -> StyleAndTextTuples:
    body = f"{line} "
    pad = max(inner - 2 - get_cwidth(body), 0)
    return [
        ("class:perm.dollar", "$ "),
        ("class:perm.code", body + " " * pad),
    ]


def _wrap(text: str, width: int) -> list[str]:
    """Hard wrap on spaces. A word longer than the row is split."""
    width = max(width, 8)
    lines: list[str] = []
    current = ""
    for word in text.split(" "):
        while get_cwidth(word) > width:
            if current:
                lines.append(current)
                current = ""
            lines.append(word[:width])
            word = word[width:]
        candidate = f"{current} {word}" if current else word
        if get_cwidth(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current or not lines:
        lines.append(current)
    return lines
