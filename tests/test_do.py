"""Tests for shared/do.py entry point."""

import subprocess
import sys
from pathlib import Path

ENTRY = Path(__file__).resolve().parent.parent / "shared" / "do.py"


class TestEntryPoint:
    def test_help_exits_zero(self) -> None:
        r = subprocess.run(  # noqa: S603
            [sys.executable, str(ENTRY), "--help"],
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0
        assert "DOMAIN" in r.stdout

    def test_stderr_empty(self) -> None:
        r = subprocess.run(  # noqa: S603
            [sys.executable, str(ENTRY), "--help"],
            capture_output=True,
            text=True,
        )
        assert r.stderr == ""

    def test_unknown_domain_exits_nonzero(self) -> None:
        r = subprocess.run(  # noqa: S603
            [sys.executable, str(ENTRY), "nonexistent"],
            capture_output=True,
            text=True,
        )
        assert r.returncode == 2
        assert r.stderr == ""
