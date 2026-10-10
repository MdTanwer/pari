"""Closed failure labels for a ProviderError."""

from enum import StrEnum
from typing import Final

from pari.providers.exceptions.types import ProviderError


class FailureKind(StrEnum):
    AUTHENTICATION = "Authentication"
    QUOTA = "Quota"
    RATE_LIMIT = "RateLimit"
    BAD_REQUEST = "BadRequest"
    TIMEOUT = "Timeout"
    SERVICE_UNAVAILABLE = "ServiceUnavailable"
    UNKNOWN = "ProviderError"


AUTH_PATTERNS: Final[tuple[str, ...]] = (
    "unauthorized",
    "invalid api key",
    "no_matching_rule",
    "access denied",
    "rejected_by_access_enforcement",
)

QUOTA_PATTERNS: Final[tuple[str, ...]] = ("insufficient_quota", "usage_limit")


def classify_error(exc: ProviderError) -> FailureKind:
    """Status code first. Provider wording only decides when the status cannot."""
    if exc.kind == "timeout" or exc.status_code == 408:
        return FailureKind.TIMEOUT
    if exc.kind == "network":
        return FailureKind.SERVICE_UNAVAILABLE
    if exc.status_code in (401, 403) or _has(exc, AUTH_PATTERNS):
        return FailureKind.AUTHENTICATION
    if exc.status_code == 402 or _has(exc, QUOTA_PATTERNS):
        return FailureKind.QUOTA
    if exc.status_code == 429 or _has(exc, ("rate limit",)):
        return FailureKind.RATE_LIMIT
    if _is_client_error(exc.status_code) or _has(exc, ("model not found",)):
        return FailureKind.BAD_REQUEST
    if exc.status_code is not None and exc.status_code >= 500:
        return FailureKind.SERVICE_UNAVAILABLE
    return FailureKind.UNKNOWN


def is_retryable_status(status_code: int) -> bool:
    """429 and 5xx can clear on their own. Other client errors will not."""
    return status_code == 429 or 500 <= status_code <= 599


def _is_client_error(status_code: int | None) -> bool:
    return status_code is not None and 400 <= status_code < 500


def _has(exc: ProviderError, needles: tuple[str, ...]) -> bool:
    text = f"{exc.detail}\n{exc.code}\n{exc.error_type}".casefold()
    return any(needle in text for needle in needles)
