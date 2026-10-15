"""Full-screen view of one turn's activity.

It runs on the alternate screen, so closing it leaves the scrollback and the
prompt exactly as they were.
"""

from prompt_toolkit.application import Application
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import TextArea

from pari.tui.style import CLI_STYLE


_FOOTER = " ctrl+o to collapse · ↑/↓ PgUp/PgDn to scroll · q to close"


def transcript_viewer(text: str) -> Application:
    """Open at the end, where the latest step is."""
    area = TextArea(read_only=True, scrollbar=True, wrap_lines=True)
    area.buffer.set_document(
        Document(text, cursor_position=len(text)), bypass_readonly=True
    )
    footer = Window(
        FormattedTextControl([("class:bottom-toolbar.text", _FOOTER)]),
        height=1,
    )
    keys = KeyBindings()

    @keys.add("c-o")
    @keys.add("q")
    @keys.add("escape", eager=True)
    def _close(event):
        event.app.exit()

    return Application(
        layout=Layout(HSplit([area, footer]), focused_element=area),
        key_bindings=keys,
        style=CLI_STYLE,
        full_screen=True,
        mouse_support=True,
    )
