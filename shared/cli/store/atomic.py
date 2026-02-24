"""Atomic file write: write to temp, fsync, then os.replace()."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def write(path: Path, data: Any) -> None:
    """Atomically write JSON data to path.

    Strategy: mkstemp in same directory -> write -> fsync -> os.replace().
    On any failure, the temp file is unlinked; no temp files are left behind.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    content = json.dumps(data, ensure_ascii=True, indent=2)
    encoded = content.encode("utf-8")

    fd, tmp_path = tempfile.mkstemp(dir=path.parent)
    try:
        try:
            os.write(fd, encoded)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def read(path: Path) -> Any:
    """Read JSON data from path. Returns None if file does not exist."""
    path = Path(path)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)
