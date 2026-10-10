"""Saved sign-in credentials.

The file is the user's home auth store, not the workspace. Mode 0600 keeps the
token off other accounts on the machine.
"""

import json
import os
import tempfile
from pathlib import Path


def auth_path() -> Path:
    raw = os.environ.get("PARI_AUTH_FILE")
    if raw:
        return Path(raw)
    return Path.home() / ".pari" / "auth.json"


class AuthStore:
    def __init__(self, path: Path | None = None):
        if path is None:
            path = auth_path()
        self.path = path

    def load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            data = None
        if not isinstance(data, dict):
            raise RuntimeError(f"Auth file is not valid JSON: {self.path}")
        return data

    def save(self, data: dict) -> None:
        """Replace the file in one step so a crash cannot leave a half-written one."""
        self.path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        payload = json.dumps(data, indent=2) + "\n"
        # mkstemp creates the file with mode 0600 in the same directory.
        fd, temp = tempfile.mkstemp(dir=self.path.parent, prefix=".auth-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, self.path)
        except BaseException:
            Path(temp).unlink(missing_ok=True)
            raise


def saved_row(data: dict, provider_id: str) -> dict | None:
    """The saved record for a provider, or None when it has no usable secret."""
    row = data.get(provider_id)
    if not isinstance(row, dict):
        return None
    secret = row.get("secret")
    if isinstance(secret, str) and secret.strip():
        return row
    return None
