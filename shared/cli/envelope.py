"""Result envelope formatting for cli CLI output."""

from __future__ import annotations

import json
from typing import Any


def ok(data: Any) -> dict[str, Any]:
    """Return a success envelope."""
    return {"ok": True, "data": data}


def err(error: str, message: str) -> dict[str, Any]:
    """Return a failure envelope.

    Args:
        error: UPPER_SNAKE_CASE error code in MODULE_CONDITION format.
        message: Human-readable description.
    """
    return {"ok": False, "error": error, "message": message}


def render(envelope: dict[str, Any]) -> str:
    """Serialize an envelope to a compact JSON string."""
    return json.dumps(envelope, separators=(",", ":"), ensure_ascii=True)
