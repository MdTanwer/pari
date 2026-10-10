"""Model failures, in the OpenHands conversation-error shape.

The code is a closed label. The detail is the provider's own text.
"""

from pari.providers.errors import ProviderError


def model_error_text(exc: ProviderError) -> str:
    """Code plus the provider detail. The session stays up."""
    return f"Model error\nCode: {_display_code(exc)}\n\nDetail:\n{_detail(exc)}"


def _display_code(exc: ProviderError) -> str:
    """One label. Provider wording cannot change it once the status is known."""
    if exc.kind == "timeout" or exc.status_code == 408:
        return "Timeout"
    if exc.kind == "network":
        return "ServiceUnavailable"
    if exc.status_code in (401, 403) or _auth_text(exc):
        return "Authentication"
    if exc.code == "insufficient_quota" or _has(
        exc, "insufficient_quota", "usage_limit"
    ):
        return "Quota"
    if exc.status_code == 429 or _has(exc, "rate limit"):
        return "RateLimit"
    if exc.status_code in (400, 404) or _has(exc, "model not found"):
        return "BadRequest"
    if exc.status_code is not None and exc.status_code >= 500:
        return "ServiceUnavailable"
    return "ProviderError"


def _detail(exc: ProviderError) -> str:
    """Provider message, type, and code. Transport failures have no body."""
    lines: list[str] = []
    if exc.detail:
        lines.append(exc.detail)
    if exc.error_type and exc.error_type not in lines:
        lines.append(exc.error_type)
    if exc.code and exc.code not in lines:
        lines.append(exc.code)
    if lines:
        return "\n".join(lines)
    if exc.kind == "timeout":
        return f"{exc.provider} did not respond in time."
    if exc.kind == "network":
        return f"Could not reach {exc.provider}."
    if exc.status_code is None:
        return f"{exc.provider} request failed."
    return f"{exc.provider} request failed ({exc.status_code})."


def _auth_text(exc: ProviderError) -> bool:
    return _has(
        exc,
        "unauthorized",
        "invalid api key",
        "no_matching_rule",
        "access denied",
        "rejected_by_access_enforcement",
    )


def _has(exc: ProviderError, *needles: str) -> bool:
    text = f"{exc.detail}\n{exc.code}\n{exc.error_type}".casefold()
    return any(needle in text for needle in needles)
