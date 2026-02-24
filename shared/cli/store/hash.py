"""Content hashing for canonical object identity."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def content_hash(obj: Any) -> str:
    """Return SHA-256 hex digest of the canonical JSON form of obj.

    Uses sort_keys=True so that identical logical objects with different key
    insertion orders produce the same hash.
    """
    canonical = json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
