"""Saved sign-in credentials.

The file is the user's home auth store, not the workspace. Mode 0600 keeps the
token off other accounts on the machine.
"""

import json
import os
from pathlib import Path


def auth_path() -> Path:
    raw = os.environ.get("PARI_AUTH_FILE")
    if raw:
        return Path(raw)
    return Path.home() / ".pari" / "auth.json"


class AuthStore:
    def __init__(self, path: Path | None = None):
        self.path = path or auth_path()

    def load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Auth file is not valid JSON: {self.path}") from exc
        if not isinstance(data, dict):
            raise RuntimeError(f"Auth file is not valid JSON: {self.path}")
        return data

    def save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        payload = (json.dumps(data, indent=2) + "\n").encode()
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)
