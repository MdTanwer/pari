"""macOS Seatbelt runner is not implemented yet."""

from pathlib import Path

import pytest

from pari.sandbox.seatbelt import MacOSSeatbeltSandboxRunner


def test_seatbelt_run_is_coming_soon(tmp_path: Path):
    runner = MacOSSeatbeltSandboxRunner(tmp_path)
    with pytest.raises(NotImplementedError, match="coming soon"):
        runner.run_command("echo hello")
