"""The masked key prompt shows one x per character and takes one paste."""

import pytest

from pari.auth.credential import MAX_API_KEY_LENGTH
from pari.auth.interactive import read_menu_key
from pari.auth.login import sign_in
from pari.auth.secret_field import SecretField
from pari.auth.store import AuthStore


KEY = "sk-0123456789abcdefxyz"


def _feed(field: SecretField, keys: list[str]) -> str | None:
    result = None
    for key in keys:
        result = field.on_key(key)
    return result


def _paste(text: str) -> list[str]:
    return ["paste_start", *text, "paste_end"]


def test_typed_characters_are_shown_as_x_and_returned_on_enter():
    field = SecretField()
    assert _feed(field, [*"sk-abc", "backspace", "enter"]) == "enter"
    assert field.masked == "xxxxx"
    assert field.value == "sk-ab"


def test_pasting_twice_leaves_one_key():
    field = SecretField()
    _feed(field, _paste(KEY))
    _feed(field, _paste(KEY))
    assert field.value == KEY
    assert field.masked == "x" * len(KEY)


def test_typing_after_a_paste_is_ignored_until_the_paste_is_edited():
    field = SecretField()
    _feed(field, _paste(KEY))
    _feed(field, [*"more"])
    assert field.value == KEY
    _feed(field, ["backspace", "backspace", *"zz"])
    assert field.value == KEY[:-2]


def test_a_newline_inside_a_paste_does_not_submit_the_key():
    field = SecretField()
    assert _feed(field, ["paste_start", *"sk-ab", "enter", *"cd"]) is None
    assert _feed(field, ["paste_end"]) is None
    assert field.value == "sk-abcd"
    assert field.on_key("enter") == "enter"


def test_enter_on_an_empty_field_waits_and_escape_cancels():
    field = SecretField()
    assert field.on_key("enter") is None
    assert field.on_key("cancel") == "cancel"


def test_input_stops_at_the_length_limit():
    field = SecretField()
    _feed(field, _paste("a" * (MAX_API_KEY_LENGTH + 50)))
    assert len(field.value) == MAX_API_KEY_LENGTH
    _feed(field, [*"b" * 10])
    assert len(field.value) == MAX_API_KEY_LENGTH


def test_terminal_paste_markers_become_paste_keys():
    key, rest = read_menu_key(-1, b"\x1b[200~", None)
    assert (key, rest) == ("paste_start", b"")
    key, rest = read_menu_key(-1, b"\x1b[201~", None)
    assert (key, rest) == ("paste_end", b"")


def test_a_key_over_the_length_limit_is_not_saved(tmp_path):
    store = AuthStore(tmp_path / "auth.json")
    with pytest.raises(ValueError, match="too long"):
        sign_in("deepseek", "sk-" + "a" * MAX_API_KEY_LENGTH, "api_key", store)
    assert store.load() == {}
