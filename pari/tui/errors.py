"""Model failures, in the OpenHands conversation-error shape.

The code is a closed label. The detail is the provider's own text.
"""

from pari.providers.exceptions import ProviderError, classify_error


def model_error_text(exc: ProviderError) -> str:
    """Code plus the provider detail. The session stays up."""
    return f"Model error\nCode: {classify_error(exc)}\n\nDetail:\n{_detail(exc)}"


def _detail(exc: ProviderError) -> str:
    """Provider message, type, and code. Transport failures have no body."""
    lines: list[str] = []
    for part in (exc.detail, exc.error_type, exc.code):
        if part and part not in lines:
            lines.append(part)
    if lines:
        return "\n".join(lines)
    return str(exc)
