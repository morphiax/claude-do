"""Research store operations: add, search, list_research."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cli.store import atomic
from cli.envelope import ok, err


def _research_dir(root: Path) -> Path:
    return Path(root) / "research"


def add(root: Path, data: dict[str, Any]) -> dict[str, Any]:
    """Create a new research artifact as an individual JSON file.

    Required fields: topic, findings.
    """
    required = ["topic", "findings"]
    for field in required:
        if field not in data:
            return err("RESEARCH_MISSING_FIELD", f"missing required field: {field}")

    artifact_id = str(uuid.uuid4())
    record = {
        **data,
        "id": artifact_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    dest = _research_dir(root) / f"{artifact_id}.json"
    atomic.write(dest, record)
    return ok({"id": artifact_id})


def search(root: Path, keyword: str) -> dict[str, Any]:
    """Case-insensitive substring search on topic and findings across all artifacts."""
    research_dir = _research_dir(root)
    results = []
    kw = keyword.lower()

    if not research_dir.exists():
        return ok({"results": []})

    for fpath in sorted(research_dir.glob("*.json")):
        record = atomic.read(fpath)
        if record is None:
            continue
        topic_match = kw in str(record.get("topic", "")).lower()
        findings_match = kw in str(record.get("findings", "")).lower()
        if topic_match or findings_match:
            results.append(record)

    return ok({"results": results})


def list_research(root: Path) -> dict[str, Any]:
    """Return all research artifacts."""
    research_dir = _research_dir(root)
    results = []

    if not research_dir.exists():
        return ok({"results": []})

    for fpath in sorted(research_dir.glob("*.json")):
        record = atomic.read(fpath)
        if record is not None:
            results.append(record)

    return ok({"results": results})
