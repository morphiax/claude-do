import sys
from pathlib import Path

import pytest

# Ensure shared/ is on sys.path so `import cli` resolves without PYTHONPATH=shared
_shared = str(Path(__file__).resolve().parent.parent / "shared")
if _shared not in sys.path:
    sys.path.insert(0, _shared)


@pytest.fixture  # type: ignore[misc]
def root(tmp_path: Path) -> Path:
    """Isolated .do root directory."""
    d = tmp_path / ".do"
    d.mkdir()
    return d
