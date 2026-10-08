"""Constants and checks the execution loop applies before it runs a tool.

The loop itself decides when to stop. These values are the limits it checks.
"""

MAX_TURNS = 40
TURN_WARNING = 30
DAEMON_IDLE_SECONDS = 10

# Shown when stop_reason is "length". The loop must drop the pending tool
# calls before it appends this notice. A truncated edit must not touch disk.
LENGTH_TRUNCATION_NOTICE = (
    "WARNING: Your previous tool call was truncated due to the "
    "output token ceiling. No changes were written to disk. "
    "Please break your modification into smaller, focused "
    "search/replace blocks of <= 100 lines."
)


def is_length_stop(stop_reason: str | None) -> bool:
    """True when the model hit max_tokens and the tool payload may be cut off."""
    return stop_reason == "length"


def format_daemon_notice(command: str, idle_seconds: int = DAEMON_IDLE_SECONDS) -> str:
    """Notice for a command that kept streaming past the idle window."""
    shown = command.strip() or "command"
    return (
        f"[DAEMON DETECTED]: Command '{shown}' did not exit after "
        f"{idle_seconds}s. Process was backgrounded. "
        "Stdout snapshot spooled to disk. "
        "To manage background daemons, use background task APIs."
    )
