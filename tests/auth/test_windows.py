"""The login screen starts on Windows, where termios does not exist."""

import sys

from pari.auth.interactive import TerminalLogin, read_menu_key
from pari.auth.menu import METHOD_ACCOUNT, METHOD_API_KEY


class _Console:
    def __init__(self, keys, ready=True):
        self._keys = list(keys)
        self._ready = ready

    def kbhit(self):
        return self._ready and bool(self._keys)

    def getwch(self):
        return self._keys.pop(0)


def test_windows_down_arrow_is_down_not_cancel(monkeypatch):
    monkeypatch.setattr(
        "pari.auth.interactive.msvcrt",
        _Console(["\xe0", "P"]),
    )
    key, rest = read_menu_key(0, b"", None)
    assert key == "down"
    assert rest == b""


def test_windows_wait_returns_without_a_key(monkeypatch):
    monkeypatch.setattr(
        "pari.auth.interactive.msvcrt",
        _Console([], ready=False),
    )
    key, rest = read_menu_key(0, b"", 0.01)
    assert key == ""
    assert rest == b""


def test_login_menu_opens_without_termios(monkeypatch):
    monkeypatch.setattr("pari.auth.interactive.termios", None)
    monkeypatch.setattr("pari.auth.interactive.tty", None)
    monkeypatch.setattr(sys.stdin, "fileno", lambda: 0)
    monkeypatch.setattr("pari.auth.interactive._enable_windows_vt", lambda: None)
    monkeypatch.setattr(
        "pari.auth.interactive.msvcrt",
        _Console(["\xe0", "P", "\r"]),
    )
    chosen = TerminalLogin().choose(
        "Select authentication method:",
        [METHOD_ACCOUNT, METHOD_API_KEY],
    )
    assert chosen == METHOD_API_KEY
