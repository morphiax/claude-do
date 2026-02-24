"""Behavioral spec registry operations."""

from __future__ import annotations

import re
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cli.store import hash as store_hash
from cli.store import jsonl

_SPECS_FILE = "specs.jsonl"
_VALID_TYPES = {"execute", "review"}


def _specs_path(root: Path) -> Path:
    return Path(root) / _SPECS_FILE


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _deduplicate(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return last-write-wins mapping of id -> record."""
    result: dict[str, dict[str, Any]] = {}
    for rec in records:
        if "id" in rec:
            result[rec["id"]] = rec
    return result


def register(
    root: Any,
    id: str,
    type: str,
    content: dict[str, Any],
    evidence_commands: list[str] | None = None,
) -> dict[str, Any]:
    """Add a new contract to the registry.

    Args:
        root: Root directory path.
        id: Unique contract identifier.
        type: Contract type — 'execute' or 'review'.
        content: Contract content dict.
        evidence_commands: Optional list of shell commands for review-type contracts.

    Returns:
        Envelope dict with ok/err result.
    """
    from cli.envelope import err, ok

    if type not in _VALID_TYPES:
        return err("SPEC_INVALID_TYPE", f"Type must be one of {sorted(_VALID_TYPES)}")

    if type == "review":
        missing = [f for f in ("question", "artifact") if f not in content]
        if missing:
            return err(
                "SPEC_REVIEW_INVALID",
                f"Review-type content missing required fields: {sorted(missing)}",
            )

    path = _specs_path(root)
    records = jsonl.read(path)
    existing = _deduplicate(records)

    if id in existing:
        return err("SPEC_DUPLICATE", f"Contract '{id}' already registered")

    content_hash = store_hash.content_hash(content)
    record: dict[str, Any] = {
        "id": id,
        "timestamp": _now_iso(),
        "type": type,
        "content": content,
        "content_hash": content_hash,
        "status": "pending",
        "satisfied_at": None,
        "proof": None,
        "artifact_hash": None,
    }
    if evidence_commands is not None:
        record["evidence_commands"] = evidence_commands
    jsonl.append(path, record)
    return ok({"id": id, "content_hash": content_hash, "status": "pending"})


def list_specs(root: Any) -> dict[str, Any]:
    """Return all contracts with current status (last-write-wins per id).

    Args:
        root: Root directory path.

    Returns:
        Envelope dict with list of contracts.
    """
    from cli.envelope import ok

    path = _specs_path(root)
    records = jsonl.read(path)
    deduped = _deduplicate(records)
    return ok(list(deduped.values()))


def count(root: Any) -> dict[str, Any]:
    """Return the number of registered contracts (deduplicated).

    Args:
        root: Root directory path.

    Returns:
        Envelope dict with count of unique contracts.
    """
    from cli.envelope import ok

    path = _specs_path(root)
    records = jsonl.read(path)
    deduped = _deduplicate(records)
    return ok({"count": len(deduped)})


def satisfy(root: Any, id: str, proof: dict[str, Any]) -> dict[str, Any]:
    """Record satisfaction for a contract.

    Args:
        root: Root directory path.
        id: Contract identifier.
        proof: Proof dict stored alongside the contract record. Hash verification
            is performed automatically — callers do not supply a content_hash.

    Returns:
        Envelope dict.
    """
    from cli.envelope import err, ok

    path = _specs_path(root)
    records = jsonl.read(path)
    existing = _deduplicate(records)

    if id not in existing:
        return err("SPEC_NOT_FOUND", f"Contract '{id}' not found")

    contract = existing[id]
    if contract["status"] == "satisfied":
        return err("SPEC_ALREADY_SATISFIED", f"Contract '{id}' is already satisfied")

    stored_hash = contract["content_hash"]
    current_hash = store_hash.content_hash(contract["content"])
    if current_hash != stored_hash:
        return err(
            "SPEC_HASH_MISMATCH",
            f"Content hash '{current_hash}' does not match registered"
            f" '{stored_hash}' — contract was modified outside of design",
        )

    artifact_hash = None
    if contract["type"] == "review":
        artifact_path = proof.get("artifact_path")
        if artifact_path:
            try:
                artifact_bytes = Path(artifact_path).read_bytes()
                artifact_hash = store_hash.content_hash(
                    artifact_bytes.decode("utf-8", errors="replace")
                )
            except OSError:
                pass

    satisfied_at = _now_iso()
    updated = {
        **contract,
        "status": "satisfied",
        "satisfied_at": satisfied_at,
        "proof": proof,
        "artifact_hash": artifact_hash,
    }
    jsonl.append(path, updated)
    return ok({"id": id, "status": "satisfied", "satisfied_at": satisfied_at})


def _recheck_execute(contract: dict[str, Any]) -> bool:
    """Re-run execute command. Returns True if still passing."""
    cmd_str = contract.get("content", {}).get("command", "")
    if not cmd_str:
        return False
    try:
        result = subprocess.run(
            shlex.split(cmd_str),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
        passed: bool = result.returncode == 0
        return passed
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def _recheck_review(contract: dict[str, Any]) -> bool:
    """Re-check artifact hash. Returns True if artifact unchanged."""
    proof = contract.get("proof") or {}
    artifact_path = proof.get("artifact_path")
    stored_artifact_hash = contract.get("artifact_hash")
    if not artifact_path or not stored_artifact_hash:
        return True
    try:
        artifact_bytes = Path(artifact_path).read_bytes()
        current_hash = store_hash.content_hash(
            artifact_bytes.decode("utf-8", errors="replace")
        )
        result: bool = current_hash == stored_artifact_hash
        return result
    except OSError:
        return False


def preflight(root: Any) -> dict[str, Any]:
    """Re-verify all satisfied contracts.

    Execute-type: re-run command, check exit 0.
    Review-type: check artifact content hash against snapshot.

    Args:
        root: Root directory path.

    Returns:
        Envelope with lists of still_satisfied and revoked contract ids.
    """
    from cli.envelope import ok

    path = _specs_path(root)
    records = jsonl.read(path)
    existing = _deduplicate(records)

    still_satisfied = []
    revoked = []

    for contract in existing.values():
        if contract["status"] != "satisfied":
            continue

        if contract["type"] == "execute":
            passed = _recheck_execute(contract)
        elif contract["type"] == "review":
            passed = _recheck_review(contract)
        else:
            passed = True

        if passed:
            still_satisfied.append(contract["id"])
        else:
            revoked.append(contract["id"])
            updated = {
                **contract,
                "status": "pending",
                "satisfied_at": None,
                "proof": None,
                "artifact_hash": None,
            }
            jsonl.append(path, updated)

    return ok({"still_satisfied": still_satisfied, "revoked": revoked})


def divergence(root: Any, spec_doc_path: Any) -> dict[str, Any]:
    """Compare contract IDs in a document against the registry.

    Args:
        root: Root directory path.
        spec_doc_path: Path to spec document to scan.

    Returns:
        Envelope with unregistered (in doc, not registry) and orphaned
        (in registry, not doc) lists.
    """
    from cli.envelope import err, ok

    try:
        doc_text = Path(spec_doc_path).read_text(encoding="utf-8")
    except OSError as e:
        return err("SPEC_DOC_NOT_FOUND", f"Cannot read spec doc: {e}")

    doc_ids = set(re.findall(r"\[([A-Z]+-\d+[a-z]*)\]", doc_text))

    path = _specs_path(root)
    records = jsonl.read(path)
    registry_ids = set(_deduplicate(records).keys())

    unregistered = sorted(doc_ids - registry_ids)
    orphaned = sorted(registry_ids - doc_ids)

    return ok({"unregistered": unregistered, "orphaned": orphaned})


def coverage(root: Any, ids: list[str]) -> dict[str, Any]:
    """Cross-reference given ids against the registry.

    Args:
        root: Root directory path.
        ids: List of contract ids to check.

    Returns:
        Envelope with per-id coverage info.
    """
    from cli.envelope import ok

    path = _specs_path(root)
    records = jsonl.read(path)
    existing = _deduplicate(records)

    results = []
    for cid in ids:
        if cid in existing:
            status = existing[cid]["status"]
            results.append({
                "id": cid,
                "registered": True,
                "status": status,
                "needs_work": status != "satisfied",
            })
        else:
            results.append({
                "id": cid,
                "registered": False,
                "status": None,
                "needs_work": True,
            })
    return ok(results)


def tighten(root: Any, id: str, new_content: dict[str, Any]) -> dict[str, Any]:
    """Update a contract's content and revert status to pending.

    Args:
        root: Root directory path.
        id: Contract identifier.
        new_content: New content dict.

    Returns:
        Envelope dict.
    """
    from cli.envelope import err, ok

    path = _specs_path(root)
    records = jsonl.read(path)
    existing = _deduplicate(records)

    if id not in existing:
        return err("SPEC_NOT_FOUND", f"Contract '{id}' not found")

    contract = existing[id]
    new_hash = store_hash.content_hash(new_content)

    updated = {
        **contract,
        "content": new_content,
        "content_hash": new_hash,
        "status": "pending",
        "satisfied_at": None,
        "proof": None,
        "artifact_hash": None,
        "timestamp": _now_iso(),
    }
    jsonl.append(path, updated)
    return ok({"id": id, "content_hash": new_hash, "status": "pending"})
