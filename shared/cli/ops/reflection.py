"""Reflection store operations: add, list_reflections."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cli.store import jsonl
from cli.envelope import ok, err

VALID_LENS = {"product", "process"}
VALID_URGENCY = {"immediate", "deferred"}


def _reflection_path(root: Path) -> Path:
    return Path(root) / "reflections.jsonl"


def add(root: Path, data: dict[str, Any]) -> dict[str, Any]:
    """Validate and append a reflection record.

    Required fields: type, outcome, lens, urgency.
    Lens must be 'product' or 'process'.
    Urgency must be 'immediate' or 'deferred'.
    If failures is non-empty, fix_proposals must be non-empty.
    """
    required = ["type", "outcome", "lens", "urgency"]
    for field in required:
        if field not in data:
            return err("REFLECTION_MISSING_FIELD", f"missing required field: {field}")

    if data["lens"] not in VALID_LENS:
        return err(
            "REFLECTION_INVALID_LENS",
            f"lens must be one of {sorted(VALID_LENS)}, got: {data['lens']}",
        )

    if data["urgency"] not in VALID_URGENCY:
        return err(
            "REFLECTION_INVALID_URGENCY",
            f"urgency must be one of {sorted(VALID_URGENCY)}, got: {data['urgency']}",
        )

    failures = data.get("failures", [])
    fix_proposals = data.get("fix_proposals", [])
    if failures and not fix_proposals:
        return err(
            "REFLECTION_MISSING_FIX_PROPOSALS",
            "fix_proposals must be non-empty when failures is non-empty",
        )

    record = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": data["type"],
        "outcome": data["outcome"],
        "lens": data["lens"],
        "urgency": data["urgency"],
        "failures": failures,
        "fix_proposals": fix_proposals,
        "severity": data.get("severity"),
        "evidence": data.get("evidence"),
        "proposals": data.get("proposals"),
    }

    Path(root).mkdir(parents=True, exist_ok=True)
    jsonl.append(_reflection_path(root), record)
    return ok({"id": record["id"]})


def resolve(root: Path, finding_id: str, resolution_text: str) -> dict[str, Any]:
    """Append a resolution record referencing an existing finding.

    Returns an error if the finding_id does not exist in the store.
    Does not modify existing JSONL records — appends a new resolution record.
    """
    records = jsonl.read(_reflection_path(root))
    finding_ids = {r["id"] for r in records if r.get("type") != "resolution" and "id" in r}
    if finding_id not in finding_ids:
        return err("REFLECTION_NOT_FOUND", f"finding not found: {finding_id}")

    record = {
        "id": str(uuid.uuid4()),
        "type": "resolution",
        "finding_id": finding_id,
        "resolution": resolution_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    Path(root).mkdir(parents=True, exist_ok=True)
    jsonl.append(_reflection_path(root), record)
    return ok({
        "id": record["id"],
        "finding_id": finding_id,
        "resolution": resolution_text,
        "timestamp": record["timestamp"],
    })


def list_reflections(
    root: Path,
    lens: str | None = None,
    urgency: str | None = None,
    include_resolved: bool = False,
) -> dict[str, Any]:
    """Return reflections filtered by lens and/or urgency.

    Excludes resolved findings by default. Pass include_resolved=True to show all findings.
    Resolution records are never included in list output.
    """
    records = jsonl.read(_reflection_path(root))
    resolved_ids: set[str] = {
        r["finding_id"] for r in records if r.get("type") == "resolution" and "finding_id" in r
    }
    results = [r for r in records if r.get("type") != "resolution"]
    if not include_resolved:
        results = [r for r in results if r.get("id") not in resolved_ids]
    if lens is not None:
        results = [r for r in results if r.get("lens") == lens]
    if urgency is not None:
        results = [r for r in results if r.get("urgency") == urgency]
    return ok({"results": results})
