"""Constants and checks the execution loop applies before it runs a tool.

The loop itself decides when to stop. These values are the limits it checks.
"""

MAX_TURNS = 40
TURN_WARNING = 30
TURN_EXTENSION = 10
DAEMON_IDLE_SECONDS = 10
TURN_LIMIT_PROMPT = "[Turn limit reached. Continue (+10 turns) | Revert | Stop]?"

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
    """Notice for a command killed because it did not exit."""
    shown = command.strip() or "command"
    return (
        f"[DAEMON DETECTED]: Command '{shown}' was stopped after "
        f"{idle_seconds}s. Run long-lived servers in a separate terminal."
    )
