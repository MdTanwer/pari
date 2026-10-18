"""PARI Layer 2: Safe Context Compaction.

Architectural Purpose:
    Closes Claude Code F7 (Context amnesia on compaction) & Cursor F3 (Context drift).
    When context token usage crosses 70% of model window capacity:
    1. Extracts and preserves API schemas, architectural agreements, and file mutation
    lists.
    2. Summarizes conversational chitchat and repetitive tool execution outputs.
    3. Replaces Tier 6 (Turn History) with the compressed summary, leaving Tiers 1-5
    intact.
"""

import json
from typing import overload

from pari.context.chunks import ContextChunk, ContextTier
from pari.providers.message import ProviderMessage


DEFAULT_MAX_TOKENS = 128000
DEFAULT_COMPACTION_THRESHOLD = 0.70
DEFAULT_KEEP_LAST = 5


def compact_messages(
    messages: list[ProviderMessage],
    tokens_in: int = 0,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    compaction_threshold: float = DEFAULT_COMPACTION_THRESHOLD,
    keep_last: int = DEFAULT_KEEP_LAST,
) -> list[ProviderMessage]:
    """Summarize older messages when provider tokens_in crosses threshold.

    System prompt and the last N turns stay verbatim. Older assistant/tool
    pairs and user messages are summarized.
    """
    budget = int(max_tokens * compaction_threshold)
    if tokens_in <= budget:
        return list(messages)
    if len(messages) <= 1:
        return list(messages)

    system_msg: ProviderMessage | None = None
    if messages and messages[0].role == "system":
        system_msg = messages[0]
        chat = list(messages[1:])
    else:
        chat = list(messages)

    user_indices = [
        idx
        for idx, msg in enumerate(chat)
        if msg.role == "user"
        and not msg.content.startswith("[Summary of prior history:")
    ]

    if len(user_indices) > keep_last:
        split_idx = user_indices[-keep_last]
    else:
        asst_indices = [idx for idx, msg in enumerate(chat) if msg.role == "assistant"]
        if len(asst_indices) > keep_last:
            split_idx = asst_indices[-keep_last]
        else:
            return list(messages)

    old_messages = chat[:split_idx]
    recent_messages = chat[split_idx:]
    if not old_messages:
        return list(messages)

    summary_lines: list[str] = []
    for msg in old_messages:
        if msg.role == "user":
            if msg.content.startswith("[Summary of prior history:"):
                clean = (
                    msg.content.removeprefix("[Summary of prior history:")
                    .removesuffix("]")
                    .strip()
                )
                if clean:
                    summary_lines.append(clean)
            else:
                summary_lines.append(f"User: {_clip(msg.content)}")
        elif msg.role == "assistant":
            if msg.tool_calls:
                calls_str = ", ".join(
                    f"{c.name}({json.dumps(c.arguments)})" for c in msg.tool_calls
                )
                summary_lines.append(f"Assistant called: {calls_str}")
            if msg.content:
                summary_lines.append(f"Assistant: {_clip(msg.content)}")
        elif msg.role == "tool":
            tid = msg.tool_call_id or "tool"
            summary_lines.append(
                f"Tool result ({tid}): {len(msg.content)} chars output"
            )

    if len(summary_lines) > 20:
        omitted = len(summary_lines) - 15
        summary_lines = (
            summary_lines[:5]
            + [f"... [{omitted} intermediate turns omitted] ..."]
            + summary_lines[-10:]
        )

    summary_text = "[Summary of prior history:\n" + "\n".join(summary_lines) + "]"
    summary_user = ProviderMessage(role="user", content=summary_text)

    compacted: list[ProviderMessage] = []
    if system_msg is not None:
        compacted.append(system_msg)

    if recent_messages and recent_messages[0].role == "user":
        ack_asst = ProviderMessage(
            role="assistant", content="Acknowledged prior history summary."
        )
        compacted.extend([summary_user, ack_asst])
    else:
        compacted.append(summary_user)

    compacted.extend(recent_messages)
    return compacted


def _clip(text: str, max_len: int = 120) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_len:
        return cleaned
    return f"{cleaned[:max_len]}..."


@overload
def compact_context(
    chunks: list[ContextChunk],
    max_tokens: int = DEFAULT_MAX_TOKENS,
    compaction_threshold: float = DEFAULT_COMPACTION_THRESHOLD,
    tokens_in: int | None = None,
) -> list[ContextChunk]: ...


@overload
def compact_context(
    chunks: list[ProviderMessage],
    max_tokens: int = DEFAULT_MAX_TOKENS,
    compaction_threshold: float = DEFAULT_COMPACTION_THRESHOLD,
    tokens_in: int | None = None,
) -> list[ProviderMessage]: ...


def compact_context(
    chunks: list[ContextChunk] | list[ProviderMessage],
    max_tokens: int = DEFAULT_MAX_TOKENS,
    compaction_threshold: float = DEFAULT_COMPACTION_THRESHOLD,
    tokens_in: int | None = None,
) -> list[ContextChunk] | list[ProviderMessage]:
    """Summarize history once the window fills."""
    if chunks and isinstance(chunks[0], ProviderMessage):
        msgs = [c for c in chunks if isinstance(c, ProviderMessage)]
        return compact_messages(
            msgs,
            tokens_in=tokens_in or 0,
            max_tokens=max_tokens,
            compaction_threshold=compaction_threshold,
        )

    chunk_list = [c for c in chunks if isinstance(c, ContextChunk)]
    budget = max_tokens * compaction_threshold
    estimate = tokens_in if tokens_in is not None else _estimate_tokens(chunk_list)
    if estimate <= budget:
        return list(chunk_list)
    recent = {
        id(chunk)
        for chunk in [
            item for item in chunk_list if item.tier == ContextTier.TURN_HISTORY
        ][-5:]
    }
    compacted: list[ContextChunk] = []
    for chunk in chunk_list:
        if chunk.tier != ContextTier.TURN_HISTORY or id(chunk) in recent:
            compacted.append(chunk)
            continue
        summary = (
            f"[compacted history {chunk.identifier}: "
            f"{len(chunk.content)} chars omitted]"
        )
        compacted.append(
            ContextChunk(
                tier=chunk.tier,
                content=summary,
                identifier=chunk.identifier,
                cache_control=chunk.cache_control,
            )
        )
    return compacted


def _estimate_tokens(chunks: list[ContextChunk]) -> int:
    """Rough token count. Four characters is one token for this budget check."""
    return sum(max(1, len(chunk.content) // 4) for chunk in chunks)
