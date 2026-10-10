"""Validated input for ``sign_in``."""

import re
from typing import Literal

from pydantic import BaseModel, ValidationError, field_validator, model_validator

from pari.auth.providers import PROVIDERS, ProviderInfo, get_info, no_account_message


_KEY_CHARS = re.compile(r"[A-Za-z0-9_-]+")
_MIN_API_KEY = 20
MAX_API_KEY_LENGTH = 256


class SignInInput(BaseModel):
    """One sign-in request. Fields are checked in declaration order."""

    method: Literal["api_key", "account"]
    provider_id: str
    secret: str
    refresh: str | None = None
    client_id: str | None = None
    expires: int | None = None

    @property
    def info(self) -> ProviderInfo:
        return get_info(self.provider_id)

    @field_validator("method", mode="before")
    @classmethod
    def _method(cls, value: object) -> object:
        if value not in ("api_key", "account"):
            raise ValueError("Sign in with an API key or an account token.")
        return value

    @field_validator("provider_id")
    @classmethod
    def _provider(cls, value: str) -> str:
        return get_info(value).id

    @field_validator("secret")
    @classmethod
    def _secret(cls, value: str) -> str:
        token = value.strip()
        if not token:
            raise ValueError("The credential is empty.")
        return token

    @field_validator("refresh", "client_id", mode="before")
    @classmethod
    def _optional_text(cls, value: object) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    @field_validator("expires", mode="before")
    @classmethod
    def _optional_int(cls, value: object) -> int | None:
        return value if isinstance(value, int) else None

    @model_validator(mode="after")
    def _check_credential(self) -> "SignInInput":
        if self.method == "account" and not self.info.account:
            raise ValueError(no_account_message(self.info))
        if self.method == "api_key":
            _check_api_key(self.info, self.secret)
        return self


def parse_sign_in(
    provider_id: str,
    secret: str,
    method: str,
    extra: dict | None = None,
) -> SignInInput:
    """Validate the input. Raises ``ValueError`` with a message to show as is."""
    extra = extra or {}
    try:
        return SignInInput.model_validate(
            {
                "method": method,
                "provider_id": provider_id,
                "secret": secret,
                "refresh": extra.get("refresh"),
                "client_id": extra.get("client_id"),
                "expires": extra.get("expires"),
            }
        )
    except ValidationError as exc:
        raise ValueError(_message(exc)) from None


def _message(exc: ValidationError) -> str:
    """The first error as a sentence. Rule failures carry their own text."""
    error = exc.errors()[0]
    if error["type"] == "value_error":
        return str(error["ctx"]["error"])
    return f"{error['loc'][0]}: {error['msg']}"


def _check_api_key(info: ProviderInfo, token: str) -> None:
    if any(char.isspace() for char in token):
        raise ValueError(f"{info.label} API keys cannot contain spaces.")
    _check_prefix(info, token)
    if not _KEY_CHARS.fullmatch(token):
        raise ValueError(
            f"That {info.label} API key uses characters that are not allowed."
        )
    if len(token) < _MIN_API_KEY:
        raise ValueError(f"That {info.label} API key is too short.")
    if len(token) > MAX_API_KEY_LENGTH:
        raise ValueError(f"That {info.label} API key is too long.")


def _check_prefix(info: ProviderInfo, token: str) -> None:
    """The most specific prefix wins, so ``sk-ant-`` is Anthropic and not OpenAI."""
    matches = [item for item in PROVIDERS if token.startswith(item.key_prefix)]
    if not matches:
        raise ValueError(f"{info.label} API keys start with {info.key_prefix}.")
    longest = max(len(item.key_prefix) for item in matches)
    owners = [item for item in matches if len(item.key_prefix) == longest]
    if info not in owners:
        names = " or ".join(item.label for item in owners)
        raise ValueError(
            f"That key belongs to {names}. "
            f"{info.label} keys start with {info.key_prefix}."
        )
