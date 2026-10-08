"""Keyboard menus for ``pari login``.

The first screen picks an account or an API key. The next screen picks a
provider. Radius is not a choice.
"""

from dataclasses import dataclass

from pari.auth.providers import PROVIDERS, ProviderInfo
from pari.auth.store import AuthStore


METHOD_ACCOUNT = "Sign in with an account"
METHOD_API_KEY = "Sign in with an API key"
METHOD_OPTIONS = (METHOD_ACCOUNT, METHOD_API_KEY)
API_KEY_TITLE = "Select provider to configure:"
LOGOUT_TITLE = "Select provider to logout:"
NAV_HINT = "↑↓ navigate  enter select  escape/ctrl+c cancel"
_MAX_VISIBLE = 8


@dataclass(frozen=True)
class ProviderChoice:
    id: str
    name: str
    status: str


def provider_rows(method: str, store: AuthStore | None = None) -> list[ProviderChoice]:
    """Providers in name order, each with a status that does not include the secret."""
    data = (store or AuthStore()).load()
    infos = sorted(PROVIDERS, key=lambda item: item.label.lower())
    return [
        ProviderChoice(info.id, info.label, _status(info, method, data))
        for info in infos
    ]


def signed_in_rows(store: AuthStore | None = None) -> list[ProviderChoice]:
    """Saved sign-ins only. Environment keys are left in place."""
    data = (store or AuthStore()).load()
    infos = sorted(PROVIDERS, key=lambda item: item.label.lower())
    rows: list[ProviderChoice] = []
    for info in infos:
        row = data.get(info.id)
        if not isinstance(row, dict) or not str(row.get("secret") or "").strip():
            continue
        kind = "account" if row.get("method") == "account" else "API key"
        rows.append(ProviderChoice(info.id, info.label, f" • {kind}"))
    return rows


def _status(info: ProviderInfo, viewing: str, data: dict) -> str:
    row = data.get(info.id)
    stored = ""
    if isinstance(row, dict) and str(row.get("secret") or "").strip():
        stored = "account" if row.get("method") == "account" else "api_key"
    if stored == viewing:
        return " ✓ configured"
    if stored == "api_key":
        return " • API key configured"
    if stored == "account":
        return " • account configured"
    return " • not configured"


class ChoiceMenu:
    """A short list. ``j`` and ``k`` move, like the method screen."""

    def __init__(self, title: str, options: list[str]):
        self.title = title
        self.options = options
        self.selected = 0

    def lines(self) -> list[str]:
        rows = [self.title, ""]
        for index, option in enumerate(self.options):
            prefix = "→ " if index == self.selected else "  "
            rows.append(prefix + option)
        rows.extend(["", NAV_HINT])
        return rows

    def on_key(self, key: str) -> str | None:
        """Return the chosen option, ``cancel``, or None to keep the menu open."""
        count = len(self.options)
        if key in ("up", "k"):
            self.selected = max(0, self.selected - 1)
            return None
        if key in ("down", "j"):
            self.selected = min(count - 1, self.selected + 1) if count else 0
            return None
        if key == "cancel":
            return "cancel"
        if key == "enter" and count:
            return self.options[self.selected]
        return None


class ProviderMenu:
    """Provider list. An API-key login also has the search line from the picker."""

    def __init__(self, rows: list[ProviderChoice], *, search: bool, title: str = ""):
        self.rows = rows
        self.search = search
        self.title = title
        self.query = ""
        self.selected = 0

    def visible(self) -> list[ProviderChoice]:
        query = self.query.casefold()
        if not query:
            return list(self.rows)
        return [
            row
            for row in self.rows
            if query in row.name.casefold() or query in row.id.casefold()
        ]

    def lines(self) -> list[str]:
        shown = self.visible()
        self.selected = max(0, min(self.selected, len(shown) - 1)) if shown else 0
        rows: list[str] = []
        if self.title:
            rows.extend([self.title, ""])
        if self.search:
            rows.extend([f"> {self.query}", ""])
        if not shown:
            rows.append("  No matching providers")
        else:
            start, end = _window(self.selected, len(shown))
            for index in range(start, end):
                row = shown[index]
                prefix = "→ " if index == self.selected else "  "
                rows.append(f"{prefix}{row.name}{row.status}")
            if len(shown) > _MAX_VISIBLE:
                rows.append(f"  ({self.selected + 1}/{len(shown)})")
        rows.extend(["", NAV_HINT])
        return rows

    def on_key(self, key: str) -> str | None:
        """Return a provider id, ``cancel``, or None."""
        shown = self.visible()
        if key == "up" or (key == "k" and not self.search):
            self.selected = max(0, self.selected - 1)
            return None
        if key == "down" or (key == "j" and not self.search):
            if shown:
                self.selected = min(len(shown) - 1, self.selected + 1)
            return None
        if key == "cancel":
            return "cancel"
        if key == "enter":
            if not shown:
                return None
            return shown[self.selected].id
        if not self.search:
            return None
        if key == "backspace":
            self.query = self.query[:-1]
            self.selected = 0
            return None
        if len(key) == 1 and key.isprintable():
            self.query += key
            self.selected = 0
            return None
        return None


def _window(selected: int, count: int) -> tuple[int, int]:
    if count <= _MAX_VISIBLE:
        return 0, count
    start = max(0, min(selected - _MAX_VISIBLE // 2, count - _MAX_VISIBLE))
    return start, start + _MAX_VISIBLE
