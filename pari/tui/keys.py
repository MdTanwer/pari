"""Keys for the slash-command menu and the turn-limit menu.

Each binding is filtered with ``has_completions``, so Enter still submits the
line when the menu is closed.
"""

from collections.abc import Callable

from prompt_toolkit.filters import Condition, has_completions
from prompt_toolkit.key_binding import KeyBindings


# The prompt returns this when ctrl+o asks for the transcript. No one types NUL.
EXPAND = "\x00expand"


def create_key_bindings(
    can_expand: Callable[[], bool] | None = None,
) -> KeyBindings:
    kb = KeyBindings()

    if can_expand is not None:

        @kb.add("c-o", filter=Condition(can_expand) & ~has_completions, eager=True)
        def _expand(event):
            # The viewer runs after the prompt exits. Inside the prompt the tty
            # drops to cooked mode, where ctrl+o is the discard-output key.
            event.app.erase_when_done = True
            event.app.exit(result=EXPAND)

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


def create_limit_key_bindings() -> KeyBindings:
    """Arrow keys move. Enter inserts the highlighted choice and submits it."""
    kb = create_key_bindings()

    @kb.add("enter", filter=has_completions, eager=True)
    def _accept_choice(event):
        buff = event.current_buffer
        if buff.complete_state and buff.complete_state.current_completion:
            buff.apply_completion(buff.complete_state.current_completion)
        buff.validate_and_handle()

    return kb
