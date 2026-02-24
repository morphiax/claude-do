"""Trace store operations: append-only event log."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cli.store import jsonl
from cli.envelope import ok, err


def _trace_path(root: Path) -> Path:
    return Path(root) / "traces.jsonl"


def add(root: Path, data: dict[str, Any]) -> dict[str, Any]:
    """Append a trace event. Write failures do not crash — warning included in result.

    Required field: event.
    """
    if "event" not in data:
        return err("TRACE_MISSING_FIELD", "missing required field: event")

    record = {
        **data,
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    warning = None
    try:
        Path(root).mkdir(parents=True, exist_ok=True)
        jsonl.append(_trace_path(root), record)
    except Exception as exc:
        warning = f"write failed: {exc}"

    result: dict[str, Any] = {"id": record["id"]}
    if warning is not None:
        result["warning"] = warning
    return ok(result)
