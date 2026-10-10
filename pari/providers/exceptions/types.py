from typing import Literal


FailureTransport = Literal["http", "timeout", "network"]


class ProviderError(RuntimeError):
    """The model API refused the call or could not be reached.

    ``detail`` is a short phrase from the provider. The response body stays
    off the message so a traceback cannot dump it into the terminal.
    """

    def __init__(
        self,
        provider: str,
        *,
        status_code: int | None = None,
        code: str = "",
        detail: str = "",
        error_type: str = "",
        kind: FailureTransport = "http",
    ):
        self.provider = provider
        self.status_code = status_code
        self.code = code
        self.detail = detail
        self.error_type = error_type
        self.kind = kind
        super().__init__(detail or _summary(provider, status_code, kind))


def _summary(provider: str, status_code: int | None, kind: FailureTransport) -> str:
    if kind == "timeout":
        return f"{provider} did not respond in time."
    if kind == "network":
        return f"Could not reach {provider}."
    if status_code is None:
        return f"{provider} request failed."
    return f"{provider} request failed ({status_code})."
