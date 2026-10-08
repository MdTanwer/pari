"""Keys for the slash-command menu.

Each binding is filtered with ``has_completions``, so Enter still submits the
line when the menu is closed.
"""

from prompt_toolkit.filters import has_completions
from prompt_toolkit.key_binding import KeyBindings


def create_key_bindings() -> KeyBindings:
    kb = KeyBindings()

    @kb.add("enter", filter=has_completions)
    def _handle_enter(event):
        buff = event.current_buffer
        if buff.complete_state and buff.complete_state.current_completion:
            buff.apply_completion(buff.complete_state.current_completion)
        else:
            buff.validate_and_handle()

    @kb.add("tab", filter=has_completions)
    def _handle_tab(event):
        buff = event.current_buffer
        if buff.complete_state:
            buff.complete_next()

    @kb.add("s-tab", filter=has_completions)
    def _handle_s_tab(event):
        buff = event.current_buffer
        if buff.complete_state:
            buff.complete_previous()

    @kb.add("down", filter=has_completions)
    def _handle_down(event):
        event.current_buffer.complete_next()

    @kb.add("up", filter=has_completions)
    def _handle_up(event):
        event.current_buffer.complete_previous()

    @kb.add("escape", filter=has_completions)
    def _handle_escape(event):
        event.current_buffer.cancel_completion()

    return kb
