"""The state behind the masked API key prompt.

A terminal that supports bracketed paste marks where a paste starts and ends.
A paste replaces what was typed or pasted before it, so pasting the key twice
leaves one key. Once a paste is in, typing is ignored; backspace edits it and
a new paste replaces it. A terminal without bracketed paste sends a paste as
typed keys, so only the length limit applies.
"""

from pari.auth.credential import MAX_API_KEY_LENGTH


MASK = "x"


class SecretField:
    def __init__(self, limit: int = MAX_API_KEY_LENGTH) -> None:
        self._limit = limit
        self._text = ""
        self._pasting = False
        self._locked = False

    @property
    def value(self) -> str:
        return self._text

    @property
    def masked(self) -> str:
        return MASK * len(self._text)

    def on_key(self, key: str) -> str | None:
        """Apply one key. Returns ``enter`` or ``cancel`` when the prompt ends."""
        if key == "cancel":
            return "cancel"
        if key == "paste_start":
            self._text = ""
            self._pasting = True
        elif key == "paste_end":
            self._pasting = False
            self._locked = bool(self._text)
        elif key == "backspace":
            self._text = self._text[:-1]
            self._locked = self._locked and bool(self._text)
        elif key == "enter":
            if self._text and not self._pasting:
                return "enter"
        elif len(key) == 1 and (self._pasting or not self._locked):
            if len(self._text) < self._limit:
                self._text += key
        return None
