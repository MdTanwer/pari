"""``pari-cli login`` screens: method, provider, then the sign-in itself."""

import base64
import ctypes
import os
import select
import sys
import time
import webbrowser


try:
    import msvcrt
except ImportError:
    msvcrt = None
try:
    import termios
    import tty
except ImportError:
    termios = None
    tty = None

from pari.auth.account import AccountUI, LoginCancelled, sign_in_account
from pari.auth.login import KeyVerifier, sign_in, sign_out, status_text
from pari.auth.menu import (
    API_KEY_TITLE,
    LOGOUT_TITLE,
    METHOD_ACCOUNT,
    METHOD_OPTIONS,
    ChoiceMenu,
    ProviderChoice,
    ProviderMenu,
    provider_rows,
    signed_in_rows,
)
from pari.auth.providers import ProviderInfo, get_info, no_account_message
from pari.auth.secret_field import SecretField
from pari.auth.store import AuthStore
from pari.auth.verify import verify_api_key


_ACCENT = "\033[38;2;255;121;198m"
_DIM = "\033[38;2;140;140;140m"
_WARN = "\033[38;2;230;180;80m"
_OK = "\033[38;2;80;200;120m"
_BOLD = "\033[1m"
_RESET = "\033[0m"
_PASTE_ON = "\033[?2004h"
_PASTE_OFF = "\033[?2004l"


def run_login(
    ui: AccountUI,
    store: AuthStore | None = None,
    provider_id: str | None = None,
    verify: KeyVerifier | None = None,
) -> str:
    """Walk the menus and return the success sentence. Empty means cancelled."""
    auth = store or AuthStore()
    title = "Select authentication method:"
    if provider_id:
        title = f"Select authentication method for {get_info(provider_id).label}:"
    while True:
        method = ui.choose(title, list(METHOD_OPTIONS))
        if not method:
            return ""
        kind = "account" if method == METHOD_ACCOUNT else "api_key"
        if provider_id:
            message = _finish(kind, provider_id, ui, auth, verify)
            if message is None:
                continue
            return message
        while True:
            chosen = ui.choose_provider(kind, provider_rows(kind, auth))
            if not chosen:
                break
            message = _finish(kind, chosen, ui, auth, verify)
            if message is None:
                continue
            return message


def run_logout(ui: AccountUI, store: AuthStore | None = None) -> str:
    """Pick a saved sign-in and remove it. Empty means the menu was cancelled."""
    auth = store or AuthStore()
    rows = signed_in_rows(auth)
    if not rows:
        return "No saved sign-in to remove."
    chosen = ui.choose_provider("logout", rows)
    if not chosen:
        return ""
    return sign_out(chosen, auth)


def logout_tty() -> int:
    """Open the logout picker. A pipe lists saved sign-ins and does not wait."""
    auth = AuthStore()
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        rows = signed_in_rows(auth)
        if rows:
            print("\n".join(f"{row.name}{row.status}" for row in rows))
        else:
            print("No saved sign-in to remove.")
        print("pari-cli logout <provider>")
        return 0
    ui = TerminalLogin()
    try:
        message = run_logout(ui, auth)
    except KeyboardInterrupt:
        return 0
    except (ValueError, RuntimeError) as exc:
        print(exc, file=sys.stderr)
        return 1
    finally:
        ui.close()
    if message:
        print(message)
    return 0


def login_tty(provider_id: str | None = None) -> int:
    """Open the menus on a terminal. A pipe prints status and does not wait."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print(status_text())
        return 0
    ui = TerminalLogin()
    try:
        message = run_login(ui, provider_id=provider_id, verify=verify_api_key)
    except KeyboardInterrupt:
        return 0
    except (ValueError, RuntimeError) as exc:
        print(exc, file=sys.stderr)
        return 1
    finally:
        ui.close()
    if message:
        print(message)
    return 0


def _finish(
    kind: str,
    provider_id: str,
    ui: AccountUI,
    store: AuthStore,
    verify: KeyVerifier | None,
) -> str | None:
    info = get_info(provider_id)
    try:
        if kind == "api_key":
            return _read_api_key(ui, info, store, verify)
        if not info.account:
            ui.show_error(no_account_message(info))
            return None
        return sign_in_account(info.id, ui, store)
    except LoginCancelled:
        return None


def _read_api_key(
    ui: AccountUI,
    info: ProviderInfo,
    store: AuthStore,
    verify: KeyVerifier | None,
) -> str:
    """Ask until the provider accepts the key, or the user cancels."""
    prompt = f"Enter your {info.label} API key:"
    while True:
        secret = ui.read_secret(prompt)
        if secret is None:
            raise LoginCancelled()
        try:
            return sign_in(info.id, secret, "api_key", store, verify=verify)
        except ValueError as exc:
            ui.show_error(str(exc))


class TerminalLogin:
    """Draw the picker in the alternate screen and restore it afterwards."""

    def __init__(self) -> None:
        self._alt = False
        self._raw = False
        self._fd = -1
        self._term: list | None = None
        self._pending = b""
        self._buffer = ""

    def close(self) -> None:
        self._leave()

    def choose(self, title: str, options: list[str]) -> str | None:
        return self._run(ChoiceMenu(title, options))

    def choose_provider(self, method: str, rows: list[ProviderChoice]) -> str | None:
        if method == "logout":
            return self._run(ProviderMenu(rows, search=True, title=LOGOUT_TITLE))
        search = method == "api_key"
        title = API_KEY_TITLE if search else ""
        return self._run(ProviderMenu(rows, search=search, title=title))

    def read_secret(self, prompt: str) -> str | None:
        """Read a key shown as ``x`` per character. None means cancelled."""
        self._leave()
        # The alternate screen restores the cursor onto the previous prompt.
        sys.stdout.write("\n" + _PASTE_ON)
        field = SecretField()
        try:
            self._enter_raw()
            while True:
                sys.stdout.write(f"\r\033[K{prompt} {field.masked}")
                sys.stdout.flush()
                result = field.on_key(self._key(None))
                if result == "cancel":
                    return None
                if result == "enter":
                    return field.value
        finally:
            sys.stdout.write(_PASTE_OFF + "\n")
            sys.stdout.flush()
            self._leave()

    def show_error(self, message: str) -> None:
        self._leave()
        print(message, file=sys.stderr)

    def read_line(self, prompt: str) -> str | None:
        self._leave()
        try:
            return input(prompt + " ")
        except (KeyboardInterrupt, EOFError):
            return None

    def show_auth_url(
        self,
        url: str,
        instructions: str,
        prompt: str,
        done,
    ) -> str | None:
        _open_browser(url)
        self._enter()
        self._buffer = ""
        try:
            while not done.is_set():
                self._draw(_auth_lines(url, instructions, prompt, self._buffer))
                key = self._key(0.2)
                if done.is_set():
                    return None
                if key == "cancel":
                    raise LoginCancelled()
                if key == "copy":
                    _copy_url(url)
                    continue
                if key == "enter":
                    text = self._buffer
                    self._buffer = ""
                    if text.strip():
                        return text
                    continue
                if key == "backspace":
                    self._buffer = self._buffer[:-1]
                elif len(key) == 1 and key.isprintable():
                    self._buffer += key
            return None
        finally:
            self._buffer = ""

    def show_device(self, url: str, user_code: str) -> None:
        _open_browser(url)
        self._enter()
        self._draw(
            [
                _link(url),
                _DIM + "Ctrl+click to open • ctrl+x to copy" + _RESET,
                "",
                f"Enter code: {user_code}",
                "",
                "Waiting for authentication...",
                _DIM + "(escape/ctrl+c to cancel)" + _RESET,
            ]
        )

    def sleep(self, seconds: float) -> bool:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            key = self._key(min(0.2, max(0, remaining)))
            if key == "cancel":
                return True
        return False

    def progress(self, message: str) -> None:
        self._enter()
        self._draw([_DIM + message + _RESET])

    def _run(self, menu: ChoiceMenu | ProviderMenu) -> str | None:
        self._enter()
        while True:
            self._draw([_paint(line) for line in menu.lines()])
            key = self._key(None)
            if not key:
                continue
            result = menu.on_key(key)
            if result == "cancel":
                return None
            if result:
                return result

    def _key(self, timeout: float | None) -> str:
        key, self._pending = read_menu_key(self._fd, self._pending, timeout)
        return key

    def _enter(self) -> None:
        if not self._alt:
            sys.stdout.write("\033[?1049h\033[?25l")
            sys.stdout.flush()
            self._alt = True
        self._enter_raw()

    def _enter_raw(self) -> None:
        if self._raw:
            return
        self._fd = sys.stdin.fileno()
        if termios is None or tty is None:
            _enable_windows_vt()
            self._raw = True
            return
        current = termios.tcgetattr(self._fd)
        self._term = _copy_mode(current)
        # cbreak, not raw: raw turns off newline output, so each row is drawn
        # from the end of the previous one and the arrow never lines up.
        mode = _copy_mode(self._term)
        mode[tty.LFLAG] &= ~(termios.ECHO | termios.ICANON | termios.ISIG)
        mode[tty.CC][termios.VMIN] = 1
        mode[tty.CC][termios.VTIME] = 0
        termios.tcsetattr(self._fd, termios.TCSADRAIN, mode)
        self._raw = True

    def _leave(self) -> None:
        if self._raw and self._term is not None:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._term)
            self._raw = False
            self._pending = b""
        if not self._alt:
            return
        sys.stdout.write("\033[?1049l\033[?25h")
        sys.stdout.flush()
        self._alt = False

    def _draw(self, lines: list[str]) -> None:
        frame = "\033[H\033[J" + "\n".join(lines) + "\n"
        sys.stdout.write(frame)
        sys.stdout.flush()


def _auth_lines(url: str, instructions: str, prompt: str, typed: str) -> list[str]:
    return [
        _link(url),
        _DIM + "Ctrl+click to open • ctrl+x to copy" + _RESET,
        "",
        instructions,
        "",
        prompt,
        "> " + typed,
    ]


def _paint(line: str) -> str:
    if line.startswith("Select ") or line.startswith("> "):
        if line.startswith("Select "):
            return _BOLD + _ACCENT + line + _RESET
        return line
    if line == "↑↓ navigate  enter select  escape/ctrl+c cancel":
        return _DIM + line + _RESET
    mark = _status_mark(line)
    if mark is None:
        if line.startswith("→ "):
            return _ACCENT + line + _RESET
        return line
    name, status = mark
    color = _OK if status.startswith(" ✓") else _DIM
    if "configured" in status and not status.startswith(" ✓"):
        color = _WARN
    if line.startswith("→ "):
        return _ACCENT + name + _RESET + color + status + _RESET
    return name + color + status + _RESET


def _status_mark(line: str) -> tuple[str, str] | None:
    for mark in (" • ", " ✓ "):
        index = line.find(mark)
        if index != -1:
            return line[:index], line[index:]
    return None


def _link(url: str) -> str:
    return f"\033]8;;{url}\033\\{_ACCENT}{url}{_RESET}\033]8;;\033\\"


def _copy_url(url: str) -> None:
    payload = base64.b64encode(url.encode()).decode()
    sys.stdout.write(f"\033]52;c;{payload}\a")
    sys.stdout.flush()


def _open_browser(url: str) -> None:
    try:
        webbrowser.open(url)
    except OSError:
        return


def _copy_mode(mode: list) -> list:
    return [list(item) if isinstance(item, list) else item for item in mode]


def read_menu_key(fd: int, pending: bytes, timeout: float | None) -> tuple[str, bytes]:
    """Read one key. Arrow keys stay one key; a bare Escape cancels.

    stdin's text buffer keeps the bytes after Escape, so a down arrow was
    seen as cancel. Read the terminal with ``os.read`` and hold the rest.
    """
    while True:
        if not pending:
            chunk = _read_chunk(fd, timeout)
            if not chunk:
                return "", pending
            pending = chunk
        sequence, pending = _split_sequence(pending)
        if sequence is None:
            more = _read_chunk(fd, 0.05)
            if not more:
                return _normalize(pending), b""
            pending += more
            continue
        key = _normalize(sequence)
        if key or not pending:
            return key, pending


_WIN_ARROWS = {
    "H": b"\x1b[A",
    "P": b"\x1b[B",
    "K": b"\x1b[D",
    "M": b"\x1b[C",
}


def _read_chunk(fd: int, timeout: float | None) -> bytes:
    if msvcrt is not None:
        return _read_windows(timeout)
    if timeout is not None:
        ready, _, _ = select.select([fd], [], [], timeout)
        if not ready:
            return b""
    try:
        return os.read(fd, 32)
    except OSError:
        return b""


def _read_windows(timeout: float | None) -> bytes:
    if timeout is not None and not _windows_ready(timeout):
        return b""
    char = msvcrt.getwch()
    if char in ("\x00", "\xe0"):
        return _WIN_ARROWS.get(msvcrt.getwch(), b"")
    return char.encode("utf-8")


def _windows_ready(timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while not msvcrt.kbhit():
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.01)
    return True


def _enable_windows_vt() -> None:
    if msvcrt is None:
        return
    kernel = ctypes.windll.kernel32
    handle = kernel.GetStdHandle(-11)
    mode = ctypes.c_uint()
    if not kernel.GetConsoleMode(handle, ctypes.byref(mode)):
        return
    kernel.SetConsoleMode(handle, mode.value | 0x0004)


def _split_sequence(buf: bytes) -> tuple[bytes | None, bytes]:
    """Split one key from ``buf``. None means an unfinished Escape sequence."""
    if not buf:
        return b"", b""
    if buf[0] != 0x1B:
        size = _utf8_len(buf[0])
        if len(buf) < size:
            return None, buf
        return buf[:size], buf[size:]
    if len(buf) == 1:
        return None, buf
    if buf[1] == ord("["):
        for index in range(2, len(buf)):
            if 0x40 <= buf[index] <= 0x7E:
                return buf[: index + 1], buf[index + 1 :]
        return None, buf
    if buf[1] == ord("O"):
        if len(buf) < 3:
            return None, buf
        return buf[:3], buf[3:]
    return buf[:2], buf[2:]


def _utf8_len(first: int) -> int:
    if first < 0x80:
        return 1
    if first < 0xE0:
        return 2
    if first < 0xF0:
        return 3
    return 4


def _normalize(raw: bytes) -> str:
    if raw in (b"\r", b"\n"):
        return "enter"
    if raw in (b"\x7f", b"\x08"):
        return "backspace"
    if raw == b"\x03":
        return "cancel"
    if raw == b"\x18":
        return "copy"
    if raw == b"\x1b[200~":
        return "paste_start"
    if raw == b"\x1b[201~":
        return "paste_end"
    if raw == b"\x1b":
        return "cancel"
    if raw.startswith(b"\x1b[") or (raw.startswith(b"\x1bO") and len(raw) >= 3):
        final = raw[-1:]
        if final == b"A":
            return "up"
        if final == b"B":
            return "down"
        return ""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return ""
    if len(text) == 1 and text.isprintable():
        return text
    return ""
