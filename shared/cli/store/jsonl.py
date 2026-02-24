"""JSONL store primitives: append and read with corruption tolerance."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def read(path: Path) -> list[dict[str, Any]]:
    """Read all valid records from a JSONL file.

    Skips corrupt/unparseable lines. Returns empty list if file does not exist.
    """
    if not path.exists():
        return []

    records: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                records.append(record)
            except (json.JSONDecodeError, ValueError):
                pass
    return records


def append(path: Path, record: dict[str, Any]) -> None:
    """Append a single record to a JSONL file using a single O_APPEND syscall.

    Uses os.open() with O_APPEND | O_CREAT to bypass Python buffering and
    ensure atomicity of the write at the OS level.
    """
    line = json.dumps(record, separators=(",", ":"), ensure_ascii=True) + "\n"
    encoded = line.encode("utf-8")

    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    fd = os.open(str(path), flags, 0o644)
    try:
        os.write(fd, encoded)
    finally:
        os.close(fd)
