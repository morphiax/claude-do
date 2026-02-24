"""Memory store operations: add, search, boost, suppress."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cli.store import jsonl
from cli.envelope import ok, err


def _memory_path(root: Path) -> Path:
    return Path(root) / "memory.jsonl"


def _dedup(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate by id, last entry wins."""
    seen: dict[str, dict[str, Any]] = {}
    for r in records:
        seen[r["id"]] = r
    return list(seen.values())


def _validate_importance(value: Any) -> tuple[bool, str, int]:
    """Validate and return (valid, error_message, numeric_value)."""
    if value is None:
        return True, "", 3
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False, "importance must be numeric", 0
    numeric = int(value)
    if numeric < 3:
        return False, "importance must be >= 3", 0
    return True, "", numeric


def add(root: Path, data: dict[str, Any]) -> dict[str, Any]:
    """Validate and append a memory record.

    Required fields: category, keywords, content, source.
    Importance defaults to 3, must be 3-10.
    """
    required = ["category", "keywords", "content", "source"]
    for field in required:
        if field not in data:
            return err("MEMORY_MISSING_FIELD", f"missing required field: {field}")

    valid, msg, importance = _validate_importance(data.get("importance"))
    if not valid:
        return err("MEMORY_INVALID_IMPORTANCE", msg)

    record = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "category": data["category"],
        "keywords": data["keywords"],
        "content": data["content"],
        "source": data["source"],
        "importance": importance,
    }

    try:
        root_path = Path(root)
        root_path.mkdir(parents=True, exist_ok=True)
        jsonl.append(_memory_path(root), record)
    except Exception as exc:
        return ok({"id": record["id"], "warning": f"write failed: {exc}"})

    return ok({"id": record["id"]})


def search(root: Path, keyword: str) -> dict[str, Any]:
    """Case-insensitive substring search on category, keywords list items, and content."""
    records = _dedup(jsonl.read(_memory_path(root)))
    kw = keyword.lower()
    results = []
    for r in records:
        category_match = kw in r.get("category", "").lower()
        content_match = kw in r.get("content", "").lower()
        kws = r.get("keywords", [])
        keywords_match = any(kw in k.lower() for k in kws if isinstance(k, str))
        if category_match or content_match or keywords_match:
            results.append(r)
    return ok({"results": results})


def boost(root: Path, record_id: str, amount: int) -> dict[str, Any]:
    """Increment importance by amount, clamp at 10, append updated record."""
    records = jsonl.read(_memory_path(root))
    deduped = _dedup(records)
    target = next((r for r in deduped if r["id"] == record_id), None)
    if target is None:
        return err("MEMORY_NOT_FOUND", f"no memory with id: {record_id}")

    new_importance = min(10, target.get("importance", 3) + amount)
    updated = {**target, "importance": new_importance}

    try:
        Path(root).mkdir(parents=True, exist_ok=True)
        jsonl.append(_memory_path(root), updated)
    except Exception as exc:
        return ok({"id": record_id, "warning": f"write failed: {exc}"})

    return ok({"id": record_id, "importance": new_importance})


def suppress(root: Path, record_id: str) -> dict[str, Any]:
    """Set importance to 0, append updated record."""
    records = jsonl.read(_memory_path(root))
    deduped = _dedup(records)
    target = next((r for r in deduped if r["id"] == record_id), None)
    if target is None:
        return err("MEMORY_NOT_FOUND", f"no memory with id: {record_id}")

    updated = {**target, "importance": 0}

    try:
        Path(root).mkdir(parents=True, exist_ok=True)
        jsonl.append(_memory_path(root), updated)
    except Exception as exc:
        return ok({"id": record_id, "warning": f"write failed: {exc}"})

    return ok({"id": record_id, "importance": 0})
