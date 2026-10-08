"""Prompt and completion-menu colors for the REPL."""

from prompt_toolkit.styles import Style


CLI_STYLE = Style.from_dict(
    {
        "prompt": "fg:#38bdf8 bold",
        "": "fg:#f3f4f6",
        "placeholder": "fg:#6b7280 italic",
        "completion-menu": "bg:#18181b fg:#f4f4f5",
        "completion-menu.completion": "bg:#18181b fg:#38bdf8",
        "completion-menu.completion.current": "bg:#27272a fg:#38bdf8 bold",
        "completion-menu.meta.completion": "bg:#18181b fg:#717882",
        "completion-menu.meta.completion.current": "bg:#27272a fg:#e4e4e7",
        "completion-menu.multi-column-meta": "bg:#18181b fg:#717882",
        "scrollbar.background": "bg:#18181b",
        "scrollbar.button": "bg:#3f3f46",
        "scrollbar.arrow": "bg:#18181b fg:#717882",
        "bottom-toolbar": "bg:default fg:#717882",
        "bottom-toolbar.text": "bg:default fg:#717882",
        "toolbar-key": "fg:#38bdf8 bold",
        "toolbar-key-esc": "fg:#717882",
        "toolbar-action": "fg:#717882",
        "toolbar-dot": "fg:#4b5563",
    }
)
