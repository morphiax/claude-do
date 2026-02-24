"""Archive operation: move ephemeral directories to timestamped history."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from typing import Any

from cli import envelope

# Files/directories that persist across archive operations.
_PERSISTENT_FILES = {
    "specs.jsonl",
    "memory.jsonl",
    "reflections.jsonl",
    "traces.jsonl",
    "conventions.md",
    "aesthetics.md",
}
_PERSISTENT_DIRS = {"research"}

# Directories that are ephemeral and will be moved to history on archive.
_EPHEMERAL_DIRS = {"plans", "experts", "workers"}


def _timestamp() -> str:
    """Return an ISO-8601 UTC timestamp in YYYYMMDD_HHMMSS format."""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y%m%d_%H%M%S")


def _sanitize_goal(goal: str) -> str:
    """Sanitize a plan goal string into a safe filename stem.

    Returns 'unnamed-plan' if the goal is empty or whitespace-only after
    sanitization.
    """
    # Remove filesystem-unsafe characters (nulls, slashes, colons) by replacing
    # with hyphens, then treat all non-alphanumeric chars as hyphens.
    sanitized = goal.lower()
    sanitized = re.sub(r"[^a-z0-9]+", "-", sanitized)
    sanitized = sanitized.strip("-")
    sanitized = sanitized[:60]
    sanitized = sanitized.strip("-")
    return sanitized or "unnamed-plan"


def _rename_plan(history_dest: Path) -> None:
    """Rename current.json in the archived plans dir to a goal-derived name."""
    plans_dir = history_dest / "plans"
    current = plans_dir / "current.json"
    if not current.exists():
        return

    goal_name = "unnamed-plan"
    try:
        data = json.loads(current.read_text())
        raw_goal = data.get("goal", "")
        if isinstance(raw_goal, str) and raw_goal.strip():
            goal_name = _sanitize_goal(raw_goal)
    except (json.JSONDecodeError, OSError):
        pass

    current.rename(plans_dir / f"{goal_name}.json")


def _read_plan(history_dest: Path) -> dict[str, Any]:
    """Read the plan from the archived plans directory, if present."""
    plans_dir = history_dest / "plans"
    if not plans_dir.is_dir():
        return {}
    for p in plans_dir.glob("*.json"):
        try:
            result: dict[str, Any] = json.loads(p.read_text())
            return result
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _write_summary(history_dest: Path, ts: str) -> None:
    """Write an ARCHIVE.md summary file to the history destination directory."""
    plan = _read_plan(history_dest)
    goal = plan.get("goal", "")
    roles: list[dict[str, Any]] = plan.get("roles", [])

    lines: list[str] = [
        "# Archive Summary",
        "",
        "## Timestamp",
        "",
        ts,
        "",
        "## Plan Goal",
        "",
        goal if goal else "(no goal)",
        "",
        "## Roles",
        "",
    ]

    if roles:
        for role in roles:
            name = role.get("name", "(unnamed)")
            status = role.get("status", "(no status)")
            contracts: list[str] = role.get("contract_ids", [])
            contract_str = ", ".join(contracts) if contracts else ""
            role_line = f"- **{name}**: {status}"
            if contract_str:
                role_line += f" (contracts: {contract_str})"
            lines.append(role_line)
    else:
        lines.append("(no roles)")

    lines += [
        "",
        "## File Inventory",
        "",
    ]

    for item in sorted(history_dest.rglob("*")):
        if item.name == "ARCHIVE.md":
            continue
        rel = item.relative_to(history_dest)
        lines.append(f"- {rel}")

    lines.append("")

    (history_dest / "ARCHIVE.md").write_text("\n".join(lines))


def archive(root: Path) -> dict[str, Any]:
    """Move ephemeral directories to {root}/history/{timestamp}/.

    Args:
        root: The root directory containing ephemeral and persistent state.

    Returns:
        An envelope dict. ok=True on success (including no-op). ok=False if
        any post-condition fails.
    """
    root = Path(root)

    # Identify which ephemeral dirs actually exist.
    existing_ephemeral = [
        root / d for d in _EPHEMERAL_DIRS if (root / d).is_dir()
    ]

    if not existing_ephemeral:
        return envelope.ok({"archived": [], "message": "nothing to archive"})

    # Snapshot which persistent files exist before the operation.
    persistent_before = {
        name for name in _PERSISTENT_FILES if (root / name).exists()
    }
    persistent_dirs_before = {
        name for name in _PERSISTENT_DIRS if (root / name).is_dir()
    }

    # Create the history destination.
    ts = _timestamp()
    history_dest = root / "history" / ts
    history_dest.mkdir(parents=True, exist_ok=True)

    archived = []
    for src in existing_ephemeral:
        dest = history_dest / src.name
        src.rename(dest)
        archived.append(src.name)

    # XC-43: Rename current.json to a goal-derived filename.
    _rename_plan(history_dest)

    # XC-44: Write archive summary.
    _write_summary(history_dest, ts)

    # Verify post-conditions.
    failures = _verify_postconditions(
        root, history_dest, persistent_before, persistent_dirs_before, archived
    )

    if failures:
        return envelope.err(
            "ARCHIVE_POSTCONDITION_FAILED",
            "Post-condition failures: " + "; ".join(failures),
        )

    return envelope.ok({"archived": archived, "history": str(history_dest)})


def _verify_postconditions(
    root: Path,
    history_dest: Path,
    persistent_before: set[str],
    persistent_dirs_before: set[str],
    archived: list[str],
) -> list[str]:
    """Return a list of failure messages (empty means all checks passed)."""
    failures: list[str] = []

    # a) No ephemeral directories remain in root.
    for name in _EPHEMERAL_DIRS:
        if (root / name).exists():
            failures.append(f"ephemeral dir still present: {name}")

    # b) All persistent files that existed before still exist.
    for name in persistent_before:
        if not (root / name).exists():
            failures.append(f"persistent file missing after archive: {name}")
    for name in persistent_dirs_before:
        if not (root / name).is_dir():
            failures.append(f"persistent dir missing after archive: {name}")

    # c) History directory contains the archived artifacts.
    for name in archived:
        if not (history_dest / name).exists():
            failures.append(f"archived artifact missing from history: {name}")

    # d) Summary file exists.
    if not (history_dest / "ARCHIVE.md").exists():
        failures.append("ARCHIVE.md missing from history destination")

    return failures
