"""How a provider failure is labelled for the user."""

import pytest

from pari.providers.exceptions import FailureKind, ProviderError, classify_error


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (401, FailureKind.AUTHENTICATION),
        (402, FailureKind.QUOTA),
        (404, FailureKind.BAD_REQUEST),
        (413, FailureKind.BAD_REQUEST),
        (422, FailureKind.BAD_REQUEST),
        (429, FailureKind.RATE_LIMIT),
        (503, FailureKind.SERVICE_UNAVAILABLE),
    ],
)
def test_status_decides_the_label(status: int, kind: FailureKind):
    assert classify_error(ProviderError("X", status_code=status)) is kind


def test_quota_wording_beats_the_429_status():
    error = ProviderError("X", status_code=429, code="insufficient_quota")
    assert classify_error(error) is FailureKind.QUOTA


def test_transport_failures_are_not_http_errors():
    assert classify_error(ProviderError("X", kind="timeout")) is FailureKind.TIMEOUT
    assert (
        classify_error(ProviderError("X", kind="network"))
        is FailureKind.SERVICE_UNAVAILABLE
    )
