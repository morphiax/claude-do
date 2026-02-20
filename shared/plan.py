#!/usr/bin/env python3
"""plan.py - Deterministic operations for .design/plan.json manipulation.

Schema version 4: Role-based briefs with goal-directed execution.

Query commands (read-only):
  team-name, status, summary, overlap-matrix, tasklist-data, worker-pool,
  retry-candidates, circuit-breaker, memory-search, reflection-search,
  memory-summary

Mutation commands (modify plan.json):
  resume-reset, update-status, memory-add, reflection-add

Build commands (validation & enrichment):
  finalize, expert-validate, reflection-validate, research-validate,
  research-summary

Archive command:
  archive

All commands output JSON to stdout with top-level 'ok' field.
Exit code: 0 for success, 1 for errors.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, NoReturn

# ============================================================================
# Shared Utilities
# ============================================================================


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_timestamp(value: Any) -> float:
    """Parse a timestamp to epoch seconds. Handles both ISO strings and floats."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
            return dt.replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            pass
    return 0.0


def load_plan(path: str) -> dict[str, Any]:
    """Load and parse plan.json. Exit on error."""
    return _load_json_file(path, "plan file")


def _load_json_file(path: str, label: str = "file") -> dict[str, Any]:
    """Load and parse a JSON file. Exit on error.

    Args:
        path: File path to load.
        label: Human-readable label for error messages (e.g., "plan file", "research file").
    """
    if not os.path.exists(path):
        error_exit(f"{label.capitalize()} not found: {path}")

    try:
        with open(path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        error_exit(f"Invalid JSON in {label}: {e}")
    except OSError as e:
        error_exit(f"Error reading {label}: {e}")


def output_json(data: Any) -> NoReturn:
    """Output JSON to stdout and exit 0."""
    sys.stdout.write(json.dumps(data, indent=2) + "\n")
    sys.exit(0)


def error_exit(message: str) -> NoReturn:
    """Output error JSON and exit 1."""
    sys.stdout.write(json.dumps({"ok": False, "error": message}, indent=2) + "\n")
    sys.exit(1)


def build_name_index(roles: list[dict[str, Any]]) -> dict[str, int]:
    """Build role name → index mapping."""
    return {r.get("name", ""): i for i, r in enumerate(roles)}


def _read_jsonl(path: str, filter_fn=None) -> list[dict[str, Any]]:
    """Read a JSONL file, skipping empty lines and parse errors.

    Returns list of parsed dicts. Returns [] if file does not exist.
    Raises OSError if file exists but cannot be opened/read.
    Optional filter_fn(entry) -> bool filters out entries when False.
    """
    if not os.path.exists(path):
        return []
    entries: list[dict[str, Any]] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if filter_fn is None or filter_fn(entry):
                    entries.append(entry)
            except json.JSONDecodeError:
                pass
    return entries


def resolve_dependencies(
    roles: list[dict[str, Any]], name_index: dict[str, int]
) -> list[list[int]]:
    """Resolve scope.dependencies (role names) to index lists."""
    resolved = []
    for role in roles:
        deps = role.get("scope", {}).get("dependencies", [])
        resolved.append([name_index[d] for d in deps if d in name_index])
    return resolved


def _plan_with_deps(
    plan_path: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, int], list[list[int]]]:
    """Load plan and compute name_index + dep_indices in one call.

    Returns:
        (plan, roles, name_index, dep_indices)
    """
    plan = load_plan(plan_path)
    roles = plan.get("roles", [])
    name_index = build_name_index(roles)
    dep_indices = resolve_dependencies(roles, name_index)
    return plan, roles, name_index, dep_indices


def _read_stdin_json(error_msg: str, include_error: bool = False) -> Any:
    """Read and parse JSON from stdin. Calls error_exit on parse failure.

    Args:
        error_msg: Base error message. When include_error=True, ': {exception}' is appended.
        include_error: If True, append the JSONDecodeError detail to error_msg.
    """
    try:
        return json.load(sys.stdin)
    except json.JSONDecodeError as e:
        if include_error:
            error_exit(f"{error_msg}: {e}")
        else:
            error_exit(error_msg)


def compute_depths(
    roles: list[dict[str, Any]], dep_indices: list[list[int]]
) -> dict[int, int]:
    """Compute dependency depth for each role. Returns dict {roleIndex: depth}."""
    depths: dict[int, int] = {}

    def get_depth(index: int, visited: set[int] | None = None) -> int:
        if visited is None:
            visited = set()
        if index in depths:
            return depths[index]
        if index in visited:
            return 999

        blocked_by = dep_indices[index]
        if not blocked_by:
            depths[index] = 1
            return 1

        visited.add(index)
        max_dep_depth = max(
            (get_depth(dep, visited.copy()) for dep in blocked_by), default=0
        )
        visited.remove(index)
        depths[index] = max_dep_depth + 1
        return depths[index]

    for i in range(len(roles)):
        if i not in depths:
            get_depth(i)
    return depths


def get_transitive_deps(
    dep_indices: list[list[int]], start_indices: list[int]
) -> set[int]:
    """Get all roles transitively depending on start_indices (forward closure)."""
    reverse_deps: dict[int, list[int]] = defaultdict(list)
    for i, deps in enumerate(dep_indices):
        for dep in deps:
            reverse_deps[dep].append(i)

    transitive: set[int] = set()
    queue: deque[int] = deque(start_indices)
    while queue:
        idx = queue.popleft()
        if idx in transitive:
            continue
        transitive.add(idx)
        for dependent in reverse_deps.get(idx, []):
            if dependent not in transitive:
                queue.append(dependent)

    return transitive - set(start_indices)


def atomic_write(path: str, data: Any) -> None:
    """Atomically write JSON data to path using temp file + rename."""
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        os.rename(tmp_path, path)
    except OSError:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


# ============================================================================
# Query Commands
# ============================================================================


def cmd_team_name(args: argparse.Namespace) -> NoReturn:
    """Generate a deterministic, project-unique team name.

    Combines a skill prefix with a sanitized directory basename and a short
    hash of the full path to avoid collisions between projects with the
    same directory name.
    """
    skill = args.skill
    cwd = os.getcwd()
    basename = os.path.basename(cwd).lower()
    # Sanitize: keep only alphanumeric and hyphens, collapse runs
    sanitized = re.sub(r"[^a-z0-9]+", "-", basename).strip("-")[:20]
    short_hash = hashlib.md5(cwd.encode(), usedforsecurity=False).hexdigest()[:6]
    team_name = f"do-{skill}-{sanitized}-{short_hash}"
    output_json({"ok": True, "teamName": team_name})


def _load_plan_for_status(plan_path: str) -> dict[str, Any]:
    """Load plan.json with machine-parseable error tokens for execute pre-flight."""
    if not os.path.exists(plan_path):
        error_exit("not_found")
    try:
        with open(plan_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        error_exit("invalid_json")


def cmd_status(args: argparse.Namespace) -> NoReturn:
    """Validate plan and return status counts."""
    plan_path = args.plan_path
    plan = _load_plan_for_status(plan_path)

    schema_version = plan.get("schemaVersion")
    if schema_version != 4:
        error_exit(f"bad_schema (schemaVersion={schema_version}, expected 4)")

    roles = plan.get("roles", [])
    if not roles:
        error_exit("empty_roles")

    counts: dict[str, int] = defaultdict(int)
    for role in roles:
        status = role.get("status", "pending")
        counts[status] += 1

    total = len(roles)
    is_resume = any(status != "pending" for status in counts)

    output_json(
        {
            "ok": True,
            "schemaVersion": schema_version,
            "roleCount": total,
            "counts": dict(counts),
            "isResume": is_resume,
        }
    )


def cmd_summary(args: argparse.Namespace) -> NoReturn:
    """Compute roleCount, maxDepth, depthSummary, and modelDistribution."""
    plan, roles, _name_index, dep_indices = _plan_with_deps(args.plan_path)
    goal = plan.get("goal", "")

    role_count = len(roles)
    depths = compute_depths(roles, dep_indices)
    max_depth = max(depths.values()) if depths else 0

    depth_summary: dict[str, list[str]] = defaultdict(list)
    for i, role in enumerate(roles):
        depth = depths.get(i, 1)
        model = role.get("model", "")
        name = role.get("name", "")
        depth_summary[str(depth)].append(f"Role {i}: {name} ({model})")

    model_counts: dict[str, int] = defaultdict(int)
    for role in roles:
        model = role.get("model", "unknown")
        model_counts[model] += 1

    model_dist = ", ".join(
        f"{count} {model}" for model, count in sorted(model_counts.items())
    )

    auxiliary = plan.get("auxiliaryRoles", [])
    aux_names = [a.get("name", "") for a in auxiliary]

    output_json(
        {
            "ok": True,
            "goal": goal,
            "roleCount": role_count,
            "maxDepth": max_depth,
            "depthSummary": dict(depth_summary),
            "modelDistribution": model_dist,
            "auxiliaryRoles": aux_names,
        }
    )


def _compute_overlaps(
    roles: list[dict[str, Any]], dep_indices: list[list[int]]
) -> dict[int, list[int]]:
    """Compute directory overlaps for concurrent role pairs (j>i ordering).

    Args:
        roles: List of role dicts with scope containing directories/patterns.
        dep_indices: Dependency indices from resolve_dependencies.

    Returns:
        Dictionary mapping role index i to list of overlapping role indices j (all j > i).
    """
    # Collect directories + patterns per role
    role_dirs: list[set[str]] = []
    for role in roles:
        scope = role.get("scope", {})
        dirs = set(scope.get("directories", []))
        dirs.update(scope.get("patterns", []))
        role_dirs.append(dirs)

    # Enforce j>i ordering to prevent bidirectional deadlocks.
    # When roles i and j overlap, only the later role (j) blocks on the earlier (i).
    overlaps_by_role: dict[int, list[int]] = {}
    for i in range(len(roles)):
        i_closure = set(_transitive_closure(dep_indices, i))
        overlaps: list[int] = []
        for j in range(len(roles)):
            if j <= i:
                continue  # Enforce j>i rule to prevent bidirectional deadlocks
            j_closure = set(_transitive_closure(dep_indices, j))
            if (
                j not in i_closure
                and i not in j_closure
                and _dirs_overlap(role_dirs[i], role_dirs[j])
            ):
                overlaps.append(j)
        if overlaps:
            overlaps_by_role[i] = overlaps

    return overlaps_by_role


def cmd_overlap_matrix(args: argparse.Namespace) -> NoReturn:
    """Compute directory overlap matrix between roles."""
    _plan, roles, _name_index, dep_indices = _plan_with_deps(args.plan_path)

    overlaps_by_role = _compute_overlaps(roles, dep_indices)

    # Convert to string-keyed matrix for JSON output
    matrix: dict[str, list[int]] = {
        str(i): overlaps for i, overlaps in overlaps_by_role.items()
    }

    output_json({"ok": True, "matrix": matrix})


def _paths_overlap(a: str, b: str) -> bool:
    """Check if two directory paths or glob patterns overlap."""
    if a == b:
        return True
    a_norm = a.rstrip("/") + "/"
    b_norm = b.rstrip("/") + "/"
    if a_norm.startswith(b_norm) or b_norm.startswith(a_norm):
        return True
    return _glob_bases_overlap(a, b)


def _glob_bases_overlap(a: str, b: str) -> bool:
    """Check if glob pattern base directories overlap."""
    if "**" not in a and "**" not in b:
        return False
    a_base = a.split("*")[0].rstrip("/")
    b_base = b.split("*")[0].rstrip("/")
    if not a_base or not b_base:
        return False
    a_base_norm = a_base + "/"
    b_base_norm = b_base + "/"
    return a_base_norm.startswith(b_base_norm) or b_base_norm.startswith(a_base_norm)


def _dirs_overlap(dirs_a: set[str], dirs_b: set[str]) -> bool:
    """Check if two sets of directories/patterns have potential overlap."""
    return any(_paths_overlap(a, b) for a in dirs_a for b in dirs_b)


def _transitive_closure(dep_indices: list[list[int]], start: int) -> list[int]:
    """Get all transitive dependencies of a role (backward closure)."""
    visited: set[int] = set()
    queue: deque[int] = deque([start])
    while queue:
        idx = queue.popleft()
        for dep in dep_indices[idx]:
            if dep not in visited:
                visited.add(dep)
                queue.append(dep)
    return list(visited)


def cmd_tasklist_data(args: argparse.Namespace) -> NoReturn:
    """Extract fields needed for TaskCreate calls — one entry per role."""
    _plan, roles, _name_index, dep_indices = _plan_with_deps(args.plan_path)

    result = []
    for i, role in enumerate(roles):
        result.append(
            {
                "roleIndex": i,
                "name": role.get("name", ""),
                "goal": role.get("goal", ""),
                "activeForm": f"Working as {role.get('name', 'worker')}",
                "blockedBy": dep_indices[i],
                "status": role.get("status", "pending"),
            }
        )

    output_json({"ok": True, "roles": result})


def _slugify_role(role: str) -> str:
    """Convert role name to kebab-case slug for worker naming."""
    slug = role.lower()
    slug = re.sub(r"[_\s]+", "-", slug)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug)
    return slug.strip("-") or "worker"


def _deduplicate_slug(slug: str, used_slugs: set[str]) -> str:
    """Return a unique slug by appending numeric suffixes if needed."""
    if slug not in used_slugs:
        return slug
    suffix = 2
    while f"{slug}-{suffix}" in used_slugs:
        suffix += 1
    return f"{slug}-{suffix}"


def cmd_worker_pool(args: argparse.Namespace) -> NoReturn:
    """Compute worker pool directly from roles[] — one worker per role."""
    _plan, roles, _name_index, dep_indices = _plan_with_deps(args.plan_path)

    # Filter to pending/runnable roles
    runnable: list[int] = []
    for i, role in enumerate(roles):
        if role.get("status", "pending") != "pending":
            continue
        # Check if any dependency is failed/blocked/skipped
        deps_ok = True
        for dep in dep_indices[i]:
            dep_status = roles[dep].get("status", "pending")
            if dep_status in ("failed", "blocked", "skipped"):
                deps_ok = False
                break
        if deps_ok:
            runnable.append(i)

    if not runnable:
        output_json({"ok": True, "workers": [], "maxConcurrency": 0, "totalWorkers": 0})

    # Compute max concurrency from dependency graph width
    depths = compute_depths(roles, dep_indices)
    depth_groups: dict[int, list[int]] = defaultdict(list)
    for i in runnable:
        depth_groups[depths.get(i, 1)].append(i)
    max_width = max((len(g) for g in depth_groups.values()), default=1)

    workers = []
    used_slugs: set[str] = set()
    for i in runnable:
        role = roles[i]
        slug = _deduplicate_slug(_slugify_role(role.get("name", "")), used_slugs)
        used_slugs.add(slug)
        workers.append(
            {
                "name": slug,
                "role": role.get("name", ""),
                "model": role.get("model", "sonnet"),
                "roleIndex": i,
            }
        )

    output_json(
        {
            "ok": True,
            "workers": workers,
            "maxConcurrency": max_width,
            "totalWorkers": len(workers),
        }
    )


def cmd_retry_candidates(args: argparse.Namespace) -> NoReturn:
    """Find failed roles with attempts < 3."""
    plan = load_plan(args.plan_path)
    roles = plan.get("roles", [])

    retryable = []
    for i, role in enumerate(roles):
        status = role.get("status")
        attempts = role.get("attempts", 0)

        if status == "failed" and attempts < 3:
            retryable.append(
                {
                    "roleIndex": i,
                    "name": role.get("name", ""),
                    "goal": role.get("goal", ""),
                    "attempts": attempts,
                    "result": role.get("result", ""),
                    "model": role.get("model", ""),
                    "fallback": role.get("fallback"),
                }
            )

    output_json({"ok": True, "retryable": retryable})


def cmd_circuit_breaker(args: argparse.Namespace) -> NoReturn:
    """Check if >50% of remaining roles would be skipped by cascading failures."""
    _plan, roles, _name_index, dep_indices = _plan_with_deps(args.plan_path)

    total_roles = len(roles)
    pending_count = sum(1 for r in roles if r.get("status") == "pending")

    failed_indices = [
        i for i, r in enumerate(roles) if r.get("status") in ("failed", "blocked")
    ]

    would_skip = get_transitive_deps(dep_indices, failed_indices)
    would_be_skipped = len(
        [i for i in would_skip if roles[i].get("status") == "pending"]
    )

    # Bypass for small plans (3 or fewer roles)
    should_abort = (
        total_roles > 3
        and pending_count > 0
        and would_be_skipped >= pending_count * 0.5
    )

    reason = ""
    if should_abort:
        reason = (
            f"Circuit breaker: {would_be_skipped}/{pending_count} "
            "pending roles would be skipped"
        )

    output_json(
        {
            "ok": True,
            "totalRoles": total_roles,
            "pendingCount": pending_count,
            "wouldBeSkipped": would_be_skipped,
            "shouldAbort": should_abort,
            "reason": reason,
        }
    )


# ============================================================================
# Mutation Commands
# ============================================================================


def cmd_resume_reset(args: argparse.Namespace) -> NoReturn:
    """Reset in_progress roles to pending, increment attempts."""
    plan_path = args.plan_path
    plan = load_plan(plan_path)
    roles = plan.get("roles", [])

    reset_roles = []
    for i, role in enumerate(roles):
        if role.get("status") == "in_progress":
            role["status"] = "pending"
            role["attempts"] = role.get("attempts", 0) + 1
            reset_roles.append(
                {
                    "roleIndex": i,
                    "name": role.get("name", ""),
                }
            )

    no_work_remaining = all(r.get("status") != "pending" for r in roles)
    atomic_write(plan_path, plan)

    output_json(
        {"ok": True, "resetRoles": reset_roles, "noWorkRemaining": no_work_remaining}
    )


def _trim_role_fields(role: dict[str, Any]) -> None:
    """Remove non-essential fields from a completed role."""
    keep = {
        "name",
        "goal",
        "status",
        "result",
        "model",
        "scope",
        "attempts",
    }
    # Only keep dependencies from scope
    if "scope" in role:
        scope = role["scope"]
        role["scope"] = {"dependencies": scope.get("dependencies", [])}

    keys_to_remove = [k for k in list(role.keys()) if k not in keep]
    for k in keys_to_remove:
        del role[k]


def _apply_status_update(
    role: dict[str, Any],
    update: dict[str, Any],
    idx: int,
    updated: list[int],
    newly_failed: list[int],
    trimmed: list[int],
    plan: dict[str, Any],
) -> None:
    """Apply a single status update to a role."""
    new_status = update.get("status")

    if new_status:
        role["status"] = new_status
        updated.append(idx)

        if new_status in ("failed", "blocked"):
            newly_failed.append(idx)

    if "result" in update:
        role["result"] = update["result"]

    if new_status == "completed":
        _trim_role_fields(role)
        trimmed.append(idx)

        if "progress" not in plan:
            plan["progress"] = {}
        if "completedRoles" not in plan["progress"]:
            plan["progress"]["completedRoles"] = []

        name = role.get("name", "")
        if name and name not in plan["progress"]["completedRoles"]:
            plan["progress"]["completedRoles"].append(name)


def _compute_cascading_failures(
    roles: list[dict[str, Any]],
    dep_indices: list[list[int]],
    newly_failed: list[int],
) -> list[dict[str, Any]]:
    """Compute which roles should be skipped due to cascading failures."""
    cascaded: list[dict[str, Any]] = []
    if not newly_failed:
        return cascaded

    affected = get_transitive_deps(dep_indices, newly_failed)
    failed_set = set(newly_failed)

    for idx in sorted(affected):
        if roles[idx].get("status") == "pending":
            roles[idx]["status"] = "skipped"

            deps = dep_indices[idx]
            cause = next(
                (
                    dep
                    for dep in deps
                    if dep in failed_set
                    or roles[dep].get("status") in ("failed", "blocked", "skipped")
                ),
                deps[0] if deps else -1,
            )
            cascaded.append(
                {
                    "roleIndex": idx,
                    "name": roles[idx].get("name", ""),
                    "status": "skipped",
                    "reason": f"dependency on failed/blocked role {cause} ({roles[cause].get('name', '')})"
                    if cause >= 0
                    else "unknown dependency failure",
                }
            )

    return cascaded


def _validate_status_transition(
    current_status: str, new_status: str
) -> tuple[bool, str]:
    """Validate state machine transition. Returns (is_valid, error_message)."""
    valid_transitions = {
        "pending": {"in_progress"},
        "in_progress": {"completed", "failed"},
        "failed": {"pending"},  # retry resets to pending
        "completed": set(),  # terminal state
        "skipped": set(),  # terminal state
        "blocked": set(),  # terminal state
    }

    allowed = valid_transitions.get(current_status, set())
    if new_status in allowed:
        return (True, "")

    return (
        False,
        f"Invalid transition: {current_status} -> {new_status}. "
        f"Allowed: {', '.join(allowed) if allowed else 'none (terminal state)'}",
    )


def cmd_update_status(args: argparse.Namespace) -> NoReturn:
    """Batch update role statuses with progressive trimming and cascading failures."""
    plan_path = args.plan_path
    plan, roles, _name_index, dep_indices = _plan_with_deps(plan_path)

    updates = _read_stdin_json("Invalid JSON in stdin")

    if not isinstance(updates, list):
        error_exit("Expected JSON array in stdin")

    updated: list[int] = []
    trimmed: list[int] = []
    newly_failed: list[int] = []

    for update in updates:
        idx = update.get("roleIndex")
        if idx is None or idx >= len(roles):
            continue

        # Validate state transition if status is being changed
        new_status = update.get("status")
        if new_status:
            current_status = roles[idx].get("status", "pending")
            is_valid, error_msg = _validate_status_transition(
                current_status, new_status
            )
            if not is_valid:
                error_exit(f"Role {idx} ({roles[idx].get('name', '')}): {error_msg}")

        _apply_status_update(
            roles[idx], update, idx, updated, newly_failed, trimmed, plan
        )

    cascaded = _compute_cascading_failures(roles, dep_indices, newly_failed)
    atomic_write(plan_path, plan)

    output_json(
        {"ok": True, "updated": updated, "cascaded": cascaded, "trimmed": trimmed}
    )


# ============================================================================
# Build Commands
# ============================================================================


def _check_cycle(dep_indices: list[list[int]]) -> bool:
    """Check for cycles in dependencies."""
    visited: set[int] = set()
    stack: set[int] = set()

    def visit(idx: int) -> bool:
        if idx in stack:
            return True
        if idx in visited:
            return False
        visited.add(idx)
        stack.add(idx)
        for dep in dep_indices[idx]:
            if visit(dep):
                return True
        stack.remove(idx)
        return False

    return any(i not in visited and visit(i) for i in range(len(dep_indices)))


def _validate_required_fields(role: dict[str, Any], idx: int, name: str) -> list[str]:
    """Validate required top-level fields on a role brief."""
    issues: list[str] = []
    if not name:
        issues.append(f"Role {idx}: missing 'name'")
    if not role.get("goal"):
        issues.append(f"Role {idx} ({name}): missing 'goal'")
    if not role.get("model"):
        issues.append(f"Role {idx} ({name}): missing 'model'")
    scope = role.get("scope", {})
    if not scope.get("directories") and not scope.get("patterns"):
        issues.append(f"Role {idx} ({name}): scope needs 'directories' or 'patterns'")
    if not isinstance(scope.get("dependencies", []), list):
        issues.append(f"Role {idx} ({name}): scope.dependencies must be an array")
    return issues


_SURFACE_ONLY_PATTERNS = [
    re.compile(r"^\s*(grep|egrep|fgrep|rg)\s", re.IGNORECASE),  # Direct grep
    re.compile(r"\|\s*(grep|egrep|fgrep|rg)\s", re.IGNORECASE),  # Piped grep
    re.compile(
        r"^\s*(test\s+-[fedsrwx]|\[\s+-[fedsrwx]|\[\[\s+-[fedsrwx])", re.IGNORECASE
    ),  # File existence
]


def _is_surface_only(check: str) -> bool:
    """Return True if a check command is purely surface-level (grep, file existence).

    Surface-level checks include:
    - Direct grep commands (grep, egrep, fgrep, rg)
    - Piped grep as the final command (e.g., 'cat file | grep pattern')
    - File existence checks (test -f, [ -f ], [[ -f ]])

    Excludes legitimate patterns like:
    - wc -l (legitimate for counting output lines)
    - tail/head (legitimate for truncating output)
    - Compound commands with && (legitimate for exit-code checks)
    """
    # Strip leading shell constructs like `! ` (negation)
    stripped = re.sub(r"^[!\s]+", "", check.strip())

    # If there's && or || after the command, it's a compound command (not surface-only)
    if "&&" in stripped or "||" in stripped:
        return False

    return any(pattern.search(stripped) for pattern in _SURFACE_ONLY_PATTERNS)


def _validate_criteria(role: dict[str, Any], idx: int, name: str) -> list[str]:
    """Validate acceptanceCriteria on a role brief."""
    issues: list[str] = []
    criteria = role.get("acceptanceCriteria", [])
    if not criteria:
        issues.append(f"Role {idx} ({name}): missing 'acceptanceCriteria'")
    has_functional = False
    for j, ac in enumerate(criteria):
        if not ac.get("criterion"):
            issues.append(
                f"Role {idx} ({name}): acceptanceCriteria[{j}] missing 'criterion'"
            )
        check = ac.get("check", "")
        if not check:
            issues.append(
                f"Role {idx} ({name}): acceptanceCriteria[{j}] missing 'check'"
            )
        elif not _is_surface_only(check):
            has_functional = True
    if criteria and not has_functional:
        issues.append(
            f"Role {idx} ({name}): all acceptance criteria are surface-level — "
            "at least one must verify functional correctness "
            "(e.g., build, test, curl, or run command)"
        )
    return issues


def _validate_expert_ctx_entries(
    expert_ctx: list[Any], idx: int, name: str
) -> list[str]:
    """Validate individual expertContext entries."""
    issues: list[str] = []
    for j, ec in enumerate(expert_ctx):
        if not ec.get("expert"):
            issues.append(f"Role {idx} ({name}): expertContext[{j}] missing 'expert'")
        if not ec.get("artifact"):
            issues.append(f"Role {idx} ({name}): expertContext[{j}] missing 'artifact'")
    return issues


def _validate_assumptions(role: dict[str, Any], idx: int, name: str) -> list[str]:
    """Validate assumptions and rollbackTriggers consistency."""
    issues: list[str] = []
    assumptions = role.get("assumptions", [])
    for j, a in enumerate(assumptions):
        if not a.get("text"):
            issues.append(f"Role {idx} ({name}): assumptions[{j}] missing 'text'")
    blocking = sum(1 for a in assumptions if a.get("severity") == "blocking")
    if blocking > 0 and not role.get("rollbackTriggers", []):
        issues.append(
            f"Role {idx} ({name}): has blocking assumptions but no rollbackTriggers"
        )
    return issues


def _validate_expert_context(role: dict[str, Any], idx: int, name: str) -> list[str]:
    """Validate constraints, expertContext, and assumptions on a role brief."""
    issues: list[str] = []
    if not isinstance(role.get("constraints", []), list):
        issues.append(f"Role {idx} ({name}): 'constraints' must be an array")
    expert_ctx = role.get("expertContext", [])
    if not isinstance(expert_ctx, list):
        issues.append(f"Role {idx} ({name}): 'expertContext' must be an array")
    else:
        issues.extend(_validate_expert_ctx_entries(expert_ctx, idx, name))
    issues.extend(_validate_assumptions(role, idx, name))
    return issues


def _validate_role_brief(role: dict[str, Any], idx: int) -> list[str]:
    """Validate a single role brief structure."""
    name = role.get("name", "")
    issues: list[str] = []
    issues.extend(_validate_required_fields(role, idx, name))
    issues.extend(_validate_criteria(role, idx, name))
    issues.extend(_validate_expert_context(role, idx, name))
    return issues


def _validate_auxiliary_role(aux: dict[str, Any], idx: int) -> list[str]:
    """Validate an auxiliary role definition."""
    issues: list[str] = []
    name = aux.get("name", "")

    if not name:
        issues.append(f"AuxiliaryRole {idx}: missing 'name'")
    if not aux.get("type"):
        issues.append(f"AuxiliaryRole {idx} ({name}): missing 'type'")
    if not aux.get("goal"):
        issues.append(f"AuxiliaryRole {idx} ({name}): missing 'goal'")
    if not aux.get("trigger"):
        issues.append(f"AuxiliaryRole {idx} ({name}): missing 'trigger'")

    valid_types = {"pre-execution", "post-execution", "per-role"}
    if aux.get("type") and aux["type"] not in valid_types:
        issues.append(
            f"AuxiliaryRole {idx} ({name}): type must be one of {valid_types}"
        )

    valid_triggers = {
        "after-design",
        "before-execution",
        "after-role-complete",
        "after-all-roles-complete",
    }
    if aux.get("trigger") and aux["trigger"] not in valid_triggers:
        issues.append(
            f"AuxiliaryRole {idx} ({name}): trigger must be one of {valid_triggers}"
        )

    return issues


def _validate_verification_specs(
    specs: list[dict[str, Any]], role_names: set[str]
) -> list[str]:
    """Validate verificationSpecs schema when present."""
    issues: list[str] = []
    for i, spec in enumerate(specs):
        # Required fields: role, path, runCommand
        role = spec.get("role", "")
        if not role:
            issues.append(f"verificationSpecs[{i}]: missing 'role' field")
        elif role not in role_names:
            issues.append(f"verificationSpecs[{i}]: role '{role}' not found in roles")

        if not spec.get("path"):
            issues.append(f"verificationSpecs[{i}]: missing 'path' field")

        if not spec.get("runCommand"):
            issues.append(f"verificationSpecs[{i}]: missing 'runCommand' field")

        # Optional fields: properties (must be array if present), sha256 (computed later)
        properties = spec.get("properties")
        if properties is not None and not isinstance(properties, list):
            issues.append(f"verificationSpecs[{i}]: 'properties' must be an array")

    return issues


def _validate_role_count_and_names(roles: list[dict[str, Any]]) -> list[str]:
    """Check role count bounds and name uniqueness."""
    issues: list[str] = []
    if len(roles) == 0:
        issues.append("No roles in plan")
    elif len(roles) > 8:
        issues.append(f"Too many roles: {len(roles)} (max 8)")
    seen: set[str] = set()
    for r in roles:
        name = r.get("name", "")
        if name in seen:
            issues.append(f"Duplicate role name: {name}")
        seen.add(name)
    return issues


def _validate_dependency_graph(roles: list[dict[str, Any]]) -> list[str]:
    """Validate dependency references, cycles, and critical path depth."""
    issues: list[str] = []
    name_index = build_name_index(roles)
    for i, role in enumerate(roles):
        for dep in role.get("scope", {}).get("dependencies", []):
            if dep not in name_index:
                issues.append(
                    f"Role {i} ({role.get('name', '')}): "
                    f"dependency '{dep}' not found in roles"
                )
    dep_indices = resolve_dependencies(roles, name_index)
    has_cycle = _check_cycle(dep_indices)
    if has_cycle:
        issues.append("Cycle detected in role dependencies")
    if roles and not has_cycle:
        depths = compute_depths(roles, dep_indices)
        max_depth = max(depths.values()) if depths else 0
        if max_depth > 5:
            issues.append(f"Critical path depth too high: {max_depth} (max 5)")
    return issues


def _validate_structure(plan: dict[str, Any]) -> list[str]:
    """Run structural checks on plan. Returns list of issues."""
    issues: list[str] = []
    roles = plan.get("roles", [])
    issues.extend(_validate_role_count_and_names(roles))
    for i, role in enumerate(roles):
        issues.extend(_validate_role_brief(role, i))
    issues.extend(_validate_dependency_graph(roles))
    for i, aux in enumerate(plan.get("auxiliaryRoles", [])):
        issues.extend(_validate_auxiliary_role(aux, i))

    # Validate verificationSpecs if present (optional, backward compatible)
    verification_specs = plan.get("verificationSpecs")
    if verification_specs is not None:
        if not isinstance(verification_specs, list):
            issues.append("'verificationSpecs' must be an array")
        else:
            role_names = {r.get("name", "") for r in roles}
            issues.extend(_validate_verification_specs(verification_specs, role_names))

    return issues


def _compute_directory_overlaps(plan: dict[str, Any]) -> int:
    """Compute directoryOverlaps for concurrent role pairs."""
    roles = plan.get("roles", [])
    name_index = build_name_index(roles)
    dep_indices = resolve_dependencies(roles, name_index)

    overlaps_by_role = _compute_overlaps(roles, dep_indices)

    # Assign computed overlaps to each role
    for i, role in enumerate(roles):
        role["directoryOverlaps"] = overlaps_by_role.get(i, [])

    return len(roles)


def _compute_spec_checksums(plan: dict[str, Any]) -> None:
    """Compute SHA256 checksums for verification spec files.

    Modifies verificationSpecs entries in-place to add sha256 field.
    If a spec file doesn't exist, skips with no error (design may not have written it yet).
    """
    verification_specs = plan.get("verificationSpecs", [])
    if not verification_specs:
        return

    for spec in verification_specs:
        path = spec.get("path", "")
        if not path:
            continue

        # Compute SHA256 if file exists
        if os.path.isfile(path):
            try:
                with open(path, "rb") as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                spec["sha256"] = file_hash
            except OSError:
                # Skip files that can't be read (permissions, etc.)
                continue


def _validate_check_commands(plan: dict[str, Any]) -> list[str]:
    """Validate acceptance criteria check commands. Returns list of warnings."""
    warnings = []
    roles = plan.get("roles", [])

    for role_idx, role in enumerate(roles):
        role_name = role.get("name", f"role-{role_idx}")
        criteria = role.get("acceptanceCriteria", [])

        for crit_idx, criterion_obj in enumerate(criteria):
            check = criterion_obj.get("check", "")
            if not check:
                warnings.append(
                    f"{role_name} criterion {crit_idx}: empty check command"
                )
                continue

            # Validate Python checks
            valid, error = _validate_python_check(check)
            if not valid:
                warnings.append(f"{role_name} criterion {crit_idx}: {error}")

    return warnings


def cmd_finalize(args: argparse.Namespace) -> NoReturn:
    """Validate role brief structure and compute directory overlaps."""
    plan_path = args.plan_path
    plan = load_plan(plan_path)

    # Step 1: Validate structure
    issues = _validate_structure(plan)
    if issues:
        output_json({"ok": False, "error": "validation_failed", "issues": issues})

    # Validate-only mode
    if getattr(args, "validate_only", False):
        output_json({"ok": True, "validated": True})

    # Step 2: Compute directory overlaps
    computed = _compute_directory_overlaps(plan)

    # Step 2.5: Compute SHA256 checksums for verification specs (if present)
    _compute_spec_checksums(plan)

    # Step 2.6: Validate acceptance criteria check commands (non-blocking warning)
    check_warnings = _validate_check_commands(plan)

    # Step 3: Initialize role statuses
    for role in plan.get("roles", []):
        if "status" not in role:
            role["status"] = "pending"
        if "attempts" not in role:
            role["attempts"] = 0
        if "result" not in role:
            role["result"] = None

    # Step 4: Initialize progress
    if "progress" not in plan:
        plan["progress"] = {"completedRoles": []}

    # Single atomic write
    atomic_write(plan_path, plan)

    result = {
        "ok": True,
        "validated": True,
        "computedOverlaps": computed,
        "roleCount": len(plan.get("roles", [])),
        "auxiliaryCount": len(plan.get("auxiliaryRoles", [])),
    }
    if check_warnings:
        result["checkWarnings"] = check_warnings

    output_json(result)


# ============================================================================
# Validate Checks Command
# ============================================================================


def _update_fstring_depth(depth: int, char: str) -> int:
    """Update f-string brace depth based on character."""
    if char == "{":
        return depth + 1
    if char == "}" and depth > 0:
        return depth - 1
    return depth


def _find_closing_quote(check: str, start_pos: int, quote_char: str) -> int:
    """Find matching closing quote.

    Handles f-strings with nested quotes inside braces by tracking brace depth.
    Returns index of closing quote or -1 if not found.
    """
    is_fstring = start_pos >= 1 and check[start_pos - 1] == "f"
    pos = start_pos + 1
    depth = 0

    while pos < len(check):
        ch = check[pos]

        # Skip escaped characters in double-quoted strings
        if quote_char == '"' and ch == "\\" and pos + 1 < len(check):
            pos += 2
            continue

        # Track brace nesting in f-strings
        if is_fstring:
            depth = _update_fstring_depth(depth, ch)

        # Check for closing quote when not inside braces
        if ch == quote_char and depth == 0:
            return pos

        pos += 1

    return -1


def _extract_python_from_check(check: str) -> str | None:
    """Extract Python code from 'python3 -c ...' command.

    Returns the Python string if found, None otherwise.
    Simple heuristic: find 'python3 -c ' then extract until matching quote.
    """
    if "python3 -c" not in check:
        return None

    # Find the -c flag position
    c_flag_pos = check.find("-c")
    if c_flag_pos == -1:
        return None

    # Skip past '-c ' to find the quote
    start_pos = c_flag_pos + 2
    while start_pos < len(check) and check[start_pos] in (" ", "\t"):
        start_pos += 1

    if start_pos >= len(check):
        return None

    # Detect quote type
    quote_char = check[start_pos]
    if quote_char not in ("'", '"'):
        return None

    # Find matching closing quote
    end_pos = _find_closing_quote(check, start_pos, quote_char)
    if end_pos == -1:
        return None

    return check[start_pos + 1 : end_pos]


def _validate_python_check(check: str) -> tuple[bool, str | None]:
    """Validate Python inline check syntax.

    Returns (valid, error_message).
    """
    python_code = _extract_python_from_check(check)
    if python_code is None:
        return (True, None)  # Not a Python check, skip validation

    try:
        compile(python_code, "<check>", "exec")
        return (True, None)
    except SyntaxError as e:
        return (False, f"SyntaxError: {e.msg} at line {e.lineno}")
    except Exception as e:  # noqa: BLE001
        return (False, f"Compilation error: {e}")


def cmd_validate_checks(args: argparse.Namespace) -> NoReturn:
    """Validate acceptance criteria check commands.

    Extracts each acceptanceCriteria[].check, detects Python inline checks
    (python3 -c '...'), validates their syntax with compile(), and reports
    errors per role/criterion.

    JSON output: {ok: true/false, results: [{roleIndex, roleName, criterionIndex,
                 criterion, valid, error}]}
    """
    plan_path = args.plan_path
    plan = load_plan(plan_path)

    roles = plan.get("roles", [])
    results = []
    all_valid = True

    for role_idx, role in enumerate(roles):
        role_name = role.get("name", f"role-{role_idx}")
        criteria = role.get("acceptanceCriteria", [])

        for crit_idx, criterion_obj in enumerate(criteria):
            criterion = criterion_obj.get("criterion", "")
            check = criterion_obj.get("check", "")

            if not check:
                # Empty check is invalid
                results.append(
                    {
                        "roleIndex": role_idx,
                        "roleName": role_name,
                        "criterionIndex": crit_idx,
                        "criterion": criterion,
                        "valid": False,
                        "error": "Empty check command",
                    }
                )
                all_valid = False
                continue

            # Validate Python checks
            valid, error = _validate_python_check(check)
            results.append(
                {
                    "roleIndex": role_idx,
                    "roleName": role_name,
                    "criterionIndex": crit_idx,
                    "criterion": criterion,
                    "valid": valid,
                    "error": error,
                }
            )
            if not valid:
                all_valid = False

    output_json({"ok": all_valid, "results": results})


# ============================================================================
# Health Check Command
# ============================================================================


def _check_plan_json(design_dir: str) -> list[str]:
    """Check plan.json validity. Returns list of issues."""
    issues = []
    plan_path = os.path.join(design_dir, "plan.json")
    if not os.path.exists(plan_path):
        issues.append("plan.json not found")
        return issues

    try:
        with open(plan_path) as f:
            plan = json.load(f)
        if plan.get("schemaVersion") != 4:
            issues.append(
                f"Invalid schema version: {plan.get('schemaVersion')} (expected 4)"
            )
    except json.JSONDecodeError as e:
        issues.append(f"plan.json is not valid JSON: {e}")
    except OSError as e:
        issues.append(f"Cannot read plan.json: {e}")

    return issues


def _check_jsonl_file(
    file_path: str, required_fields: set[str], file_label: str
) -> tuple[list[str], list[str], int]:
    """Check JSONL file validity. Returns (issues, warnings, count)."""
    issues = []
    warnings = []
    count = 0

    if not os.path.exists(file_path):
        return (issues, warnings, count)

    try:
        with open(file_path) as f:
            line_num = 0
            for line in f:
                line_num += 1
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    count += 1
                    missing = required_fields - set(entry.keys())
                    if missing:
                        warnings.append(
                            f"{file_label} line {line_num}: missing fields {missing}"
                        )
                except json.JSONDecodeError:
                    warnings.append(f"{file_label} line {line_num}: invalid JSON")
    except OSError as e:
        issues.append(f"Cannot read {file_label}: {e}")

    return (issues, warnings, count)


def _check_symlinks(design_dir: str) -> tuple[list[str], list[str]]:
    """Check symlinks in design directory. Returns (issues, warnings)."""
    issues = []
    warnings = []

    try:
        for item in os.listdir(design_dir):
            item_path = os.path.join(design_dir, item)
            if os.path.islink(item_path):
                target = os.readlink(item_path)
                if not os.path.exists(item_path):
                    issues.append(f"Broken symlink: {item} -> {target}")
    except OSError as e:
        warnings.append(f"Cannot scan directory for symlinks: {e}")

    return (issues, warnings)


def cmd_health_check(args: argparse.Namespace) -> NoReturn:
    """Validate .design/ directory integrity.

    Checks:
    - plan.json exists and is valid JSON
    - memory.jsonl entries are valid (if file exists)
    - reflection.jsonl entries are valid (if file exists)
    - symlinks resolve (if any exist)
    """
    design_dir = args.design_dir.rstrip("/")
    all_issues = []
    all_warnings = []

    # Check if design directory exists
    if not os.path.exists(design_dir):
        error_exit(f"Design directory not found: {design_dir}")

    if not os.path.isdir(design_dir):
        error_exit(f"{design_dir} is not a directory")

    # Check plan.json
    all_issues.extend(_check_plan_json(design_dir))

    # Check memory.jsonl
    memory_path = os.path.join(design_dir, "memory.jsonl")
    mem_issues, mem_warnings, _ = _check_jsonl_file(
        memory_path, {"id", "category", "content", "timestamp"}, "memory.jsonl"
    )
    all_issues.extend(mem_issues)
    all_warnings.extend(mem_warnings)

    # Check reflection.jsonl
    reflection_path = os.path.join(design_dir, "reflection.jsonl")
    ref_issues, ref_warnings, _ = _check_jsonl_file(
        reflection_path,
        {"id", "skill", "goal", "outcome", "timestamp"},
        "reflection.jsonl",
    )
    all_issues.extend(ref_issues)
    all_warnings.extend(ref_warnings)

    # Check trace.jsonl
    trace_path = os.path.join(design_dir, "trace.jsonl")
    trace_issues, trace_warnings, _ = _check_jsonl_file(
        trace_path,
        {"id", "sessionId", "eventType", "timestamp"},
        "trace.jsonl",
    )
    all_issues.extend(trace_issues)
    all_warnings.extend(trace_warnings)

    # Check symlinks
    sym_issues, sym_warnings = _check_symlinks(design_dir)
    all_issues.extend(sym_issues)
    all_warnings.extend(sym_warnings)

    # Return results
    healthy = len(all_issues) == 0
    output_json(
        {"ok": True, "healthy": healthy, "issues": all_issues, "warnings": all_warnings}
    )


def _count_criteria_changes(
    criteria_a: dict[str, Any], criteria_b: dict[str, Any]
) -> tuple[int, int, int]:
    """Count criteria changes. Returns (added, removed, modified)."""
    added = sum(1 for c in criteria_b if c not in criteria_a)
    removed = sum(1 for c in criteria_a if c not in criteria_b)
    modified = sum(
        1
        for c in criteria_a
        if c in criteria_b and criteria_a[c].get("check") != criteria_b[c].get("check")
    )
    return (added, removed, modified)


def _compare_acceptance_criteria(
    role_a: dict[str, Any], role_b: dict[str, Any]
) -> list[str]:
    """Compare acceptance criteria between two roles. Returns change descriptions."""
    changes = []
    criteria_a = {c.get("criterion"): c for c in role_a.get("acceptanceCriteria", [])}
    criteria_b = {c.get("criterion"): c for c in role_b.get("acceptanceCriteria", [])}

    added, removed, modified = _count_criteria_changes(criteria_a, criteria_b)

    if added > 0:
        changes.append(f"+{added} acceptance criteria")
    if removed > 0:
        changes.append(f"-{removed} acceptance criteria")
    if modified > 0:
        changes.append(f"~{modified} acceptance criteria modified")

    return changes


def _compare_dependencies(role_a: dict[str, Any], role_b: dict[str, Any]) -> list[str]:
    """Compare dependencies between two roles. Returns change descriptions."""
    changes = []
    deps_a = set(role_a.get("scope", {}).get("dependencies", []))
    deps_b = set(role_b.get("scope", {}).get("dependencies", []))

    if deps_a != deps_b:
        added_deps = deps_b - deps_a
        removed_deps = deps_a - deps_b
        if added_deps:
            changes.append(f"+deps: {', '.join(added_deps)}")
        if removed_deps:
            changes.append(f"-deps: {', '.join(removed_deps)}")

    return changes


def _compare_role(role_a: dict[str, Any], role_b: dict[str, Any]) -> list[str]:
    """Compare two roles. Returns list of change descriptions."""
    changes = []

    if role_a.get("goal") != role_b.get("goal"):
        changes.append("goal modified")

    if role_a.get("status") != role_b.get("status"):
        changes.append(f"status: {role_a.get('status')} -> {role_b.get('status')}")

    changes.extend(_compare_acceptance_criteria(role_a, role_b))
    changes.extend(_compare_dependencies(role_a, role_b))

    return changes


def _find_modified_roles(
    roles_a: dict[str, dict[str, Any]], roles_b: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Find modified roles between two plans. Returns list of {role, changes}."""
    modified_roles = []
    for name in roles_a:
        if name not in roles_b:
            continue

        changes = _compare_role(roles_a[name], roles_b[name])
        if changes:
            modified_roles.append({"role": name, "changes": changes})

    return modified_roles


def _build_summary(
    added_count: int, removed_count: int, modified_count: int, goal_changed: bool
) -> str:
    """Build summary text from change counts."""
    parts = []
    if added_count > 0:
        parts.append(f"{added_count} roles added")
    if removed_count > 0:
        parts.append(f"{removed_count} roles removed")
    if modified_count > 0:
        parts.append(f"{modified_count} roles modified")
    if goal_changed:
        parts.append("goal changed")

    return ", ".join(parts) if parts else "no changes detected"


def _compute_plan_diff(
    plan_a: dict[str, Any], plan_b: dict[str, Any]
) -> dict[str, Any]:
    """Compute differences between two plans. Returns diff result dict."""
    roles_a = {r.get("name", ""): r for r in plan_a.get("roles", [])}
    roles_b = {r.get("name", ""): r for r in plan_b.get("roles", [])}

    added_roles = [name for name in roles_b if name not in roles_a]
    removed_roles = [name for name in roles_a if name not in roles_b]
    modified_roles = _find_modified_roles(roles_a, roles_b)
    goal_changed = plan_a.get("goal") != plan_b.get("goal")

    summary = _build_summary(
        len(added_roles), len(removed_roles), len(modified_roles), goal_changed
    )

    return {
        "ok": True,
        "summary": summary,
        "addedRoles": added_roles,
        "removedRoles": removed_roles,
        "modifiedRoles": modified_roles,
        "goalChanged": goal_changed,
    }


def cmd_plan_diff(args: argparse.Namespace) -> NoReturn:
    """Compare two plan.json files and output human-readable summary of changes.

    Compares:
    - Added/removed/modified roles
    - Changed acceptance criteria
    - Dependency changes
    - Status changes
    """
    plan_a = load_plan(args.plan_a)
    plan_b = load_plan(args.plan_b)

    result = _compute_plan_diff(plan_a, plan_b)
    output_json(result)


# ============================================================================
# Memory Commands
# ============================================================================


def _tokenize(text: str) -> set[str]:
    """Tokenize text for keyword matching: lowercase, split on non-alphanumeric."""
    if not text:
        return set()
    # Lowercase and split on whitespace/punctuation
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    # Filter out very short tokens (noise)
    return {t for t in tokens if len(t) > 2}


def _score_memory(
    entry: dict[str, Any], query_tokens: set[str], current_time: float
) -> float:
    """Score a memory entry by keyword overlap + recency decay + importance.

    Importance scale: 1-10 (10 = most important). Default: 5.
    Formula: keyword_score * recency_factor * (importance / 10)
    """
    # Keyword overlap score
    entry_keywords = set(entry.get("keywords", []))
    content_tokens = _tokenize(entry.get("content", ""))
    all_entry_tokens = entry_keywords.union(content_tokens)

    if not all_entry_tokens or not query_tokens:
        return 0.0

    overlap = len(query_tokens.intersection(all_entry_tokens))
    keyword_score = overlap / len(query_tokens)

    # Recency decay: entries lose 10% relevance per 30 days
    timestamp = _parse_timestamp(entry.get("timestamp", current_time))
    age_seconds = current_time - timestamp
    age_months = age_seconds / (30 * 24 * 60 * 60)
    recency_factor = 0.9**age_months

    # Importance factor: 1-10 scale, default 5 for backward compatibility
    importance = entry.get("importance", 5)
    importance_factor = importance / 10

    return keyword_score * recency_factor * importance_factor


def _format_memory_result(score: float, entry: dict[str, Any]) -> dict[str, Any]:
    """Format a memory entry for output."""
    return {
        "id": entry.get("id", ""),
        "category": entry.get("category", ""),
        "keywords": entry.get("keywords", []),
        "content": entry.get("content", ""),
        "source": entry.get("source", ""),
        "timestamp": _parse_timestamp(entry.get("timestamp", 0)),
        "goal_context": entry.get("goal_context", ""),
        "importance": entry.get("importance", 5),
        "usage_count": entry.get("usage_count", 0),
        "score": round(score, 3),
    }


def _rank_memories(
    entries: list[dict[str, Any]], query_tokens: set[str], limit: int
) -> list[dict[str, Any]]:
    """Score, rank, and return top memory entries."""
    current_time = time.time()
    scored = [
        (score, entry)
        for entry in entries
        if (score := _score_memory(entry, query_tokens, current_time)) > 0
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [_format_memory_result(score, entry) for score, entry in scored[:limit]]


def cmd_memory_search(args: argparse.Namespace) -> NoReturn:
    """Search memory.jsonl for relevant entries matching query keywords."""
    memory_path = args.memory_path
    parts = [args.goal or "", args.stack or "", args.keywords or ""]
    query = " ".join(p for p in parts if p)

    query_tokens = _tokenize(query)
    if not query_tokens:
        output_json({"ok": True, "memories": []})

    try:
        entries = _read_jsonl(memory_path)
    except OSError as e:
        error_exit(f"Error reading memory file: {e}")

    if not entries:
        output_json({"ok": True, "memories": []})

    output_json(
        {"ok": True, "memories": _rank_memories(entries, query_tokens, args.limit)}
    )


def _validate_memory_input(category: str, content: str, keywords_str: str) -> list[str]:
    """Validate memory add inputs. Returns list of keywords or exits on error."""
    valid_categories = {
        "pattern",
        "mistake",
        "convention",
        "approach",
        "failure",
        "procedure",
    }
    if category not in valid_categories:
        error_exit(f"Invalid category '{category}'. Must be one of: {valid_categories}")

    if not content:
        error_exit("Content is required")

    keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
    if not keywords:
        error_exit("At least one keyword is required")

    return keywords


def _ensure_parent_dir(path: str) -> None:
    """Create parent directory for a file if it does not exist."""
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent)


def _update_memory_importance(memory_path: str, entry_id: str, boost: bool) -> NoReturn:
    """Update importance of an existing memory entry."""
    if not os.path.exists(memory_path):
        error_exit(f"Memory file not found: {memory_path}")

    try:
        entries = _read_jsonl(memory_path)
    except OSError as e:
        error_exit(f"Error reading memory file: {e}")

    # Find and update entry
    updated = False
    new_importance = 5
    for entry in entries:
        if entry.get("id") == entry_id:
            current_importance = entry.get("importance", 5)
            new_importance = (
                min(10, current_importance + 1)
                if boost
                else max(1, current_importance - 1)
            )
            entry["importance"] = new_importance
            updated = True
            break

    if not updated:
        error_exit(f"Entry with id '{entry_id}' not found")

    # Rewrite file
    try:
        _ensure_parent_dir(memory_path)
        with open(memory_path, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
    except OSError as e:
        error_exit(f"Error writing memory file: {e}")

    output_json(
        {
            "ok": True,
            "id": entry_id,
            "importance": new_importance,
            "action": "boosted" if boost else "decayed",
        }
    )


def _add_new_memory_entry(
    memory_path: str,
    category: str,
    content: str,
    keywords_str: str,
    source: str,
    goal_context: str,
    importance: int,
) -> dict[str, Any]:
    """Create and append a new memory entry."""
    if importance < 1 or importance > 10:
        error_exit("Importance must be between 1 and 10 (inclusive)")

    keywords = _validate_memory_input(category, content, keywords_str)

    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": _now_iso(),
        "category": category,
        "keywords": keywords,
        "content": content,
        "source": source,
        "goal_context": goal_context,
        "importance": importance,
        "usage_count": 0,
    }

    try:
        _ensure_parent_dir(memory_path)
        with open(memory_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        error_exit(f"Error writing memory file: {e}")

    return entry


def cmd_memory_add(args: argparse.Namespace) -> NoReturn:
    """Add a new memory entry or update importance of existing entry.

    --boost: increase importance by 1 (capped at 10)
    --decay: decrease importance by 1 (floor at 1)
    --id: specify entry ID to update (required for boost/decay)
    """
    memory_path = args.memory_path
    boost = getattr(args, "boost", False)
    decay = getattr(args, "decay", False)
    entry_id = getattr(args, "id", None)

    # Mode: update existing entry importance
    if boost or decay:
        if not entry_id:
            error_exit("--id required when using --boost or --decay")
        _update_memory_importance(memory_path, entry_id, boost)
    else:
        # Mode: add new entry
        if not args.category:
            error_exit("--category is required for new entries")
        if not args.content:
            error_exit("--content is required for new entries")

        entry = _add_new_memory_entry(
            memory_path,
            args.category,
            args.content,
            args.keywords or "",
            args.source or "unknown",
            args.goal_context or "",
            args.importance,
        )

        output_json(
            {
                "ok": True,
                "id": entry["id"],
                "category": entry["category"],
                "keywords": entry["keywords"],
                "importance": entry["importance"],
            }
        )


def _apply_memory_feedback(
    entries: list[dict[str, Any]],
    role_outcomes: list[dict[str, Any]],
) -> dict[str, int]:
    """Apply boost/decay to memories based on role outcomes. Returns counts."""
    entry_map = {e.get("id"): e for e in entries}
    counts = {"boosted": 0, "decayed": 0, "unchanged": 0}

    for outcome in role_outcomes:
        memory_ids = outcome.get("memoryIds", [])
        succeeded = outcome.get("roleSucceeded", False)
        first_attempt = outcome.get("firstAttempt", True)

        for mid in memory_ids:
            if mid not in entry_map:
                continue
            entry = entry_map[mid]
            entry["usage_count"] = entry.get("usage_count", 0) + 1
            current = entry.get("importance", 5)

            if succeeded and first_attempt:
                entry["importance"] = min(10, current + 1)
                counts["boosted"] += 1
            elif not succeeded:
                entry["importance"] = max(1, current - 1)
                counts["decayed"] += 1
            else:
                counts["unchanged"] += 1

    return counts


def cmd_memory_feedback(args: argparse.Namespace) -> NoReturn:
    """Boost or decay memories based on role outcomes.

    Reads role outcomes from stdin as JSON array:
    [{"memoryIds": ["id1", "id2"], "roleSucceeded": true, "firstAttempt": true}]

    Memories injected into roles that succeeded first-attempt get boosted.
    Memories injected into roles that failed get decayed.
    Roles that succeeded on retry get no change (ambiguous signal).
    """
    memory_path = args.memory_path
    role_outcomes = _read_stdin_json(
        "Invalid JSON in stdin (expected array of role outcomes)"
    )

    if not isinstance(role_outcomes, list):
        error_exit("Expected JSON array of role outcomes")

    if not os.path.exists(memory_path):
        output_json({"ok": True, "boosted": 0, "decayed": 0, "unchanged": 0})

    try:
        entries = _read_jsonl(memory_path)
    except OSError as e:
        error_exit(f"Error reading memory file: {e}")

    counts = _apply_memory_feedback(entries, role_outcomes)

    try:
        _ensure_parent_dir(memory_path)
        with open(memory_path, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
    except OSError as e:
        error_exit(f"Error writing memory file: {e}")

    output_json({"ok": True, **counts})


# ============================================================================
# Reflection Commands
# ============================================================================


def cmd_reflection_add(args: argparse.Namespace) -> NoReturn:
    """Add a structured self-reflection entry to reflection.jsonl."""
    reflection_path = args.reflection_path
    skill = args.skill
    goal = args.goal
    outcome = args.outcome
    goal_achieved = args.goal_achieved

    if skill not in ("design", "execute", "research", "simplify"):
        error_exit(
            f"Invalid skill '{skill}'. Must be one of: design, execute, research, simplify"
        )

    if outcome not in ("completed", "partial", "failed", "aborted"):
        error_exit(
            f"Invalid outcome '{outcome}'. "
            "Must be one of: completed, partial, failed, aborted"
        )

    if not goal:
        error_exit("Goal is required")

    # Read evaluation from stdin (JSON object)
    evaluation = _read_stdin_json("Invalid JSON in stdin (expected evaluation object)")

    # Validate: if whatFailed is non-empty, promptFixes must also be non-empty
    what_failed = evaluation.get("whatFailed", [])
    prompt_fixes = evaluation.get("promptFixes", [])
    if what_failed and not prompt_fixes:
        error_exit(
            "whatFailed is non-empty but promptFixes is empty \u2014 reflection too vague. "
            "For each failure, write idealOutcome + promptFix per Self-Monitoring Step B."
        )

    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": _now_iso(),
        "skill": skill,
        "goal": goal,
        "outcome": outcome,
        "goalAchieved": goal_achieved,
        "evaluation": evaluation,
    }

    # Append to JSONL file
    try:
        _ensure_parent_dir(reflection_path)
        with open(reflection_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        error_exit(f"Error writing reflection file: {e}")

    output_json(
        {
            "ok": True,
            "id": entry["id"],
            "skill": skill,
            "outcome": outcome,
            "goalAchieved": goal_achieved,
        }
    )


def cmd_reflection_search(args: argparse.Namespace) -> NoReturn:
    """Search reflection.jsonl for relevant past reflections."""
    reflection_path = args.reflection_path
    skill_filter = args.skill
    limit = args.limit

    if not os.path.exists(reflection_path):
        output_json({"ok": True, "reflections": []})

    try:
        filter_fn = (lambda e: e.get("skill") == skill_filter) if skill_filter else None
        entries = _read_jsonl(reflection_path, filter_fn)
    except OSError as e:
        error_exit(f"Error reading reflection file: {e}")

    # Sort by timestamp descending (most recent first)
    entries.sort(key=lambda x: _parse_timestamp(x.get("timestamp", 0)), reverse=True)

    output_json({"ok": True, "reflections": entries[:limit]})


# ============================================================================
# Trace Commands
# ============================================================================

_VALID_TRACE_EVENT_TYPES = frozenset(
    {"spawn", "completion", "failure", "respawn", "skill-start", "skill-complete"}
)
_LEAD_LEVEL_EVENT_TYPES = frozenset({"skill-start", "skill-complete"})
_VALID_TRACE_SKILLS = frozenset({"design", "execute", "research", "simplify"})


def _parse_trace_payload(payload_str: str | None) -> dict[str, Any]:
    """Parse --payload string to dict. Calls error_exit on invalid input."""
    if not payload_str:
        return {}
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError as e:
        error_exit(f"Invalid JSON in --payload: {e}")
    if not isinstance(payload, dict):
        error_exit("--payload must be a JSON object (dict), not a scalar or array")
    return payload  # type: ignore[return-value]


def _validate_trace_args(event_type: str, skill: str, agent_name: str | None) -> None:
    """Validate trace-add arguments. Calls error_exit on invalid input."""
    if event_type not in _VALID_TRACE_EVENT_TYPES:
        error_exit(
            f"Invalid eventType '{event_type}'. "
            f"Must be one of: {', '.join(sorted(_VALID_TRACE_EVENT_TYPES))}"
        )
    if skill not in _VALID_TRACE_SKILLS:
        error_exit(
            f"Invalid skill '{skill}'. Must be one of: {', '.join(sorted(_VALID_TRACE_SKILLS))}"
        )
    if event_type not in _LEAD_LEVEL_EVENT_TYPES and not agent_name:
        error_exit(
            f"--agent is required for event type '{event_type}'. "
            "Only skill-start and skill-complete are lead-level events."
        )


def _write_trace_entry(trace_path: str, entry: dict[str, Any]) -> None:
    """Append entry to trace.jsonl. Raises OSError on failure."""
    _ensure_parent_dir(trace_path)
    with open(trace_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def cmd_trace_add(args: argparse.Namespace) -> NoReturn:
    """Append one trace event to trace.jsonl.

    Generates id and timestamp automatically. Returns {ok: true, id: uuid}.
    Gracefully degrades: if write fails, returns {ok: false, error: ...} but
    never exits 1 (always exits 0).
    """
    event_type = args.event
    agent_name = args.agent
    _validate_trace_args(event_type, args.skill, agent_name)
    payload = _parse_trace_payload(args.payload)

    entry: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "timestamp": _now_iso(),
        "sessionId": args.session_id,
        "skill": args.skill,
        "eventType": event_type,
        "payload": payload,
    }
    if agent_name is not None:
        entry["agentName"] = agent_name
    if args.role is not None:
        entry["agentRole"] = args.role

    try:
        _write_trace_entry(args.trace_path, entry)
    except OSError as e:
        # Always exit 0 — trace failures must never break skill execution
        sys.stdout.write(
            json.dumps({"ok": False, "error": f"Trace write failed: {e}"}, indent=2)
            + "\n"
        )
        sys.exit(0)

    output_json({"ok": True, "id": entry["id"]})


def _trace_event_matches(
    entry: dict[str, Any],
    session_id: str | None,
    skill: str | None,
    event: str | None,
    agent: str | None,
) -> bool:
    """Return True if entry matches all provided filters (AND logic)."""
    if session_id and entry.get("sessionId") != session_id:
        return False
    if skill and entry.get("skill") != skill:
        return False
    if event and entry.get("eventType") != event:
        return False
    return not (agent and entry.get("agentName") != agent)


def _load_trace_events(
    trace_path: str,
    session_id: str | None,
    skill: str | None,
    event: str | None,
    agent: str | None,
) -> list[dict[str, Any]]:
    """Load and filter trace events from file. Returns [] if file missing."""
    try:
        return _read_jsonl(
            trace_path,
            lambda e: _trace_event_matches(e, session_id, skill, event, agent),
        )
    except OSError as e:
        error_exit(f"Error reading trace file: {e}")


def cmd_trace_search(args: argparse.Namespace) -> NoReturn:
    """Search trace events with optional filters.

    Returns {ok: true, events: [...], count: N}.
    All filters are optional and AND-combined.
    Returns empty list (not error) if file missing.
    """
    events = _load_trace_events(
        args.trace_path,
        getattr(args, "session_id", None),
        getattr(args, "skill", None),
        getattr(args, "event", None),
        getattr(args, "agent", None),
    )
    events.sort(key=lambda x: _parse_timestamp(x.get("timestamp", 0)), reverse=True)
    limited = events[: args.limit]
    output_json({"ok": True, "events": limited, "count": len(limited)})


def _aggregate_trace_stats(
    events: list[dict[str, Any]],
) -> tuple[set[str], set[str], dict[str, int], dict[str, Any] | None]:
    """Aggregate session/agent/type stats and find latest event."""
    sessions: set[str] = set()
    agents: set[str] = set()
    events_by_type: dict[str, int] = {}
    latest_event: dict[str, Any] | None = None
    latest_ts: float = 0.0

    for ev in events:
        sid = ev.get("sessionId", "")
        if sid:
            sessions.add(sid)
        agent = ev.get("agentName")
        if agent:
            agents.add(agent)
        etype = ev.get("eventType", "unknown")
        events_by_type[etype] = events_by_type.get(etype, 0) + 1
        ts = _parse_timestamp(ev.get("timestamp", 0))
        if ts > latest_ts:
            latest_ts = ts
            latest_event = ev

    return sessions, agents, events_by_type, latest_event


def cmd_trace_summary(args: argparse.Namespace) -> NoReturn:
    """Format trace data for human-readable display.

    Returns aggregate stats: sessionCount, eventsByType, agentCount, latestSession.
    If --session-id given, shows that session only.
    """
    session_id_filter = getattr(args, "session_id", None)
    events = _load_trace_events(args.trace_path, session_id_filter, None, None, None)

    if not events and not os.path.exists(args.trace_path):
        output_json(
            {
                "ok": True,
                "sessionCount": 0,
                "eventsByType": {},
                "agentCount": 0,
                "latestSession": None,
            }
        )

    sessions, agents, events_by_type, latest_event = _aggregate_trace_stats(events)

    latest_session = None
    if latest_event:
        session_events = [
            e for e in events if e.get("sessionId") == latest_event.get("sessionId")
        ]
        latest_session = {
            "sessionId": latest_event.get("sessionId"),
            "skill": latest_event.get("skill"),
            "startTime": min(
                (e.get("timestamp", "") for e in session_events), default=""
            ),
            "eventCount": len(session_events),
        }

    output_json(
        {
            "ok": True,
            "sessionCount": len(sessions),
            "eventsByType": events_by_type,
            "agentCount": len(agents),
            "latestSession": latest_session,
        }
    )


def cmd_trace_validate(args: argparse.Namespace) -> NoReturn:
    """Schema validation for trace.jsonl entries.

    Checks required fields on each line. Returns {ok: true/false, warnings: [...], entryCount: N}.
    Missing file is not an error (returns ok=true, empty result).
    """
    trace_path = args.trace_path
    required_fields = {"id", "timestamp", "sessionId", "skill", "eventType", "payload"}
    issues, warnings, entry_count = _check_jsonl_file(
        trace_path, required_fields, "trace.jsonl"
    )
    if issues:
        error_exit(issues[0])
    output_json({"ok": True, "warnings": warnings, "entryCount": entry_count})


# ============================================================================
# Validation Commands
# ============================================================================


def cmd_expert_validate(args: argparse.Namespace) -> NoReturn:
    """Validate expert artifact JSON against minimal required schema.

    Required fields: summary, verificationProperties
    """
    artifact_path = args.artifact_path
    data = _load_json_file(artifact_path, "artifact")

    # Check required fields
    missing = []
    if "summary" not in data:
        missing.append("summary")
    if "verificationProperties" not in data:
        missing.append("verificationProperties")

    if missing:
        error_exit(f"Missing required fields: {', '.join(missing)}")

    # Validate verificationProperties is a list
    if not isinstance(data["verificationProperties"], list):
        error_exit("verificationProperties must be an array")

    output_json({"ok": True, "valid": True})


VALID_FAILURE_CLASSES = {
    "spec-disobey",
    "step-repetition",
    "context-loss",
    "termination-unaware",
    "ignored-peer-input",
    "task-derailment",
    "premature-termination",
    "incorrect-verification",
    "no-verification",
    "reasoning-action-mismatch",
}

PROMPT_FIX_FIELDS = {"section", "problem", "idealOutcome", "fix", "failureClass"}


def _validate_prompt_fixes(fixes: list[Any]) -> list[str]:
    """Validate promptFixes entries have required subfields and valid failureClass."""
    warnings: list[str] = []
    for i, fix in enumerate(fixes):
        if not isinstance(fix, dict):
            continue
        missing = PROMPT_FIX_FIELDS - fix.keys()
        if missing:
            warnings.append(f"promptFixes[{i}] missing: {', '.join(missing)}")
        fc = fix.get("failureClass", "")
        if fc and fc not in VALID_FAILURE_CLASSES:
            warnings.append(f"promptFixes[{i}] invalid failureClass: {fc}")
    return warnings


def cmd_reflection_validate(args: argparse.Namespace) -> NoReturn:
    """Validate reflection evaluation JSON against schema.

    Reads evaluation JSON from stdin.
    Required fields: promptFixes (array), stepsSkipped (array),
    instructionsIgnored (array), whatWorked (array), whatFailed (array).
    Legacy field doNextTime (array) accepted but not required.
    """
    _ = args  # Unused but required for dispatch compatibility
    evaluation = _read_stdin_json("Invalid JSON in evaluation", include_error=True)

    required = [
        "promptFixes",
        "stepsSkipped",
        "instructionsIgnored",
        "whatWorked",
        "whatFailed",
    ]
    has_legacy = all(
        f in evaluation for f in ["whatWorked", "whatFailed", "doNextTime"]
    )
    has_new = all(f in evaluation for f in required)

    if not has_legacy and not has_new:
        error_exit(
            f"Missing required fields. Need: {', '.join(required)} "
            "(or legacy: whatWorked, whatFailed, doNextTime)"
        )

    array_fields = [*required, "doNextTime", "acGradients"]
    invalid = [
        f
        for f in array_fields
        if f in evaluation and not isinstance(evaluation[f], list)
    ]
    if invalid:
        error_exit(f"Fields must be arrays: {', '.join(invalid)}")

    warnings = _validate_prompt_fixes(evaluation.get("promptFixes", []))
    output_json({"ok": True, "valid": True, "warnings": warnings})


def _validate_json_schema(
    data: dict[str, Any], required_fields: list[str], field_types: dict[str, type]
) -> list[str]:
    """Shared JSON schema validation helper.

    Args:
        data: JSON object to validate
        required_fields: List of required field names
        field_types: Dict of field_name -> expected_type

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Check required fields
    missing = [f for f in required_fields if f not in data]
    if missing:
        errors.append(f"Missing required fields: {', '.join(missing)}")

    # Check types
    for field, expected_type in field_types.items():
        if field in data and not isinstance(data[field], expected_type):
            errors.append(
                f"Field '{field}' must be {expected_type.__name__}, got {type(data[field]).__name__}"
            )

    return errors


def _validate_single_challenger_issue(issue: dict[str, Any], index: int) -> list[str]:
    """Validate a single challenger issue object."""
    errors: list[str] = []

    required = [
        "category",
        "severity",
        "description",
        "affectedRoles",
        "recommendation",
    ]
    missing = [f for f in required if f not in issue]
    if missing:
        errors.append(f"issues[{index}]: missing {', '.join(missing)}")

    valid_categories = {
        "scope-gap",
        "overlap",
        "invalid-assumption",
        "missing-dependency",
        "criteria-gap",
        "constraint-conflict",
    }
    if "category" in issue and issue["category"] not in valid_categories:
        errors.append(f"issues[{index}]: invalid category '{issue['category']}'")

    valid_severities = {"blocking", "high-risk", "low-risk"}
    if "severity" in issue and issue["severity"] not in valid_severities:
        errors.append(f"issues[{index}]: invalid severity '{issue['severity']}'")

    return errors


def _validate_challenger_issues(data: dict[str, Any]) -> list[str]:
    """Validate challenger report issues array."""
    errors: list[str] = []
    if "issues" not in data:
        return errors

    for i, issue in enumerate(data["issues"]):
        if not isinstance(issue, dict):
            errors.append(f"issues[{i}] must be an object")
            continue
        errors.extend(_validate_single_challenger_issue(issue, i))

    return errors


def _validate_aux_challenger(data: dict[str, Any]) -> list[str]:
    errors = _validate_json_schema(
        data, ["issues", "summary"], {"issues": list, "summary": str}
    )
    if not errors:
        errors.extend(_validate_challenger_issues(data))
    return errors


def _validate_aux_integration_verifier(data: dict[str, Any]) -> list[str]:
    errors = _validate_json_schema(
        data,
        [
            "status",
            "acceptanceCriteria",
            "crossRoleIssues",
            "testResults",
            "endToEndVerification",
            "summary",
        ],
        {
            "status": str,
            "acceptanceCriteria": list,
            "crossRoleIssues": list,
            "testResults": dict,
            "endToEndVerification": dict,
            "summary": str,
        },
    )
    if not errors and "status" in data and data["status"] not in {"PASS", "FAIL"}:
        errors.append(f"status must be 'PASS' or 'FAIL', got '{data['status']}'")
    return errors


_AUX_VALIDATORS: dict[str, Any] = {
    "challenger": _validate_aux_challenger,
    "scout": lambda d: _validate_json_schema(
        d,
        ["scopeAreas", "discrepancies", "summary"],
        {"scopeAreas": list, "discrepancies": list, "summary": str},
    ),
    "integration-verifier": _validate_aux_integration_verifier,
    "regression-checker": lambda d: _validate_json_schema(
        d,
        ["passed", "changes", "regressions", "summary"],
        {"passed": bool, "changes": list, "regressions": list, "summary": str},
    ),
    "memory-curator": lambda d: _validate_json_schema(
        d, ["memories", "summary"], {"memories": list, "summary": str}
    ),
}


def _validate_auxiliary_by_type(aux_type: str, data: dict[str, Any]) -> list[str]:
    """Dispatch validation based on auxiliary type."""
    validator = _AUX_VALIDATORS.get(aux_type)
    if validator is None:
        return [
            f"Unknown auxiliary type: {aux_type}. Valid types: {', '.join(sorted(_AUX_VALIDATORS))}"
        ]
    return validator(data)


def _build_artifact_summary(aux_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """Build artifact summary for display."""
    summary = {"type": aux_type, "summary": data.get("summary", "")}

    if aux_type == "challenger":
        summary["issueCount"] = len(data.get("issues", []))
        blocking = sum(
            1 for i in data.get("issues", []) if i.get("severity") == "blocking"
        )
        summary["blockingCount"] = blocking
    elif aux_type == "scout":
        summary["discrepancyCount"] = len(data.get("discrepancies", []))
    elif aux_type == "integration-verifier":
        summary["status"] = data.get("status", "UNKNOWN")
    elif aux_type == "regression-checker":
        summary["passed"] = data.get("passed", False)
        summary["regressionCount"] = len(data.get("regressions", []))
    elif aux_type == "memory-curator":
        summary["memoryCount"] = len(data.get("memories", []))

    return summary


def cmd_validate_auxiliary_report(args: argparse.Namespace) -> NoReturn:
    """Validate auxiliary report JSON against type-specific schema.

    Schemas match execute/SKILL.md:
    - challenger: {issues: [{category, severity, description, affectedRoles, recommendation}], summary}
    - scout: {scopeAreas: [...], discrepancies: [...], summary}
    - integration-verifier: {status, verificationSpecs, acceptanceCriteria, crossRoleIssues, testResults, endToEndVerification, summary}
    - regression-checker: {passed: bool, changes: [...], regressions: [...], summary}
    - memory-curator: {memories: [...], summary}
    """
    artifact_path = args.artifact_path
    aux_type = args.type
    data = _load_json_file(artifact_path, "artifact")

    errors = _validate_auxiliary_by_type(aux_type, data)
    if errors:
        error_exit(f"Schema validation failed: {'; '.join(errors)}")

    artifact_summary = _build_artifact_summary(aux_type, data)
    output_json({"ok": True, "valid": True, "artifactSummary": artifact_summary})


def _validate_acceptance_criteria(data: dict[str, Any]) -> list[str]:
    """Validate acceptanceCriteria array structure."""
    errors: list[str] = []
    if "acceptanceCriteria" not in data:
        return errors

    for i, criterion in enumerate(data["acceptanceCriteria"]):
        if not isinstance(criterion, dict):
            errors.append(f"acceptanceCriteria[{i}] must be an object")
            continue
        required = ["criterion", "passed", "evidence"]
        missing = [f for f in required if f not in criterion]
        if missing:
            errors.append(f"acceptanceCriteria[{i}]: missing {', '.join(missing)}")

    return errors


def _validate_worker_optional_fields(data: dict[str, Any]) -> list[str]:
    """Validate optional worker completion fields."""
    errors: list[str] = []
    if "keyDecisions" in data and not isinstance(data["keyDecisions"], list):
        errors.append("keyDecisions must be an array")
    if "contextForDependents" in data and not isinstance(
        data["contextForDependents"], str
    ):
        errors.append("contextForDependents must be a string")
    return errors


def cmd_worker_completion_validate(args: argparse.Namespace) -> NoReturn:
    """Validate worker completion report JSON against schema.

    Schema (from execute/SKILL.md worker protocol):
    {
        role: string,
        achieved: bool,
        filesChanged: [string],
        acceptanceCriteria: [{criterion: string, passed: bool, evidence: string}],
        keyDecisions: [string],
        contextForDependents: string
    }

    Reads JSON from stdin.
    """
    _ = args  # Unused but required for dispatch compatibility

    data = _read_stdin_json("Invalid JSON in worker completion", include_error=True)

    errors = _validate_json_schema(
        data,
        ["role", "achieved", "filesChanged", "acceptanceCriteria"],
        {
            "role": str,
            "achieved": bool,
            "filesChanged": list,
            "acceptanceCriteria": list,
        },
    )

    if not errors:
        errors.extend(_validate_acceptance_criteria(data))
        errors.extend(_validate_worker_optional_fields(data))

    if errors:
        error_exit(f"Schema validation failed: {'; '.join(errors)}")

    output_json({"ok": True, "valid": True})


def _load_and_validate_research_structure(
    research_path: str,
) -> dict[str, Any]:
    """Load and validate research.json top-level structure."""
    data = _load_json_file(research_path, "research file")

    if data.get("schemaVersion") != 1:
        error_exit(
            f"Invalid schemaVersion: expected 1, got {data.get('schemaVersion')}"
        )

    required = ["goal", "sections", "recommendations", "contradictions"]
    missing = [f for f in required if f not in data]
    if missing:
        error_exit(f"Missing required fields: {', '.join(missing)}")

    if not isinstance(data.get("sections", {}), dict):
        error_exit("sections must be an object")

    if not isinstance(data.get("recommendations", []), list):
        error_exit("recommendations must be an array")

    return data


def _validate_research_recommendation(rec: dict[str, Any], index: int) -> None:
    """Validate a single recommendation entry."""
    valid_actions = {"adopt", "adapt", "investigate", "defer", "reject"}
    valid_confidence = {"high", "medium", "low"}
    valid_effort = {"trivial", "small", "medium", "large", "transformative"}

    required = ["action", "scope", "reasoning", "confidence", "effort"]
    missing = [f for f in required if f not in rec]
    if missing:
        error_exit(f"Recommendation {index}: missing fields {', '.join(missing)}")

    for field, valid_set in [
        ("action", valid_actions),
        ("confidence", valid_confidence),
        ("effort", valid_effort),
    ]:
        value = rec.get(field)
        if value not in valid_set:
            error_exit(
                f"Recommendation {index}: invalid {field} '{value}'. "
                f"Must be one of: {', '.join(sorted(valid_set))}"
            )

    action = rec.get("action")
    if action in ("adopt", "adapt") and not rec.get("designGoal"):
        error_exit(
            f"Recommendation {index}: designGoal is required when action is '{action}'"
        )


def _validate_research_design_handoff(handoff: list[dict[str, Any]]) -> None:
    """Validate designHandoff array entries."""
    required_fields = ["source", "element", "material", "usage"]
    valid_sources = {
        "reference-material",
        "codebase-analysis",
        "expert-finding",
        "literature",
    }
    for i, block in enumerate(handoff):
        if not isinstance(block, dict):
            error_exit(f"designHandoff[{i}]: must be an object")
        missing = [f for f in required_fields if f not in block]
        if missing:
            error_exit(f"designHandoff[{i}]: missing fields {', '.join(missing)}")
        source = block.get("source")
        if source not in valid_sources:
            error_exit(
                f"designHandoff[{i}]: invalid source '{source}'. "
                f"Must be one of: {', '.join(sorted(valid_sources))}"
            )
        if not isinstance(block.get("material"), (str, list, dict)):
            error_exit(f"designHandoff[{i}]: material must be string, array, or object")


def cmd_research_validate(args: argparse.Namespace) -> NoReturn:
    """Validate research.json schema.

    Validates schemaVersion, required fields, recommendations structure,
    and optional designHandoff array.
    """
    data = _load_and_validate_research_structure(args.research_path)

    recommendations = data.get("recommendations", [])
    for i, rec in enumerate(recommendations):
        _validate_research_recommendation(rec, i)

    handoff = data.get("designHandoff")
    handoff_count = 0
    if handoff is not None:
        if not isinstance(handoff, list):
            error_exit("designHandoff must be an array")
        _validate_research_design_handoff(handoff)
        handoff_count = len(handoff)

    output_json(
        {
            "ok": True,
            "recommendationCount": len(recommendations),
            "sectionCount": len(data.get("sections", {})),
            "designHandoffCount": handoff_count,
            "validated": True,
        }
    )


_ACTION_PRIORITY = {"adopt": 0, "adapt": 1, "investigate": 2, "defer": 3, "reject": 4}


def _research_verdict(recommendations: list[dict[str, Any]]) -> str:
    """Compute overall verdict from recommendation actions (priority order)."""
    for action in ("adopt", "adapt", "investigate", "defer", "reject"):
        if any(r.get("action") == action for r in recommendations):
            return action
    return "unknown"


def _research_suggested_goal(sorted_recs: list[dict[str, Any]]) -> str | None:
    """Return designGoal from first adopt/adapt recommendation, or None."""
    for rec in sorted_recs:
        if rec.get("action") in ("adopt", "adapt") and rec.get("designGoal"):
            return rec["designGoal"]  # type: ignore[return-value]
    return None


def cmd_research_summary(args: argparse.Namespace) -> NoReturn:
    """Extract summary from research.json for display.

    Returns recommendation count, section count, top recommendations with designGoal.
    """
    data = _load_json_file(args.research_path, "research file")

    recommendations = data.get("recommendations", [])
    sections = data.get("sections", {})
    contradictions = data.get("contradictions", [])
    research_gaps = data.get("researchGaps", [])
    design_handoff = data.get("designHandoff", [])

    sorted_recs = sorted(
        recommendations,
        key=lambda r: _ACTION_PRIORITY.get(r.get("action", "defer"), 99),
    )
    top_recommendations = [
        {
            "action": r.get("action", ""),
            "scope": r.get("scope", ""),
            "designGoal": r.get("designGoal", ""),
            "confidence": r.get("confidence", ""),
        }
        for r in sorted_recs[:3]
    ]

    output_json(
        {
            "ok": True,
            "verdict": _research_verdict(recommendations),
            "suggestedDesignGoal": _research_suggested_goal(sorted_recs),
            "recommendationCount": len(recommendations),
            "topRecommendations": top_recommendations,
            "sectionCount": len(sections),
            "contradictionCount": len(contradictions),
            "researchGapCount": len(research_gaps),
            "designHandoffCount": len(design_handoff),
        }
    )


def _score_and_format_memories(
    memories: list[dict[str, Any]], goal: str
) -> list[dict[str, Any]]:
    """Score memories by relevance and format for display."""
    query_tokens = _tokenize(goal)
    current_time = time.time()

    # Score and sort using canonical _score_memory (proper tokenization)
    scored = [(mem, _score_memory(mem, query_tokens, current_time)) for mem in memories]
    scored.sort(key=lambda x: x[1], reverse=True)
    top_memories = scored[:5]

    # Format for display
    entries = []
    for mem, score in top_memories:
        entries.append(
            {
                "category": mem.get("category", "unknown"),
                "content": mem.get("content", ""),
                "importance": mem.get("importance", 5),
                "score": round(score, 2),
            }
        )

    return entries


def cmd_memory_summary(args: argparse.Namespace) -> NoReturn:
    """Format memory injection summary for user display.

    Searches memory.jsonl and formats top results in human-readable format.
    """
    memory_path = args.memory_path
    goal = args.goal or ""

    # If memory file doesn't exist, return empty result
    if not os.path.exists(memory_path):
        output_json(
            {"ok": True, "summary": "No memory file found", "count": 0, "entries": []}
        )

    # Load memories
    try:
        memories = _read_jsonl(memory_path)
    except OSError:
        memories = []
    if not memories:
        output_json(
            {"ok": True, "summary": "No memories found", "count": 0, "entries": []}
        )

    # Score and format
    entries = _score_and_format_memories(memories, goal)
    summary_text = f"Found {len(memories)} memories, showing top {len(entries)}"

    output_json(
        {
            "ok": True,
            "summary": summary_text,
            "count": len(entries),
            "entries": entries,
        }
    )


def _filter_memories(
    memories: list[dict[str, Any]],
    category_filter: str | None,
    keyword_filter: str | None,
) -> list[dict[str, Any]]:
    """Filter memories by category and keyword."""
    filtered = []
    for mem in memories:
        if category_filter and mem.get("category") != category_filter:
            continue

        if keyword_filter:
            entry_keywords = mem.get("keywords", [])
            if isinstance(entry_keywords, str):
                entry_keywords = [entry_keywords]
            if not any(keyword_filter.lower() in k.lower() for k in entry_keywords):
                continue

        filtered.append(mem)
    return filtered


def _format_memory_for_review(mem: dict[str, Any]) -> dict[str, Any]:
    """Format a single memory entry for human-readable display."""
    raw_ts = mem.get("timestamp", 0)
    ts = _parse_timestamp(raw_ts)
    date_str = time.strftime("%Y-%m-%d", time.localtime(ts)) if ts else "unknown"

    return {
        "id": mem.get("id", ""),
        "category": mem.get("category", "unknown"),
        "importance": mem.get("importance", 5),
        "usage_count": mem.get("usage_count", 0),
        "date": date_str,
        "keywords": mem.get("keywords", []),
        "content": mem.get("content", ""),
        "source": mem.get("source", ""),
    }


def _read_recent_reflections(design_dir: str) -> list[dict[str, Any]]:
    """Read last 3 reflections with structured detail."""
    reflection_path = os.path.join(design_dir, "reflection.jsonl")
    try:
        entries = _read_jsonl(reflection_path)
    except OSError:
        return []
    entries.sort(key=lambda x: _parse_timestamp(x.get("timestamp", 0)), reverse=True)
    results: list[dict[str, Any]] = []
    for ref in entries[:3]:
        skill = ref.get("skill", "unknown")
        outcome = ref.get("outcome", "unknown")
        goal = ref.get("goal", "")
        status = "succeeded" if ref.get("goalAchieved", False) else "failed"
        evaluation = ref.get("evaluation", {})
        do_next_time = evaluation.get("doNextTime", [])
        what_failed = evaluation.get("whatFailed", [])
        prompt_fixes = evaluation.get("promptFixes", [])
        high_value = evaluation.get("highValueInstructions", [])
        entry: dict[str, Any] = {
            "summary": f"{skill}: {outcome} ({status})",
            "goal": goal,
            "doNextTime": do_next_time,
            "whatFailed": what_failed,
            "promptFixes": prompt_fixes,
        }
        if high_value:
            entry["highValueInstructions"] = high_value
        results.append(entry)
    return results


def _extract_unresolved_improvements(design_dir: str) -> list[dict[str, Any]]:
    """Extract and deduplicate promptFixes + doNextTime from recent reflections.

    Returns actionable items sorted failures-first (OPRO ascending pattern:
    items from failed runs surface before items from successful runs,
    making the improvement direction visible).
    Deduped by normalized text similarity.
    """
    reflection_path = os.path.join(design_dir, "reflection.jsonl")
    try:
        entries = _read_jsonl(reflection_path)
    except OSError:
        return []

    entries.sort(key=lambda x: _parse_timestamp(x.get("timestamp", 0)), reverse=True)

    # Collect items from last 5 reflections, tagged with success/failure
    raw_items: list[dict[str, Any]] = []
    for ref in entries[:5]:
        skill = ref.get("skill", "unknown")
        goal_achieved = ref.get("goalAchieved", False)
        evaluation = ref.get("evaluation", {})
        for item in evaluation.get("promptFixes", []):
            fix_text = item if isinstance(item, str) else item.get("fix", str(item))
            failure_class = (
                "" if isinstance(item, str) else item.get("failureClass", "")
            )
            raw_items.append(
                {
                    "skill": skill,
                    "type": "promptFix",
                    "text": fix_text,
                    "failureClass": failure_class,
                    "fromFailedRun": not goal_achieved,
                }
            )
        for item in evaluation.get("doNextTime", []):
            raw_items.append(
                {
                    "skill": skill,
                    "type": "doNextTime",
                    "text": item,
                    "failureClass": "",
                    "fromFailedRun": not goal_achieved,
                }
            )

    # Deduplicate by normalized prefix (first 60 chars lowercase, stripped)
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in raw_items:
        key = item["text"][:60].lower().strip()
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    # OPRO ascending sort: failures first, then successes
    deduped.sort(key=lambda x: (not x["fromFailedRun"], x["type"] != "promptFix"))

    return deduped


def _read_plan_status(design_dir: str) -> str:
    """Read current plan completion status."""
    plan_path = os.path.join(design_dir, "plan.json")
    if not os.path.exists(plan_path):
        return ""

    try:
        with open(plan_path) as f:
            plan = json.load(f)
            roles = plan.get("roles", [])
            completed = sum(1 for r in roles if r.get("status") == "completed")
            total = len(roles)
            return f"Current plan: {completed}/{total} roles completed"
    except (json.JSONDecodeError, OSError):
        return "Plan file exists but cannot be read"


def cmd_plan_health_summary(args: argparse.Namespace) -> NoReturn:
    """Generate lifecycle context summary from recent reflections and plan status.

    Shows users where they are in the workflow lifecycle.
    Includes deduplicated unresolved improvements from recent runs.
    """
    design_dir = args.design_dir

    recent = _read_recent_reflections(design_dir)
    summaries = [r["summary"] for r in recent]
    plan_status = _read_plan_status(design_dir)
    unresolved = _extract_unresolved_improvements(design_dir)

    output_json(
        {
            "ok": True,
            "reflections": summaries,
            "recentRuns": recent,
            "plan": plan_status,
            "unresolvedImprovements": unresolved,
        }
    )


def cmd_memory_review(args: argparse.Namespace) -> NoReturn:
    """List all memories in human-readable format with filtering.

    Allows filtering by category and keyword. Outputs formatted for user review.
    """
    memory_path = args.memory_path
    category_filter = getattr(args, "category", None)
    keyword_filter = getattr(args, "keyword", None)

    if not os.path.exists(memory_path):
        output_json(
            {"ok": True, "summary": "No memory file found", "count": 0, "memories": []}
        )

    try:
        all_memories = _read_jsonl(memory_path)
    except OSError as e:
        error_exit(f"Error reading memory file: {e}")

    if not all_memories:
        output_json(
            {"ok": True, "summary": "No memories found", "count": 0, "memories": []}
        )

    # Apply filters and sort
    filtered = _filter_memories(all_memories, category_filter, keyword_filter)
    filtered.sort(
        key=lambda m: (m.get("importance", 5), _parse_timestamp(m.get("timestamp", 0))),
        reverse=True,
    )

    # Format for display
    memories_formatted = [_format_memory_for_review(mem) for mem in filtered]

    # Build summary text
    summary = f"Showing {len(filtered)} of {len(all_memories)} memories"
    if category_filter:
        summary += f" (category: {category_filter})"
    if keyword_filter:
        summary += f" (keyword: {keyword_filter})"

    output_json(
        {
            "ok": True,
            "summary": summary,
            "count": len(filtered),
            "total": len(all_memories),
            "memories": memories_formatted,
        }
    )


# ============================================================================
# Archive Command
# ============================================================================


_SKILL_NAMES_PATTERN = "design|execute|research|reflect|simplify"

# Shared block patterns: section name → regex to extract the block content.
# Content is normalized by _normalize_block before fingerprinting.
_SHARED_BLOCK_PATTERNS: dict[str, str] = {
    "Script Setup": r"### Script Setup\n\n.*?```bash\n(.*?)```",
    "Liveness Pipeline Table": r"\| Rule \| Action \|\n\|---\|---\|\n((?:\|.*?\|\n)+)",
    "Finalize Fallback": r"\*\*Fallback\*\* \(if finalize fails\):?\n((?:[\d]+\. .*?\n)+)",
}


def _normalize_block(text: str) -> str:
    """Normalize a block for fingerprinting: replace skill names, collapse whitespace."""
    # Replace skill names in paths and identifiers with a placeholder
    text = re.sub(rf"\b({_SKILL_NAMES_PATTERN})\b", "{{SKILL}}", text)
    # Remove optional TEAM_NAME line (reflect doesn't have it, causing false drift)
    text = re.sub(
        r"TEAM_NAME=\$\(python3 \$PLAN_CLI team-name \{SKILL\}\)\.teamName\s*\n?",
        "",
        text,
    )
    return re.sub(r"\s+", " ", text).strip()


def _load_skill_paths(skills_dir: str) -> dict[str, str]:
    """Load and validate SKILL.md paths for all expected skills."""
    expected_skills = [
        "design",
        "execute",
        "research",
        "reflect",
        "simplify",
    ]
    skill_paths = {}

    for skill in expected_skills:
        skill_path = os.path.join(skills_dir, skill, "SKILL.md")
        if not os.path.exists(skill_path):
            error_exit(f"Missing SKILL.md for skill: {skill}")
        skill_paths[skill] = skill_path

    return skill_paths


def _extract_block_from_content(content: str, pattern: str) -> str | None:
    """Extract and normalize a block from skill content."""
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return None

    extracted = match.group(1) if match.lastindex else match.group(0)
    return _normalize_block(extracted)


def _extract_skill_blocks(
    skill_paths: dict[str, str],
) -> dict[str, dict[str, str | None]]:
    """Extract shared blocks from each skill file."""
    skill_blocks: dict[str, dict[str, str | None]] = {}

    for skill, path in skill_paths.items():
        with open(path) as f:
            content = f.read()

        skill_blocks[skill] = {
            block_name: _extract_block_from_content(content, pattern)
            for block_name, pattern in _SHARED_BLOCK_PATTERNS.items()
        }

    return skill_blocks


def _analyze_block_sync(
    block_name: str,
    skill_blocks: dict[str, dict[str, str | None]],
    all_skills: list[str],
) -> tuple[str, dict[str, Any]]:
    """Analyze whether a block is synced or drifted across skills."""
    values = {
        skill: content
        for skill, blocks in skill_blocks.items()
        if (content := blocks.get(block_name)) is not None
    }

    if not values:
        return (
            "drifted",
            {
                "block": block_name,
                "skills": all_skills,
                "issue": "block not found in any skill file",
            },
        )

    unique_values = set(values.values())
    if len(unique_values) == 1:
        return (
            "synced",
            {
                "block": block_name,
                "skills": list(values.keys()),
                "present_in": len(values),
            },
        )

    return (
        "drifted",
        {
            "block": block_name,
            "skills": list(values.keys()),
            "drift": [
                {
                    "skill": skill,
                    "content_hash": hashlib.sha256(content.encode()).hexdigest()[:8],
                }
                for skill, content in values.items()
            ],
        },
    )


def cmd_sync_check(args: argparse.Namespace) -> NoReturn:
    """Check drift between shared protocol blocks across SKILL.md files."""
    skills_dir = args.skills_dir

    if not os.path.isdir(skills_dir):
        error_exit(f"Skills directory not found: {skills_dir}")

    skill_paths = _load_skill_paths(skills_dir)
    skill_blocks = _extract_skill_blocks(skill_paths)

    synced = []
    drifted = []

    for block_name in _SHARED_BLOCK_PATTERNS:
        status, data = _analyze_block_sync(
            block_name, skill_blocks, list(skill_paths.keys())
        )
        if status == "synced":
            synced.append(data)
        else:
            drifted.append(data)

    output_json(
        {
            "ok": len(drifted) == 0,
            "synced": synced,
            "drifted": drifted,
            "skills_checked": list(skill_paths.keys()),
        }
    )


def cmd_archive(args: argparse.Namespace) -> NoReturn:
    """Archive .design/ directory to history/{timestamp}/.

    Preserves persistent files: memory.jsonl, reflection.jsonl, research.json, history/
    Moves all other files to .design/history/{UTC timestamp}/
    """
    design_dir = args.design_dir.rstrip("/")

    # Check if design directory exists
    if not os.path.exists(design_dir):
        output_json({"ok": True, "message": "nothing to archive"})

    if not os.path.isdir(design_dir):
        error_exit(f"{design_dir} is not a directory")

    # Create timestamp for archive directory
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    history_dir = os.path.join(design_dir, "history")
    archive_dir = os.path.join(history_dir, timestamp)

    # Persistent files to preserve (not archive)
    persistent = {
        "memory.jsonl",
        "reflection.jsonl",
        "research.json",
        "trace.jsonl",
        "history",
    }

    # List all items in design directory
    try:
        items = os.listdir(design_dir)
    except OSError as e:
        error_exit(f"Error reading {design_dir}: {e}")

    # Filter out persistent files
    to_archive = [item for item in items if item not in persistent]

    if not to_archive:
        output_json({"ok": True, "message": "nothing to archive"})

    # Create archive directory
    try:
        os.makedirs(archive_dir, exist_ok=True)
    except OSError as e:
        error_exit(f"Error creating archive directory: {e}")

    # Move files to archive
    try:
        for item in to_archive:
            src = os.path.join(design_dir, item)
            dst = os.path.join(archive_dir, item)
            os.rename(src, dst)
    except OSError as e:
        error_exit(f"Error archiving files: {e}")

    output_json({"ok": True, "archivedTo": archive_dir})


# ============================================================================
# Self-Test
# ============================================================================


def _run_unittest_suite() -> list[dict[str, Any]]:
    """Run the internal unittest suite and return per-test results."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestPlanCommands)

    test_results: list[dict[str, Any]] = []

    class _CollectingResult(unittest.TestResult):
        def addSuccess(self, test: unittest.TestCase) -> None:
            test_results.append(
                {
                    "command": f"unittest:{test._testMethodName}",
                    "passed": True,
                    "error": None,
                }
            )

        def addFailure(self, test: unittest.TestCase, err: Any) -> None:
            test_results.append(
                {
                    "command": f"unittest:{test._testMethodName}",
                    "passed": False,
                    "error": str(err[1]),
                }
            )

        def addError(self, test: unittest.TestCase, err: Any) -> None:
            test_results.append(
                {
                    "command": f"unittest:{test._testMethodName}",
                    "passed": False,
                    "error": str(err[1]),
                }
            )

        def addSkip(self, test: unittest.TestCase, reason: str) -> None:
            test_results.append(
                {
                    "command": f"unittest:{test._testMethodName}",
                    "passed": True,
                    "error": None,
                }
            )

    suite.run(_CollectingResult())
    return test_results


def cmd_self_test(args: argparse.Namespace) -> NoReturn:
    """Run self-tests on all commands using synthetic fixtures.

    Runs the internal unittest suite in-process, then runs subprocess tests
    that cover CLI-specific behaviors (exit codes, graceful degradation,
    file write verification) not testable in-process.
    """
    _ = args  # Unused but required for dispatch signature

    # Track results
    results: list[dict[str, Any]] = []
    passed = 0
    failed = 0

    # Run in-process unittest suite first
    unittest_results = _run_unittest_suite()
    for r in unittest_results:
        results.append(r)
        if r["passed"]:
            passed += 1
        else:
            failed += 1

    # Create temp directory for subprocess fixtures
    tmp_dir = tempfile.mkdtemp(prefix="plan-self-test-")

    try:
        # Get path to this script
        script_path = os.path.abspath(__file__)

        # Create fixtures (only needed for subprocess tests)
        fixtures = _create_fixtures(tmp_dir)

        # Subprocess tests: only those with unique CLI-level value
        # (exit-code testing, graceful degradation, file write verification)
        tests = [
            (
                "memory-add --boost (importance arithmetic)",
                lambda: _test_memory_boost(script_path, fixtures["memory_file"]),
            ),
            (
                "memory-add --decay (importance arithmetic)",
                lambda: _test_memory_decay(script_path, fixtures["memory_file"]),
            ),
            (
                "memory-feedback (boost/decay from role outcomes)",
                lambda: _test_memory_feedback(script_path, fixtures["memory_file"]),
            ),
            (
                "trace-add (new file write verification)",
                lambda: _test_trace_add_new(script_path, fixtures["trace_file"]),
            ),
            (
                "trace-add (invalid event type exit-code)",
                lambda: _test_trace_add_invalid_event(script_path, tmp_dir),
            ),
            (
                "trace-add (invalid payload exit-code)",
                lambda: _test_trace_add_invalid_payload(script_path, tmp_dir),
            ),
            (
                "trace-add (graceful degradation)",
                lambda: _test_trace_add_graceful(script_path),
            ),
            (
                "trace-add (skill-start without agent)",
                lambda: _test_trace_add_skill_start(script_path, tmp_dir),
            ),
        ]

        for test_name, test_fn in tests:
            try:
                test_fn()
                results.append({"command": test_name, "passed": True, "error": None})
                passed += 1
            except AssertionError as e:
                results.append({"command": test_name, "passed": False, "error": str(e)})
                failed += 1
            except (OSError, subprocess.TimeoutExpired, ValueError) as e:
                results.append(
                    {
                        "command": test_name,
                        "passed": False,
                        "error": f"Unexpected error: {e}",
                    }
                )
                failed += 1

        output_json(
            {"ok": failed == 0, "passed": passed, "failed": failed, "results": results}
        )

    finally:
        # Clean up temp directory
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _create_fixtures(tmp_dir: str) -> dict[str, str]:
    """Create test fixtures and return their paths."""
    from datetime import timedelta as _td

    now = datetime.now(timezone.utc)
    one_day_ago = (now - _td(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    one_week_ago = (now - _td(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    two_days_ago = (now - _td(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Minimal valid plan
    minimal_plan = {
        "schemaVersion": 4,
        "goal": "Test goal",
        "context": {
            "stack": "python",
            "conventions": [],
            "testCommand": "python -m pytest",
            "buildCommand": "python -m build",
        },
        "expertArtifacts": [],
        "designDecisions": [],
        "verificationSpecs": [],
        "roles": [
            {
                "name": "backend-developer",
                "goal": "Implement backend API",
                "model": "sonnet",
                "scope": {
                    "directories": ["src/api"],
                    "patterns": [],
                    "dependencies": [],
                },
                "constraints": ["Use REST"],
                "acceptanceCriteria": [
                    {
                        "criterion": "API responds",
                        "check": "curl -s localhost:8080/health",
                    }
                ],
                "assumptions": [],
                "rollbackTriggers": [],
                "expertContext": [],
                "fallback": "Use files",
                "status": "pending",
                "attempts": 0,
                "result": None,
                "directoryOverlaps": [],
            },
            {
                "name": "test-writer",
                "goal": "Write tests",
                "model": "haiku",
                "scope": {
                    "directories": ["tests/"],
                    "patterns": [],
                    "dependencies": ["backend-developer"],
                },
                "constraints": ["Use pytest"],
                "acceptanceCriteria": [
                    {"criterion": "Tests pass", "check": "python -m pytest tests/"}
                ],
                "assumptions": [],
                "rollbackTriggers": [],
                "expertContext": [],
                "fallback": None,
                "status": "pending",
                "attempts": 0,
                "result": None,
                "directoryOverlaps": [],
            },
        ],
        "auxiliaryRoles": [],
        "progress": {"completedRoles": []},
    }

    minimal_plan_path = os.path.join(tmp_dir, "minimal_plan.json")
    with open(minimal_plan_path, "w") as f:
        json.dump(minimal_plan, f)

    # Failed plan (role 0 failed)
    failed_plan = json.loads(json.dumps(minimal_plan))
    failed_plan["roles"][0]["status"] = "failed"
    failed_plan["roles"][0]["attempts"] = 1
    failed_plan["roles"][0]["result"] = "build error"

    failed_plan_path = os.path.join(tmp_dir, "failed_plan.json")
    with open(failed_plan_path, "w") as f:
        json.dump(failed_plan, f)

    # In-progress plan
    in_progress_plan = json.loads(json.dumps(minimal_plan))
    in_progress_plan["roles"][0]["status"] = "in_progress"

    in_progress_plan_path = os.path.join(tmp_dir, "in_progress_plan.json")
    with open(in_progress_plan_path, "w") as f:
        json.dump(in_progress_plan, f)

    # Unfinalized plan (no status fields)
    unfin_plan = {
        "schemaVersion": 4,
        "goal": "Test goal",
        "context": {
            "stack": "python",
            "conventions": [],
            "testCommand": "python -m pytest",
            "buildCommand": "python -m build",
        },
        "expertArtifacts": [],
        "designDecisions": [],
        "verificationSpecs": [],
        "roles": [
            {
                "name": "simple-role",
                "goal": "Do something",
                "model": "sonnet",
                "scope": {"directories": ["src/"], "patterns": [], "dependencies": []},
                "constraints": [],
                "acceptanceCriteria": [
                    {"criterion": "Build succeeds", "check": "python -m build"}
                ],
                "assumptions": [],
                "rollbackTriggers": [],
                "expertContext": [],
                "fallback": None,
            }
        ],
        "auxiliaryRoles": [],
        "progress": {"completedRoles": []},
    }

    unfin_plan_path = os.path.join(tmp_dir, "unfin_plan.json")
    with open(unfin_plan_path, "w") as f:
        json.dump(unfin_plan, f)

    # Modified plan (for plan-diff)
    modified_plan = json.loads(json.dumps(minimal_plan))
    modified_plan["roles"][0]["goal"] = "Different goal"

    modified_plan_path = os.path.join(tmp_dir, "modified_plan.json")
    with open(modified_plan_path, "w") as f:
        json.dump(modified_plan, f)

    # Memory file
    memory_entries = [
        {
            "id": "mem-1",
            "timestamp": one_day_ago,
            "category": "pattern",
            "keywords": ["api", "rest"],
            "content": "REST APIs should use consistent error format",
            "source": "execute",
            "goal_context": "API development",
            "importance": 7,
            "usage_count": 2,
        },
        {
            "id": "mem-2",
            "timestamp": one_week_ago,
            "category": "mistake",
            "keywords": ["test", "timeout"],
            "content": "Integration tests need explicit timeouts",
            "source": "execute",
            "goal_context": "Testing",
            "importance": 8,
            "usage_count": 0,
        },
    ]

    memory_file_path = os.path.join(tmp_dir, "memory.jsonl")
    with open(memory_file_path, "w") as f:
        for entry in memory_entries:
            f.write(json.dumps(entry) + "\n")

    # Reflection file
    reflection_entries = [
        {
            "id": "ref-1",
            "timestamp": one_day_ago,
            "skill": "execute",
            "goal": "Build API",
            "outcome": "completed",
            "goalAchieved": True,
            "evaluation": {
                "whatWorked": ["Clear criteria"],
                "whatFailed": ["Slow tests"],
                "doNextTime": ["Parallel tests"],
            },
        },
        {
            "id": "ref-2",
            "timestamp": two_days_ago,
            "skill": "design",
            "goal": "Design auth",
            "outcome": "partial",
            "goalAchieved": False,
            "evaluation": {
                "whatWorked": ["Expert debate"],
                "whatFailed": ["Missing edge cases"],
                "doNextTime": ["Security expert"],
            },
        },
    ]

    reflection_file_path = os.path.join(tmp_dir, "reflection.jsonl")
    with open(reflection_file_path, "w") as f:
        for entry in reflection_entries:
            f.write(json.dumps(entry) + "\n")

    # Expert artifact
    expert_artifact = {
        "summary": "Architecture recommendations",
        "verificationProperties": [
            {
                "property": "All endpoints return JSON",
                "category": "interface",
                "testableVia": "curl + jq",
            }
        ],
    }

    expert_artifact_path = os.path.join(tmp_dir, "expert-architect.json")
    with open(expert_artifact_path, "w") as f:
        json.dump(expert_artifact, f)

    # Design directory for health-check and plan-health-summary
    design_dir = os.path.join(tmp_dir, "test_design")
    os.makedirs(design_dir, exist_ok=True)

    shutil.copy(minimal_plan_path, os.path.join(design_dir, "plan.json"))
    shutil.copy(memory_file_path, os.path.join(design_dir, "memory.jsonl"))
    shutil.copy(reflection_file_path, os.path.join(design_dir, "reflection.jsonl"))

    # Archive directory (for testing archive command)
    archive_dir = os.path.join(tmp_dir, "test_archive")
    os.makedirs(archive_dir, exist_ok=True)

    # Create some files to archive
    shutil.copy(minimal_plan_path, os.path.join(archive_dir, "plan.json"))
    shutil.copy(expert_artifact_path, os.path.join(archive_dir, "expert-test.json"))

    # Add persistent files that should NOT be archived
    shutil.copy(memory_file_path, os.path.join(archive_dir, "memory.jsonl"))
    with open(os.path.join(archive_dir, "research.json"), "w") as f:
        f.write('{"schemaVersion": 1, "goal": "test"}')

    # Plan with bad Python check syntax
    bad_check_plan = {
        "schemaVersion": 4,
        "goal": "Test bad checks",
        "context": {"stack": "python"},
        "expertArtifacts": [],
        "designDecisions": [],
        "verificationSpecs": [],
        "roles": [
            {
                "name": "bad-role",
                "goal": "Test",
                "model": "sonnet",
                "scope": {"directories": [], "patterns": [], "dependencies": []},
                "constraints": [],
                "acceptanceCriteria": [
                    {
                        "criterion": "Broken Python - f-string with backslash escape in braces",
                        "check": r'python3 -c "x = f\"value: {d[\"key\"]}\"; print(x)"',
                    }
                ],
                "assumptions": [],
                "rollbackTriggers": [],
                "expertContext": [],
                "fallback": None,
            }
        ],
        "auxiliaryRoles": [],
        "progress": {"completedRoles": []},
    }

    bad_check_plan_path = os.path.join(tmp_dir, "bad_check_plan.json")
    with open(bad_check_plan_path, "w") as f:
        json.dump(bad_check_plan, f)

    # Research.json fixture
    research_data = {
        "schemaVersion": 1,
        "goal": "Test research",
        "scope": "test area",
        "researchDepth": "standard",
        "sources": [],
        "sections": {
            "prerequisites": {
                "summary": "test prerequisites",
                "technical": [],
                "organizational": [],
                "invisibleCurriculum": [],
            },
            "mentalModels": {
                "summary": "test mental models",
                "keyPrinciples": [],
                "tradeoffs": [],
                "commonMisconceptions": [],
            },
            "usagePatterns": {"summary": "test usage", "patterns": []},
            "failurePatterns": {"summary": "test failures", "patterns": []},
            "productionReadiness": {
                "summary": "test production",
                "observability": [],
                "operationalPatterns": [],
                "scalingConsiderations": [],
                "securityConsiderations": [],
            },
        },
        "recommendations": [
            {
                "action": "adopt",
                "scope": "all",
                "designGoal": "Test design goal",
                "reasoning": "Test reasoning",
                "confidence": "high",
                "effort": "medium",
                "prerequisites": [],
                "risks": [],
            }
        ],
        "contradictions": [],
        "researchGaps": [],
        "designHandoff": [
            {
                "source": "reference-material",
                "element": "Test building block",
                "material": "Concrete content for design",
                "usage": "Use as expert prompt template",
            }
        ],
        "timestamp": "2026-01-01T00:00:00Z",
    }

    research_file_path = os.path.join(tmp_dir, "research.json")
    with open(research_file_path, "w") as f:
        json.dump(research_data, f)

    # Create test skills directory for sync-check
    skills_dir = os.path.join(tmp_dir, "skills")
    os.makedirs(skills_dir, exist_ok=True)

    # Create mock SKILL.md files with shared blocks
    shared_script_setup = """### Script Setup

Resolve plugin root. All script calls: `python3 $PLAN_CLI <command> [args]` via Bash.

```bash
PLAN_CLI={plugin_root}/skills/{SKILL}/scripts/plan.py
TEAM_NAME=$(python3 $PLAN_CLI team-name {SKILL}).teamName
```"""

    shared_liveness = """| Rule | Action |
|---|---|
| Turn timeout (2 turns) | Send status check |
| Re-spawn ceiling | No completion 1 turn after ping → re-spawn (max 2 attempts) |
| Proceed with available | After 2 attempts → proceed with available |
| Never write artifacts yourself | Lead interpretation ≠ specialist analysis |"""

    shared_fallback = """**Fallback** (if finalize fails):
1. Fix validation errors and re-run finalize.
2. If structure is fundamentally broken: rebuild plan inline."""

    for skill in ["design", "execute", "research", "reflect", "simplify"]:
        skill_dir = os.path.join(skills_dir, skill)
        os.makedirs(skill_dir, exist_ok=True)
        skill_md = os.path.join(skill_dir, "SKILL.md")

        content = f"""---
name: {skill}
description: "Test skill for {skill}"
---

# {skill.capitalize()}

{shared_script_setup.replace("{SKILL}", skill)}

Some skill-specific content here.

{shared_liveness}

More content.

{shared_fallback}

End of skill.
"""
        with open(skill_md, "w") as f:
            f.write(content)

    # Trace file with events across 2 sessions
    trace_file_path = os.path.join(tmp_dir, "trace.jsonl")
    trace_entries = [
        {
            "id": "t-1",
            "timestamp": one_day_ago,
            "sessionId": "session-a",
            "skill": "design",
            "eventType": "skill-start",
            "payload": {},
        },
        {
            "id": "t-2",
            "timestamp": one_day_ago,
            "sessionId": "session-a",
            "skill": "design",
            "eventType": "spawn",
            "agentName": "architect",
            "agentRole": "expert",
            "payload": {"model": "sonnet"},
        },
        {
            "id": "t-3",
            "timestamp": one_day_ago,
            "sessionId": "session-a",
            "skill": "design",
            "eventType": "completion",
            "agentName": "architect",
            "agentRole": "expert",
            "payload": {},
        },
        {
            "id": "t-4",
            "timestamp": two_days_ago,
            "sessionId": "session-b",
            "skill": "execute",
            "eventType": "spawn",
            "agentName": "worker-1",
            "agentRole": "worker",
            "payload": {"model": "haiku"},
        },
    ]
    with open(trace_file_path, "w") as f:
        for entry in trace_entries:
            f.write(json.dumps(entry) + "\n")

    # Archive dir for trace persistence test
    trace_archive_dir = os.path.join(tmp_dir, "trace_archive")
    os.makedirs(trace_archive_dir, exist_ok=True)
    shutil.copy(minimal_plan_path, os.path.join(trace_archive_dir, "plan.json"))
    with open(os.path.join(trace_archive_dir, "trace.jsonl"), "w") as f:
        f.write(json.dumps(trace_entries[0]) + "\n")

    # Design dir for health-check trace test
    trace_design_dir = os.path.join(tmp_dir, "trace_design")
    os.makedirs(trace_design_dir, exist_ok=True)
    shutil.copy(minimal_plan_path, os.path.join(trace_design_dir, "plan.json"))
    with open(os.path.join(trace_design_dir, "trace.jsonl"), "w") as f:
        f.write(json.dumps(trace_entries[0]) + "\n")

    return {
        "minimal_plan": minimal_plan_path,
        "failed_plan": failed_plan_path,
        "in_progress_plan": in_progress_plan_path,
        "unfin_plan": unfin_plan_path,
        "modified_plan": modified_plan_path,
        "bad_check_plan": bad_check_plan_path,
        "memory_file": memory_file_path,
        "reflection_file": reflection_file_path,
        "expert_artifact": expert_artifact_path,
        "design_dir": design_dir,
        "archive_dir": archive_dir,
        "research_file": research_file_path,
        "skills_dir": skills_dir,
        "trace_file": trace_file_path,
        "trace_archive_dir": trace_archive_dir,
        "trace_design_dir": trace_design_dir,
    }


def _run_command(
    script_path: str, args: list[str], stdin_data: str | None = None
) -> dict[str, Any]:
    """Run a plan.py command and return parsed JSON output."""
    cmd = ["python3", script_path, *args]
    result = subprocess.run(  # noqa: S603
        cmd, capture_output=True, text=True, input=stdin_data, timeout=10
    )

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(
            f"Command {' '.join(args)} produced invalid JSON: {result.stdout[:200]}, stderr: {result.stderr[:200]}, error: {e}"
        ) from None


def _test_memory_boost(script_path: str, memory_path: str) -> None:
    """Test memory-add --boost command."""
    output = _run_command(
        script_path, ["memory-add", memory_path, "--boost", "--id", "mem-1"]
    )
    assert output.get("ok") is True, f"memory-add --boost failed: {output}"
    assert output.get("importance") == 8, (
        f"Expected importance 8 (7+1), got {output.get('importance')}"
    )


def _test_memory_decay(script_path: str, memory_path: str) -> None:
    """Test memory-add --decay command."""
    output = _run_command(
        script_path, ["memory-add", memory_path, "--decay", "--id", "mem-2"]
    )
    assert output.get("ok") is True, f"memory-add --decay failed: {output}"
    assert output.get("importance") == 7, (
        f"Expected importance 7 (8-1), got {output.get('importance')}"
    )


def _test_memory_feedback(script_path: str, memory_path: str) -> None:
    """Test memory-feedback boost/decay based on role outcomes."""
    feedback_json = json.dumps(
        [
            {"memoryIds": ["mem-1"], "roleSucceeded": True, "firstAttempt": True},
            {"memoryIds": ["mem-2"], "roleSucceeded": False, "firstAttempt": True},
        ]
    )
    output = _run_command(
        script_path, ["memory-feedback", memory_path], stdin_data=feedback_json
    )
    assert output.get("ok") is True, f"memory-feedback failed: {output}"
    assert output.get("boosted") == 1, (
        f"Expected 1 boosted, got {output.get('boosted')}"
    )
    assert output.get("decayed") == 1, (
        f"Expected 1 decayed, got {output.get('decayed')}"
    )


def _test_trace_add_new(script_path: str, trace_file: str) -> None:
    """Test trace-add creates valid JSONL entry with all required fields."""
    new_trace = trace_file + ".add_test"
    output = _run_command(
        script_path,
        [
            "trace-add",
            new_trace,
            "--session-id",
            "test-sess",
            "--event",
            "spawn",
            "--skill",
            "design",
            "--agent",
            "test-agent",
            "--role",
            "expert",
        ],
    )
    assert output.get("ok") is True, f"trace-add failed: {output}"
    assert "id" in output, "trace-add missing id field"
    with open(new_trace) as f:
        entry = json.loads(f.readline().strip())
    for field in ("id", "timestamp", "sessionId", "skill", "eventType", "payload"):
        assert field in entry, f"trace entry missing {field}"
    assert entry["agentName"] == "test-agent"
    assert entry["agentRole"] == "expert"


def _test_trace_add_invalid_event(script_path: str, tmp_dir: str) -> None:
    """Test trace-add rejects unknown event types."""
    cmd = [
        "python3",
        script_path,
        "trace-add",
        os.path.join(tmp_dir, "inv.jsonl"),
        "--session-id",
        "s",
        "--event",
        "bogus-event",
        "--skill",
        "design",
        "--agent",
        "a",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)  # noqa: S603
    assert result.returncode == 1, f"Expected exit 1, got {result.returncode}"


def _test_trace_add_invalid_payload(script_path: str, tmp_dir: str) -> None:
    """Test trace-add rejects invalid JSON payload."""
    cmd = [
        "python3",
        script_path,
        "trace-add",
        os.path.join(tmp_dir, "inv2.jsonl"),
        "--session-id",
        "s",
        "--event",
        "spawn",
        "--skill",
        "design",
        "--agent",
        "a",
        "--payload",
        "not-json",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)  # noqa: S603
    assert result.returncode == 1, f"Expected exit 1, got {result.returncode}"


def _test_trace_add_graceful(script_path: str) -> None:
    """Test trace-add gracefully handles unwritable path (exit 0)."""
    cmd = [
        "python3",
        script_path,
        "trace-add",
        "/nonexistent/dir/trace.jsonl",
        "--session-id",
        "s",
        "--event",
        "spawn",
        "--skill",
        "design",
        "--agent",
        "a",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)  # noqa: S603
    assert result.returncode == 0, (
        f"Expected exit 0 (graceful), got {result.returncode}"
    )
    output = json.loads(result.stdout)
    assert output.get("ok") is False, "Should return ok=false on write failure"


def _test_trace_add_skill_start(script_path: str, tmp_dir: str) -> None:
    """Test trace-add allows skill-start without --agent."""
    output = _run_command(
        script_path,
        [
            "trace-add",
            os.path.join(tmp_dir, "skill_start.jsonl"),
            "--session-id",
            "s",
            "--event",
            "skill-start",
            "--skill",
            "design",
        ],
    )
    assert output.get("ok") is True, f"skill-start without agent failed: {output}"


# ============================================================================
# Internal Unit Tests
# ============================================================================


class TestPlanCommands(unittest.TestCase):
    """In-process unit tests for core plan.py algorithms.

    Tests use unittest with temp directories for isolation. Each test:
    1. Creates argparse.Namespace with required args
    2. Redirects stdout to capture JSON output
    3. Catches SystemExit to verify exit codes
    4. Parses JSON output and asserts on structure/values
    """

    def setUp(self) -> None:
        """Create temporary directory and fixtures for each test."""
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.fixtures = _create_fixtures(self.tmp_dir.name)

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        self.tmp_dir.cleanup()

    def _run_cmd(
        self, func: Any, args: argparse.Namespace
    ) -> tuple[int, dict[str, Any]]:
        """Helper to run a cmd_* function and capture output."""
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            try:
                func(args)
                exit_code = 0
            except SystemExit as e:
                exit_code = e.code or 0

        result = json.loads(captured.getvalue())
        return exit_code, result

    def _run_cmd_with_stdin(
        self, func: Any, args: argparse.Namespace, json_obj: Any
    ) -> tuple[int, dict[str, Any]]:
        """Helper to run a cmd_* function with stdin injection and capture output."""
        captured = io.StringIO()
        old_stdin = sys.stdin
        exit_code = 0
        with contextlib.redirect_stdout(captured):
            try:
                sys.stdin = io.StringIO(json.dumps(json_obj))
                func(args)
            except SystemExit as e:
                exit_code = e.code or 0
            finally:
                sys.stdin = old_stdin

        result = json.loads(captured.getvalue())
        return exit_code, result

    # Test core algorithm functions

    def test_compute_depths_linear_chain(self) -> None:
        """Test depth computation for linear dependency chain."""
        roles = [
            {"name": "a", "scope": {"dependencies": []}},
            {"name": "b", "scope": {"dependencies": ["a"]}},
            {"name": "c", "scope": {"dependencies": ["b"]}},
        ]
        name_index = build_name_index(roles)
        deps = resolve_dependencies(roles, name_index)
        depths = compute_depths(roles, deps)

        self.assertEqual(depths[0], 1)
        self.assertEqual(depths[1], 2)
        self.assertEqual(depths[2], 3)

    def test_compute_depths_diamond(self) -> None:
        """Test depth computation for diamond dependency pattern."""
        roles = [
            {"name": "a", "scope": {"dependencies": []}},
            {"name": "b", "scope": {"dependencies": ["a"]}},
            {"name": "c", "scope": {"dependencies": ["a"]}},
            {"name": "d", "scope": {"dependencies": ["b", "c"]}},
        ]
        name_index = build_name_index(roles)
        deps = resolve_dependencies(roles, name_index)
        depths = compute_depths(roles, deps)

        self.assertEqual(depths[0], 1)
        self.assertEqual(depths[1], 2)
        self.assertEqual(depths[2], 2)
        self.assertEqual(depths[3], 3)

    def test_paths_overlap_exact_match(self) -> None:
        """Test that identical paths overlap."""
        self.assertTrue(_paths_overlap("src/", "src/"))

    def test_paths_overlap_prefix(self) -> None:
        """Test that prefix paths overlap."""
        self.assertTrue(_paths_overlap("src/api/", "src/"))
        self.assertTrue(_paths_overlap("src/", "src/api/"))

    def test_paths_overlap_disjoint(self) -> None:
        """Test that disjoint paths don't overlap."""
        self.assertFalse(_paths_overlap("src/", "dist/"))
        self.assertFalse(_paths_overlap("api/", "web/"))

    def test_paths_overlap_glob_patterns(self) -> None:
        """Test that glob patterns with shared base overlap."""
        self.assertTrue(_paths_overlap("src/**/*.ts", "src/**/*.test.ts"))
        self.assertTrue(_paths_overlap("src/**/*.ts", "src/api/**/*.ts"))

    def test_validate_python_check_valid(self) -> None:
        """Test validation of valid Python check commands."""
        valid, error = _validate_python_check("python3 -c 'print(1)'")
        self.assertTrue(valid)
        self.assertIsNone(error)

    def test_validate_python_check_syntax_error(self) -> None:
        """Test validation catches Python syntax errors."""
        valid, error = _validate_python_check("python3 -c 'if x'")
        self.assertFalse(valid)
        self.assertIsNotNone(error)
        self.assertIn("SyntaxError", error)

    def test_validate_python_check_non_python(self) -> None:
        """Test that non-Python commands pass through."""
        valid, error = _validate_python_check("bun test src/")
        self.assertTrue(valid)
        self.assertIsNone(error)

    def test_validate_python_check_fstring_nested_braces(self) -> None:
        """Test f-string with nested braces."""
        cmd = r"python3 -c \"x={'a':1}; print(f\"{x['a']}\")\""
        valid, error = _validate_python_check(cmd)
        self.assertTrue(valid)
        self.assertIsNone(error)

    def test_validate_status_transition_valid(self) -> None:
        """Test valid status transitions."""
        valid, _ = _validate_status_transition("pending", "in_progress")
        self.assertTrue(valid)
        valid, _ = _validate_status_transition("in_progress", "completed")
        self.assertTrue(valid)
        valid, _ = _validate_status_transition("in_progress", "failed")
        self.assertTrue(valid)
        valid, _ = _validate_status_transition("failed", "pending")
        self.assertTrue(valid)

    def test_validate_status_transition_invalid(self) -> None:
        """Test invalid status transitions are rejected."""
        valid, _ = _validate_status_transition("pending", "completed")

        self.assertFalse(valid)
        valid, _ = _validate_status_transition("completed", "in_progress")

        self.assertFalse(valid)
        valid, _ = _validate_status_transition("in_progress", "pending")

        self.assertFalse(valid)

    def test_validate_status_transition_initialization(self) -> None:
        """Test that transitions from None are invalid."""
        valid, _ = _validate_status_transition(None, "pending")
        self.assertFalse(valid)

    def test_parse_timestamp_iso(self) -> None:
        """Test parsing ISO 8601 timestamps."""
        ts = _parse_timestamp("2025-01-15T12:34:56Z")
        self.assertGreater(ts, 0)
        self.assertIsInstance(ts, float)

    def test_parse_timestamp_numeric(self) -> None:
        """Test that numeric timestamps pass through."""
        self.assertEqual(_parse_timestamp(1705320896), 1705320896.0)
        self.assertEqual(_parse_timestamp(1705320896.123), 1705320896.123)

    def test_parse_timestamp_invalid(self) -> None:
        """Test that invalid timestamps return 0.0."""
        self.assertEqual(_parse_timestamp("not-a-date"), 0.0)
        self.assertEqual(_parse_timestamp(""), 0.0)
        self.assertEqual(_parse_timestamp(None), 0.0)

    def test_get_transitive_deps_linear(self) -> None:
        """Test transitive dependency computation for linear chain."""
        deps = [[], [0], [1]]
        transitive = get_transitive_deps(deps, {0})
        self.assertEqual(transitive, {1, 2})

    def test_get_transitive_deps_empty(self) -> None:
        """Test that empty start_indices returns empty set."""
        deps = [[], [0], [1]]
        transitive = get_transitive_deps(deps, set())
        self.assertEqual(transitive, set())

    def test_get_transitive_deps_no_dependents(self) -> None:
        """Test role with no dependents returns empty set."""
        deps = [[], [0], [1]]
        transitive = get_transitive_deps(deps, {2})
        self.assertEqual(transitive, set())

    def test_validate_memory_input_valid(self) -> None:
        """Test valid memory input passes validation."""
        keywords = _validate_memory_input("pattern", "test content", "python,testing")
        self.assertEqual(keywords, ["python", "testing"])

    def test_find_closing_quote_simple(self) -> None:
        """Test finding closing quote in simple string."""
        idx = _find_closing_quote("'hello'", 0, "'")
        self.assertEqual(idx, 6)

    def test_find_closing_quote_empty(self) -> None:
        """Test finding closing quote in empty string."""
        idx = _find_closing_quote("''", 0, "'")
        self.assertEqual(idx, 1)

    def test_find_closing_quote_not_found(self) -> None:
        """Test unclosed string returns -1."""
        idx = _find_closing_quote("'hello", 0, "'")
        self.assertEqual(idx, -1)

    def test_find_closing_quote_escaped(self) -> None:
        """Test escaped quotes don't terminate string."""
        idx = _find_closing_quote('"hello \\"world\\""', 0, '"')
        self.assertEqual(idx, 16)

    def test_team_name_success(self) -> None:
        """Test team-name command generates deterministic team name."""
        args = argparse.Namespace(skill="design")
        exit_code, result = self._run_cmd(cmd_team_name, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertIn("teamName", result)
        self.assertTrue(result["teamName"].startswith("do-design-"))

    def test_status_success(self) -> None:
        """Test status command returns role counts."""
        args = argparse.Namespace(plan_path=self.fixtures["minimal_plan"])
        exit_code, result = self._run_cmd(cmd_status, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertIn("counts", result)
        self.assertIn("pending", result["counts"])

    def test_status_not_found(self) -> None:
        """Test status command with missing plan file."""
        args = argparse.Namespace(plan_path="/nonexistent/plan.json")
        exit_code, result = self._run_cmd(cmd_status, args)

        self.assertEqual(exit_code, 1)
        self.assertFalse(result["ok"])
        self.assertIn("error", result)

    def test_summary_success(self) -> None:
        """Test summary command returns plan overview."""
        args = argparse.Namespace(plan_path=self.fixtures["minimal_plan"])
        exit_code, result = self._run_cmd(cmd_summary, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertIn("roleCount", result)
        self.assertIn("modelDistribution", result)

    def test_worker_pool_success(self) -> None:
        """Test worker-pool command identifies runnable roles."""
        args = argparse.Namespace(plan_path=self.fixtures["minimal_plan"])
        exit_code, result = self._run_cmd(cmd_worker_pool, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertIn("workers", result)

    def test_worker_pool_excludes_blocked(self) -> None:
        """Test worker-pool excludes roles with failed dependencies."""
        args = argparse.Namespace(plan_path=self.fixtures["failed_plan"])
        exit_code, result = self._run_cmd(cmd_worker_pool, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        worker_names = [w["name"] for w in result["workers"]]
        self.assertNotIn("test-writer", worker_names)

    def test_retry_candidates_success(self) -> None:
        """Test retry-candidates finds failed roles under retry limit."""
        args = argparse.Namespace(plan_path=self.fixtures["failed_plan"])
        exit_code, result = self._run_cmd(cmd_retry_candidates, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertIn("retryable", result)

    def test_circuit_breaker_no_abort(self) -> None:
        """Test circuit-breaker doesn't trigger with low failure rate."""
        args = argparse.Namespace(plan_path=self.fixtures["minimal_plan"])
        exit_code, result = self._run_cmd(cmd_circuit_breaker, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertFalse(result.get("shouldAbort", False))

    def test_validate_checks_success(self) -> None:
        """Test validate-checks passes valid acceptance criteria."""
        args = argparse.Namespace(plan_path=self.fixtures["minimal_plan"])
        exit_code, result = self._run_cmd(cmd_validate_checks, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])

    def test_health_check_success(self) -> None:
        """Test health-check validates design directory integrity."""
        design_dir = os.path.join(self.tmp_dir.name, ".design")
        os.makedirs(design_dir, exist_ok=True)
        shutil.copy(
            self.fixtures["minimal_plan"], os.path.join(design_dir, "plan.json")
        )

        args = argparse.Namespace(design_dir=design_dir)
        exit_code, result = self._run_cmd(cmd_health_check, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])

    def test_overlap_matrix_success(self) -> None:
        """Test overlap-matrix computes directory overlaps."""
        args = argparse.Namespace(plan_path=self.fixtures["minimal_plan"])
        exit_code, result = self._run_cmd(cmd_overlap_matrix, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertIn("matrix", result)

    def test_tasklist_data_success(self) -> None:
        """Test tasklist-data extracts task creation data."""
        args = argparse.Namespace(plan_path=self.fixtures["minimal_plan"])
        exit_code, result = self._run_cmd(cmd_tasklist_data, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertIn("roles", result)

    def test_resume_reset_success(self) -> None:
        """Test resume-reset resets in_progress roles."""
        args = argparse.Namespace(plan_path=self.fixtures["in_progress_plan"])
        exit_code, result = self._run_cmd(cmd_resume_reset, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])

    def test_finalize_success(self) -> None:
        """Test finalize validates and enriches plan."""
        args = argparse.Namespace(plan_path=self.fixtures["minimal_plan"])
        exit_code, result = self._run_cmd(cmd_finalize, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])

    def test_plan_diff_success(self) -> None:
        """Test plan-diff compares two plan files."""
        args = argparse.Namespace(
            plan_a=self.fixtures["minimal_plan"],
            plan_b=self.fixtures["modified_plan"],
        )
        exit_code, result = self._run_cmd(cmd_plan_diff, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])

    def test_reflection_search_empty(self) -> None:
        """Test reflection-search with no reflections."""
        reflection_path = os.path.join(self.tmp_dir.name, "reflection.jsonl")
        with open(reflection_path, "w"):
            pass

        args = argparse.Namespace(reflection_path=reflection_path, skill=None, limit=10)
        exit_code, result = self._run_cmd(cmd_reflection_search, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertEqual(result["reflections"], [])

    def test_memory_review_empty(self) -> None:
        """Test memory-review with empty memory file."""
        memory_path = os.path.join(self.tmp_dir.name, "memory.jsonl")
        with open(memory_path, "w"):
            pass

        args = argparse.Namespace(
            memory_path=memory_path,
            category=None,
            keywords=None,
            min_importance=None,
            limit=None,
        )
        exit_code, result = self._run_cmd(cmd_memory_review, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])

    def test_archive_creates_history(self) -> None:
        """Test archive moves files to history directory."""
        design_dir = os.path.join(self.tmp_dir.name, ".design")
        os.makedirs(design_dir, exist_ok=True)

        test_file = os.path.join(design_dir, "test.json")
        with open(test_file, "w") as f:
            json.dump({"test": "data"}, f)

        args = argparse.Namespace(design_dir=design_dir)
        exit_code, result = self._run_cmd(cmd_archive, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])

    def test_plan_health_summary_success(self) -> None:
        """Test plan-health-summary shows lifecycle context."""
        design_dir = os.path.join(self.tmp_dir.name, ".design")
        os.makedirs(design_dir, exist_ok=True)

        args = argparse.Namespace(design_dir=design_dir)
        exit_code, result = self._run_cmd(cmd_plan_health_summary, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])

    def test_compute_directory_overlaps(self) -> None:
        """Test _compute_directory_overlaps function."""
        plan = load_plan(self.fixtures["minimal_plan"])
        overlaps_found = _compute_directory_overlaps(plan)
        self.assertIsInstance(overlaps_found, int)
        self.assertGreaterEqual(overlaps_found, 0)

    def test_validate_role_brief_valid(self) -> None:
        """Test _validate_role_brief with valid role."""
        plan = load_plan(self.fixtures["minimal_plan"])
        role = plan["roles"][0]
        errors = _validate_role_brief(role, 0)
        self.assertEqual(errors, [])

    def test_research_summary_empty(self) -> None:
        """Test research-summary with empty recommendations."""
        research_file = os.path.join(self.tmp_dir.name, "research.json")
        with open(research_file, "w") as f:
            json.dump(
                {
                    "schemaVersion": 1,
                    "goal": "Test",
                    "sections": {},
                    "recommendations": [],
                    "contradictions": [],
                },
                f,
            )

        args = argparse.Namespace(research_path=research_file)
        exit_code, result = self._run_cmd(cmd_research_summary, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])

    def test_finalize_exercises_directory_overlaps(self) -> None:
        """Test that finalize exercises _compute_directory_overlaps."""
        plan_file = os.path.join(self.tmp_dir.name, "overlap_plan.json")
        plan = load_plan(self.fixtures["minimal_plan"])
        plan["roles"][0]["scope"]["directories"] = ["src/api"]
        plan["roles"][1]["scope"]["directories"] = ["src/api"]
        with open(plan_file, "w") as f:
            json.dump(plan, f)

        args = argparse.Namespace(plan_path=plan_file)
        exit_code, result = self._run_cmd(cmd_finalize, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])

    def test_finalize_exercises_role_brief_validation(self) -> None:
        """Test that finalize exercises _validate_role_brief."""
        args = argparse.Namespace(plan_path=self.fixtures["minimal_plan"])
        exit_code, result = self._run_cmd(cmd_finalize, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])

    def test_update_status_with_cascading(self) -> None:
        """Test cmd_update_status exercises cascading failures."""
        plan_file = os.path.join(self.tmp_dir.name, "cascade_plan.json")
        plan = load_plan(self.fixtures["minimal_plan"])
        plan["roles"][0]["status"] = "pending"
        plan["roles"][1]["status"] = "pending"
        with open(plan_file, "w") as f:
            json.dump(plan, f)

        args = argparse.Namespace(plan_path=plan_file)
        _, result = self._run_cmd_with_stdin(
            cmd_update_status, args, [{"role": "backend-developer", "status": "failed"}]
        )
        self.assertTrue(result["ok"])

    def test_memory_add_with_boost(self) -> None:
        """Test cmd_memory_add with boost flag."""
        memory_file = os.path.join(self.tmp_dir.name, "memory.jsonl")
        # Create memory file with an existing entry to boost
        with open(memory_file, "w") as f:
            json.dump(
                {
                    "id": "test-id",
                    "category": "pattern",
                    "keywords": ["python"],
                    "content": "Test content",
                    "source": "",
                    "timestamp": 1735689600.0,
                    "goal_context": "",
                    "importance": 5,
                    "usage_count": 0,
                },
                f,
            )
            f.write("\n")

        args = argparse.Namespace(
            memory_path=memory_file,
            category="pattern",
            keywords="test,python",
            content="Test memory content",
            source=None,
            goal_context=None,
            importance=5,
            boost=True,
            decay=False,
            id="test-id",
        )
        exit_code, result = self._run_cmd(cmd_memory_add, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])

    def test_memory_add_with_decay(self) -> None:
        """Test cmd_memory_add with decay flag."""
        memory_file = os.path.join(self.tmp_dir.name, "memory.jsonl")
        # Create memory file with an existing entry to decay
        with open(memory_file, "w") as f:
            json.dump(
                {
                    "id": "test-id-2",
                    "category": "mistake",
                    "keywords": ["bug"],
                    "content": "Test content",
                    "source": "",
                    "timestamp": 1735689600.0,
                    "goal_context": "",
                    "importance": 8,
                    "usage_count": 0,
                },
                f,
            )
            f.write("\n")

        args = argparse.Namespace(
            memory_path=memory_file,
            category="mistake",
            keywords="error,bug",
            content="Test mistake content",
            source=None,
            goal_context=None,
            importance=3,
            boost=False,
            decay=True,
            id="test-id-2",
        )
        exit_code, result = self._run_cmd(cmd_memory_add, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])

    def test_memory_search_with_keywords(self) -> None:
        """Test cmd_memory_search with keyword matching."""
        memory_file = os.path.join(self.tmp_dir.name, "memory.jsonl")
        with open(memory_file, "w") as f:
            f.write(
                json.dumps(
                    {
                        "id": "test-id",
                        "category": "pattern",
                        "keywords": ["python", "testing"],
                        "content": "Test content",
                        "timestamp": "2025-01-01T00:00:00Z",
                        "importance": 5,
                    }
                )
                + "\n"
            )

        args = argparse.Namespace(
            memory_path=memory_file,
            goal="test python code",
            stack="python",
            keywords="testing",
            limit=5,
        )
        exit_code, result = self._run_cmd(cmd_memory_search, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertIn("memories", result)

    def test_reflection_add_success(self) -> None:
        """Test cmd_reflection_add adds reflection entry."""
        reflection_file = os.path.join(self.tmp_dir.name, "reflection.jsonl")
        with open(reflection_file, "w"):
            pass

        reflection_obj = {
            "goalAchieved": True,
            "successFactors": ["factor1"],
            "challenges": [],
            "whatWorked": [],
            "whatDidntWork": [],
            "surprises": [],
            "recommendation": "Continue",
        }

        args = argparse.Namespace(
            reflection_path=reflection_file,
            skill="design",
            goal="Test goal",
            outcome="completed",
            goal_achieved=True,
        )
        exit_code, result = self._run_cmd_with_stdin(
            cmd_reflection_add, args, reflection_obj
        )
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])

    def test_reflection_add_rejects_empty_prompt_fixes_with_failures(self) -> None:
        """Test reflection-add rejects whatFailed non-empty but promptFixes empty."""
        reflection_file = os.path.join(self.tmp_dir.name, "refl_reject.jsonl")

        reflection_obj = {
            "whatFailed": ["something went wrong"],
            "promptFixes": [],
        }

        args = argparse.Namespace(
            reflection_path=reflection_file,
            skill="design",
            goal="Test goal",
            outcome="completed",
            goal_achieved=True,
        )
        exit_code, result = self._run_cmd_with_stdin(
            cmd_reflection_add, args, reflection_obj
        )
        self.assertEqual(exit_code, 1)
        self.assertFalse(result["ok"])

    def test_reflection_add_accepts_what_failed_with_prompt_fixes(self) -> None:
        """Test reflection-add accepts whatFailed when promptFixes is also non-empty."""
        reflection_file = os.path.join(self.tmp_dir.name, "refl_accept.jsonl")

        reflection_obj = {
            "whatFailed": ["something went wrong"],
            "promptFixes": [
                {
                    "section": "Step 3",
                    "problem": "missed step",
                    "idealOutcome": "step executed",
                    "fix": "add explicit directive",
                    "failureClass": "spec-disobey",
                }
            ],
        }

        args = argparse.Namespace(
            reflection_path=reflection_file,
            skill="design",
            goal="Test goal",
            outcome="completed",
            goal_achieved=True,
        )
        exit_code, result = self._run_cmd_with_stdin(
            cmd_reflection_add, args, reflection_obj
        )
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])

    def test_reflection_search_with_skill_filter(self) -> None:
        """Test cmd_reflection_search with skill filtering."""
        reflection_file = os.path.join(self.tmp_dir.name, "reflection.jsonl")
        with open(reflection_file, "w") as f:
            f.write(
                json.dumps(
                    {
                        "id": "test-id",
                        "skill": "design",
                        "goal": "Test goal",
                        "outcome": "success",
                        "goalAchieved": True,
                        "timestamp": "2025-01-01T00:00:00Z",
                        "evaluation": {},
                    }
                )
                + "\n"
            )

        args = argparse.Namespace(
            reflection_path=reflection_file,
            skill="design",
            limit=10,
        )
        exit_code, result = self._run_cmd(cmd_reflection_search, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["reflections"]), 1)

    def test_finalize_with_missing_field(self) -> None:
        """Test cmd_finalize success despite schema variations."""
        plan_file = os.path.join(self.tmp_dir.name, "varied_plan.json")
        plan = load_plan(self.fixtures["minimal_plan"])
        # finalize should still succeed with valid base plan
        with open(plan_file, "w") as f:
            json.dump(plan, f)

        args = argparse.Namespace(plan_path=plan_file)
        exit_code, result = self._run_cmd(cmd_finalize, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])

    def test_status_with_multiple_statuses(self) -> None:
        """Test cmd_status with various role statuses."""
        plan_file = os.path.join(self.tmp_dir.name, "multi_status.json")
        plan = load_plan(self.fixtures["minimal_plan"])
        plan["roles"][0]["status"] = "completed"
        with open(plan_file, "w") as f:
            json.dump(plan, f)

        args = argparse.Namespace(plan_path=plan_file)
        exit_code, result = self._run_cmd(cmd_status, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertIn("counts", result)
        self.assertEqual(result["counts"]["completed"], 1)

    def test_worker_pool_with_dependencies(self) -> None:
        """Test cmd_worker_pool dependency resolution."""
        args = argparse.Namespace(plan_path=self.fixtures["minimal_plan"])
        exit_code, result = self._run_cmd(cmd_worker_pool, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        workers = result["workers"]
        self.assertIsInstance(workers, list)

    def test_retry_candidates_with_exhausted(self) -> None:
        """Test cmd_retry_candidates with exhausted retries."""
        plan_file = os.path.join(self.tmp_dir.name, "exhausted.json")
        plan = load_plan(self.fixtures["failed_plan"])
        plan["roles"][0]["attempts"] = 3
        with open(plan_file, "w") as f:
            json.dump(plan, f)

        args = argparse.Namespace(plan_path=plan_file)
        exit_code, result = self._run_cmd(cmd_retry_candidates, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["retryable"]), 0)

    def test_circuit_breaker_triggers(self) -> None:
        """Test cmd_circuit_breaker when it should trigger."""
        plan_file = os.path.join(self.tmp_dir.name, "circuit.json")
        plan = load_plan(self.fixtures["minimal_plan"])
        for _ in range(5):
            plan["roles"].append(
                {
                    "name": f"role-{_}",
                    "status": "failed",
                    "scope": {"dependencies": []},
                    "goal": "test",
                    "model": "sonnet",
                    "constraints": [],
                    "acceptanceCriteria": [],
                    "assumptions": [],
                    "rollbackTriggers": [],
                    "expertContext": [],
                    "fallback": None,
                    "attempts": 0,
                    "result": None,
                    "directoryOverlaps": [],
                }
            )
        with open(plan_file, "w") as f:
            json.dump(plan, f)

        args = argparse.Namespace(plan_path=plan_file)
        exit_code, result = self._run_cmd(cmd_circuit_breaker, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])

    def test_overlap_matrix_with_overlaps(self) -> None:
        """Test cmd_overlap_matrix detects overlaps."""
        plan_file = os.path.join(self.tmp_dir.name, "overlap.json")
        plan = load_plan(self.fixtures["minimal_plan"])
        plan["roles"][0]["scope"]["directories"] = ["src/"]
        plan["roles"][1]["scope"]["directories"] = ["src/api/"]
        with open(plan_file, "w") as f:
            json.dump(plan, f)

        args = argparse.Namespace(plan_path=plan_file)
        exit_code, result = self._run_cmd(cmd_overlap_matrix, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertIn("matrix", result)

    def test_archive_with_persistent_files(self) -> None:
        """Test cmd_archive preserves persistent files."""
        design_dir = os.path.join(self.tmp_dir.name, ".design")
        os.makedirs(design_dir, exist_ok=True)

        memory_file = os.path.join(design_dir, "memory.jsonl")
        with open(memory_file, "w") as f:
            f.write("test\n")

        plan_file = os.path.join(design_dir, "plan.json")
        with open(plan_file, "w") as f:
            json.dump({"test": "data"}, f)

        args = argparse.Namespace(design_dir=design_dir)
        exit_code, result = self._run_cmd(cmd_archive, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertTrue(os.path.exists(memory_file))

    def test_plan_diff_detects_changes(self) -> None:
        """Test cmd_plan_diff detects role changes."""
        args = argparse.Namespace(
            plan_a=self.fixtures["minimal_plan"],
            plan_b=self.fixtures["modified_plan"],
        )
        exit_code, result = self._run_cmd(cmd_plan_diff, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertIn("modifiedRoles", result)

    def test_validate_checks_with_python_check(self) -> None:
        """Test cmd_validate_checks with Python check."""
        plan_file = os.path.join(self.tmp_dir.name, "valid_checks.json")
        plan = load_plan(self.fixtures["minimal_plan"])
        plan["roles"][0]["acceptanceCriteria"][0]["check"] = "python3 -c 'print(1)'"
        with open(plan_file, "w") as f:
            json.dump(plan, f)

        args = argparse.Namespace(plan_path=plan_file)
        exit_code, result = self._run_cmd(cmd_validate_checks, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])

    def test_health_check_with_empty_design(self) -> None:
        """Test cmd_health_check with empty design directory."""
        design_dir = os.path.join(self.tmp_dir.name, ".design")
        os.makedirs(design_dir, exist_ok=True)

        # Create a minimal plan to satisfy health check
        plan_file = os.path.join(design_dir, "plan.json")
        with open(plan_file, "w") as f:
            json.dump({"schemaVersion": 4, "roles": []}, f)

        args = argparse.Namespace(design_dir=design_dir)
        exit_code, result = self._run_cmd(cmd_health_check, args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])

    # ================================================================
    # Tests for cmd_update_status with cascading failures
    # ================================================================

    def test_update_status_cascading_failures(self) -> None:
        """Test cmd_update_status with cascading failures when a dependency fails."""
        plan_file = os.path.join(self.tmp_dir.name, "cascade.json")
        plan = load_plan(self.fixtures["minimal_plan"])
        plan["roles"][0]["status"] = "in_progress"
        plan["roles"][1]["status"] = "pending"
        with open(plan_file, "w") as f:
            json.dump(plan, f)

        _, result = self._run_cmd_with_stdin(
            cmd_update_status,
            argparse.Namespace(plan_path=plan_file),
            [{"roleIndex": 0, "status": "failed", "result": "build error"}],
        )
        self.assertTrue(result["ok"])
        self.assertIn(0, result["updated"])
        self.assertGreater(len(result["cascaded"]), 0)
        self.assertEqual(result["cascaded"][0]["status"], "skipped")

    def test_update_status_completed_trims_fields(self) -> None:
        """Test cmd_update_status trims role fields on completion."""
        plan_file = os.path.join(self.tmp_dir.name, "trim.json")
        plan = load_plan(self.fixtures["minimal_plan"])
        plan["roles"][0]["status"] = "in_progress"
        with open(plan_file, "w") as f:
            json.dump(plan, f)

        _, result = self._run_cmd_with_stdin(
            cmd_update_status,
            argparse.Namespace(plan_path=plan_file),
            [{"roleIndex": 0, "status": "completed", "result": "done"}],
        )
        self.assertTrue(result["ok"])
        self.assertIn(0, result["trimmed"])

    def test_update_status_invalid_transition_error(self) -> None:
        """Test cmd_update_status rejects invalid state transition."""
        plan_file = os.path.join(self.tmp_dir.name, "invalid_trans.json")
        plan = load_plan(self.fixtures["minimal_plan"])
        plan["roles"][0]["status"] = "pending"
        with open(plan_file, "w") as f:
            json.dump(plan, f)

        _, result = self._run_cmd_with_stdin(
            cmd_update_status,
            argparse.Namespace(plan_path=plan_file),
            [{"roleIndex": 0, "status": "completed"}],
        )
        self.assertFalse(result["ok"])
        self.assertIn("error", result)

    # ================================================================
    # Tests for cmd_expert_validate
    # ================================================================

    def test_expert_validate_valid(self) -> None:
        """Test expert-validate with valid expert artifact."""
        expert_file = os.path.join(self.tmp_dir.name, "expert.json")
        with open(expert_file, "w") as f:
            json.dump(
                {"summary": "Test approach", "verificationProperties": ["prop1"]},
                f,
            )

        args = argparse.Namespace(artifact_path=expert_file)
        exit_code, result = self._run_cmd(cmd_expert_validate, args)
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])

    def test_expert_validate_missing_fields(self) -> None:
        """Test expert-validate rejects artifact missing required fields."""
        expert_file = os.path.join(self.tmp_dir.name, "bad_expert.json")
        with open(expert_file, "w") as f:
            json.dump({"approach": "test"}, f)

        args = argparse.Namespace(artifact_path=expert_file)
        exit_code, result = self._run_cmd(cmd_expert_validate, args)
        self.assertEqual(exit_code, 1)
        self.assertFalse(result["ok"])

    def test_expert_validate_not_found(self) -> None:
        """Test expert-validate with missing artifact file."""
        args = argparse.Namespace(artifact_path="/nonexistent/expert.json")
        exit_code, result = self._run_cmd(cmd_expert_validate, args)
        self.assertEqual(exit_code, 1)
        self.assertFalse(result["ok"])

    # ================================================================
    # Tests for cmd_reflection_validate
    # ================================================================

    def test_reflection_validate_valid(self) -> None:
        """Test reflection-validate with valid evaluation JSON."""
        evaluation = {"whatWorked": ["a"], "whatFailed": ["b"], "doNextTime": ["c"]}
        _, result = self._run_cmd_with_stdin(
            cmd_reflection_validate, argparse.Namespace(), evaluation
        )
        self.assertTrue(result["ok"])

    def test_reflection_validate_missing_fields(self) -> None:
        """Test reflection-validate rejects missing required fields."""
        evaluation = {"whatWorked": ["a"]}
        _, result = self._run_cmd_with_stdin(
            cmd_reflection_validate, argparse.Namespace(), evaluation
        )
        self.assertFalse(result["ok"])

    # ================================================================
    # Tests for cmd_validate_auxiliary_report
    # ================================================================

    def test_validate_auxiliary_report_challenger_valid(self) -> None:
        """Test validate-auxiliary-report with valid challenger report."""
        report_file = os.path.join(self.tmp_dir.name, "challenger.json")
        with open(report_file, "w") as f:
            json.dump(
                {
                    "issues": [
                        {
                            "category": "scope-gap",
                            "severity": "blocking",
                            "description": "Missing scope",
                            "affectedRoles": ["api-dev"],
                            "recommendation": "Add scope",
                        }
                    ],
                    "summary": "Found 1 issue",
                },
                f,
            )

        args = argparse.Namespace(artifact_path=report_file, type="challenger")
        exit_code, result = self._run_cmd(cmd_validate_auxiliary_report, args)
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertEqual(result["artifactSummary"]["blockingCount"], 1)

    def test_validate_auxiliary_report_scout_valid(self) -> None:
        """Test validate-auxiliary-report with valid scout report."""
        report_file = os.path.join(self.tmp_dir.name, "scout.json")
        with open(report_file, "w") as f:
            json.dump(
                {
                    "scopeAreas": [{"path": "src/"}],
                    "discrepancies": [],
                    "summary": "No issues",
                },
                f,
            )

        args = argparse.Namespace(artifact_path=report_file, type="scout")
        exit_code, result = self._run_cmd(cmd_validate_auxiliary_report, args)
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])

    def test_validate_auxiliary_report_integration_verifier_valid(self) -> None:
        """Test validate-auxiliary-report with valid integration-verifier report."""
        report_file = os.path.join(self.tmp_dir.name, "iv.json")
        with open(report_file, "w") as f:
            json.dump(
                {
                    "status": "PASS",
                    "acceptanceCriteria": [],
                    "crossRoleIssues": [],
                    "testResults": {"passed": 10, "failed": 0},
                    "endToEndVerification": {"status": "ok"},
                    "summary": "All pass",
                },
                f,
            )

        args = argparse.Namespace(
            artifact_path=report_file, type="integration-verifier"
        )
        exit_code, result = self._run_cmd(cmd_validate_auxiliary_report, args)
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertEqual(result["artifactSummary"]["status"], "PASS")

    def test_validate_auxiliary_report_regression_checker_valid(self) -> None:
        """Test validate-auxiliary-report with valid regression-checker report."""
        report_file = os.path.join(self.tmp_dir.name, "rc.json")
        with open(report_file, "w") as f:
            json.dump(
                {
                    "passed": True,
                    "changes": ["file.py"],
                    "regressions": [],
                    "summary": "No regressions",
                },
                f,
            )

        args = argparse.Namespace(artifact_path=report_file, type="regression-checker")
        exit_code, result = self._run_cmd(cmd_validate_auxiliary_report, args)
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])

    def test_validate_auxiliary_report_memory_curator_valid(self) -> None:
        """Test validate-auxiliary-report with valid memory-curator report."""
        report_file = os.path.join(self.tmp_dir.name, "mc.json")
        with open(report_file, "w") as f:
            json.dump(
                {"memories": [{"content": "learned something"}], "summary": "1 memory"},
                f,
            )

        args = argparse.Namespace(artifact_path=report_file, type="memory-curator")
        exit_code, result = self._run_cmd(cmd_validate_auxiliary_report, args)
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertEqual(result["artifactSummary"]["memoryCount"], 1)

    def test_validate_auxiliary_report_invalid_schema(self) -> None:
        """Test validate-auxiliary-report rejects invalid schema."""
        report_file = os.path.join(self.tmp_dir.name, "bad_aux.json")
        with open(report_file, "w") as f:
            json.dump({"random": "data"}, f)

        args = argparse.Namespace(artifact_path=report_file, type="challenger")
        exit_code, result = self._run_cmd(cmd_validate_auxiliary_report, args)
        self.assertEqual(exit_code, 1)
        self.assertFalse(result["ok"])

    # ================================================================
    # Tests for cmd_worker_completion_validate
    # ================================================================

    def test_worker_completion_validate_valid(self) -> None:
        """Test worker-completion-validate with valid report."""
        report = {
            "role": "api-dev",
            "achieved": True,
            "filesChanged": ["api.py"],
            "acceptanceCriteria": [
                {"criterion": "API works", "passed": True, "evidence": "tests pass"}
            ],
            "keyDecisions": ["Used REST"],
            "contextForDependents": "API at /api/v1",
        }
        _, result = self._run_cmd_with_stdin(
            cmd_worker_completion_validate, argparse.Namespace(), report
        )
        self.assertTrue(result["ok"])

    def test_worker_completion_validate_missing_fields(self) -> None:
        """Test worker-completion-validate rejects missing fields."""
        report = {"role": "api-dev"}
        _, result = self._run_cmd_with_stdin(
            cmd_worker_completion_validate, argparse.Namespace(), report
        )
        self.assertFalse(result["ok"])

    # ================================================================
    # Tests for cmd_research_validate with recommendations
    # ================================================================

    def test_research_validate_with_recommendations(self) -> None:
        """Test research-validate with valid recommendations."""
        research_file = os.path.join(self.tmp_dir.name, "research_valid.json")
        with open(research_file, "w") as f:
            json.dump(
                {
                    "schemaVersion": 1,
                    "goal": "Evaluate caching strategy",
                    "sections": {"usagePatterns": {"summary": "Redis is common"}},
                    "recommendations": [
                        {
                            "action": "adopt",
                            "scope": "all services",
                            "designGoal": "Add Redis caching layer",
                            "reasoning": "Reduces latency by 80%",
                            "confidence": "high",
                            "effort": "medium",
                        }
                    ],
                    "contradictions": [],
                },
                f,
            )

        args = argparse.Namespace(research_path=research_file)
        exit_code, result = self._run_cmd(cmd_research_validate, args)
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertEqual(result["recommendationCount"], 1)

    def test_research_validate_invalid_action(self) -> None:
        """Test research-validate rejects invalid action enum."""
        research_file = os.path.join(self.tmp_dir.name, "bad_research.json")
        with open(research_file, "w") as f:
            json.dump(
                {
                    "schemaVersion": 1,
                    "goal": "Test",
                    "sections": {},
                    "recommendations": [
                        {
                            "action": "unknown-action",
                            "scope": "all",
                            "reasoning": "test",
                            "confidence": "high",
                            "effort": "small",
                        }
                    ],
                    "contradictions": [],
                },
                f,
            )

        args = argparse.Namespace(research_path=research_file)
        exit_code, result = self._run_cmd(cmd_research_validate, args)
        self.assertEqual(exit_code, 1)
        self.assertFalse(result["ok"])

    def test_research_validate_missing_design_goal(self) -> None:
        """Test research-validate requires designGoal for adopt/adapt actions."""
        research_file = os.path.join(self.tmp_dir.name, "no_goal_research.json")
        with open(research_file, "w") as f:
            json.dump(
                {
                    "schemaVersion": 1,
                    "goal": "Test",
                    "sections": {},
                    "recommendations": [
                        {
                            "action": "adopt",
                            "scope": "all",
                            "reasoning": "good idea",
                            "confidence": "medium",
                            "effort": "small",
                            # designGoal missing — should fail
                        }
                    ],
                    "contradictions": [],
                },
                f,
            )

        args = argparse.Namespace(research_path=research_file)
        exit_code, result = self._run_cmd(cmd_research_validate, args)
        self.assertEqual(exit_code, 1)
        self.assertFalse(result["ok"])

    # ================================================================
    # Tests for cmd_research_summary with data
    # ================================================================

    def test_research_summary_with_recommendations(self) -> None:
        """Test research-summary formats recommendations for display."""
        research_file = os.path.join(self.tmp_dir.name, "research_sum.json")
        with open(research_file, "w") as f:
            json.dump(
                {
                    "schemaVersion": 1,
                    "goal": "Evaluate GraphQL",
                    "sections": {
                        "usagePatterns": {"summary": "Apollo is popular"},
                        "failurePatterns": {"summary": "N+1 is common"},
                    },
                    "recommendations": [
                        {
                            "action": "adopt",
                            "scope": "API layer",
                            "designGoal": "Replace REST with GraphQL",
                            "reasoning": "Reduces over-fetching",
                            "confidence": "high",
                            "effort": "large",
                        },
                        {
                            "action": "defer",
                            "scope": "mobile clients",
                            "reasoning": "Not ready yet",
                            "confidence": "medium",
                            "effort": "small",
                        },
                    ],
                    "contradictions": [],
                    "researchGaps": ["Need production data"],
                },
                f,
            )

        args = argparse.Namespace(research_path=research_file)
        exit_code, result = self._run_cmd(cmd_research_summary, args)
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertEqual(result["recommendationCount"], 2)
        self.assertEqual(result["sectionCount"], 2)
        self.assertEqual(result["verdict"], "adopt")
        self.assertEqual(result["researchGapCount"], 1)

    # ================================================================
    # Tests for cmd_memory_summary
    # ================================================================

    def test_memory_summary_with_data(self) -> None:
        """Test memory-summary with existing memory entries."""
        args = argparse.Namespace(
            memory_path=self.fixtures["memory_file"],
            goal="api rest testing",
        )
        exit_code, result = self._run_cmd(cmd_memory_summary, args)
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertGreater(result["count"], 0)
        self.assertIn("entries", result)

    def test_memory_summary_not_found(self) -> None:
        """Test memory-summary with missing memory file."""
        args = argparse.Namespace(
            memory_path="/nonexistent/memory.jsonl",
            goal="test",
        )
        exit_code, result = self._run_cmd(cmd_memory_summary, args)
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 0)

    # ================================================================
    # Tests for cmd_memory_review with filters
    # ================================================================

    def test_memory_review_with_category_filter(self) -> None:
        """Test memory-review filters by category."""
        args = argparse.Namespace(
            memory_path=self.fixtures["memory_file"],
            category="pattern",
            keyword=None,
        )
        exit_code, result = self._run_cmd(cmd_memory_review, args)
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        for mem in result["memories"]:
            self.assertEqual(mem["category"], "pattern")

    def test_memory_review_with_keyword_filter(self) -> None:
        """Test memory-review filters by keyword."""
        args = argparse.Namespace(
            memory_path=self.fixtures["memory_file"],
            category=None,
            keyword="api",
        )
        exit_code, result = self._run_cmd(cmd_memory_review, args)
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertGreater(result["count"], 0)

    def test_memory_review_with_data(self) -> None:
        """Test memory-review with full data."""
        args = argparse.Namespace(
            memory_path=self.fixtures["memory_file"],
            category=None,
            keyword=None,
        )
        exit_code, result = self._run_cmd(cmd_memory_review, args)
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertGreater(result["total"], 0)
        self.assertIn("memories", result)
        self.assertIn("date", result["memories"][0])
        self.assertIn("id", result["memories"][0])

    # ================================================================
    # Tests for cmd_archive full path
    # ================================================================

    def test_archive_full_cycle(self) -> None:
        """Test archive moves non-persistent files and preserves persistent ones."""
        design_dir = os.path.join(self.tmp_dir.name, "archive_test")
        os.makedirs(design_dir, exist_ok=True)

        # Create persistent files
        for pf in ["memory.jsonl", "reflection.jsonl", "research.json"]:
            with open(os.path.join(design_dir, pf), "w") as f:
                f.write("persistent\n")

        # Create non-persistent files
        for nf in ["plan.json", "expert-arch.json", "cross-review.json", "handoff.md"]:
            with open(os.path.join(design_dir, nf), "w") as f:
                json.dump({"data": nf}, f)

        args = argparse.Namespace(design_dir=design_dir)
        exit_code, result = self._run_cmd(cmd_archive, args)
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertIn("archivedTo", result)

        # Persistent files still exist
        for pf in ["memory.jsonl", "reflection.jsonl", "research.json"]:
            self.assertTrue(
                os.path.exists(os.path.join(design_dir, pf)),
                f"Persistent file {pf} should survive archive",
            )

        # Non-persistent files moved to archive
        for nf in ["plan.json", "expert-arch.json", "cross-review.json"]:
            self.assertFalse(
                os.path.exists(os.path.join(design_dir, nf)),
                f"Non-persistent file {nf} should be archived",
            )

    def test_archive_nothing_to_archive(self) -> None:
        """Test archive with only persistent files."""
        design_dir = os.path.join(self.tmp_dir.name, "empty_archive")
        os.makedirs(design_dir, exist_ok=True)

        with open(os.path.join(design_dir, "memory.jsonl"), "w") as f:
            f.write("data\n")

        args = argparse.Namespace(design_dir=design_dir)
        exit_code, result = self._run_cmd(cmd_archive, args)
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertEqual(result.get("message"), "nothing to archive")

    # ================================================================
    # Tests for cmd_finalize validation paths
    # ================================================================

    def test_finalize_with_invalid_role_returns_error(self) -> None:
        """Test cmd_finalize returns ok=false for invalid role."""
        plan_file = os.path.join(self.tmp_dir.name, "invalid_role.json")
        plan = load_plan(self.fixtures["minimal_plan"])
        del plan["roles"][0]["goal"]
        with open(plan_file, "w") as f:
            json.dump(plan, f)

        args = argparse.Namespace(plan_path=plan_file)
        exit_code, result = self._run_cmd(cmd_finalize, args)
        # finalize uses output_json which always exits 0
        self.assertEqual(exit_code, 0)
        self.assertFalse(result["ok"])
        self.assertIn("issues", result)

    def test_finalize_validate_only_mode(self) -> None:
        """Test finalize in validate-only mode."""
        args = argparse.Namespace(
            plan_path=self.fixtures["minimal_plan"],
            validate_only=True,
        )
        exit_code, result = self._run_cmd(cmd_finalize, args)
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertTrue(result["validated"])

    def test_finalize_with_verification_specs(self) -> None:
        """Test finalize validates verificationSpecs."""
        plan_file = os.path.join(self.tmp_dir.name, "specs_plan.json")
        plan = load_plan(self.fixtures["minimal_plan"])
        plan["verificationSpecs"] = [
            {
                "role": "backend-developer",
                "path": ".design/specs/spec-backend.test.py",
                "runCommand": "python3 -m pytest .design/specs/",
                "properties": ["API returns JSON"],
            }
        ]
        with open(plan_file, "w") as f:
            json.dump(plan, f)

        args = argparse.Namespace(plan_path=plan_file)
        exit_code, result = self._run_cmd(cmd_finalize, args)
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])

    def test_finalize_invalid_verification_specs(self) -> None:
        """Test finalize rejects invalid verificationSpecs."""
        plan_file = os.path.join(self.tmp_dir.name, "bad_specs.json")
        plan = load_plan(self.fixtures["minimal_plan"])
        plan["verificationSpecs"] = [{"role": "nonexistent-role"}]
        with open(plan_file, "w") as f:
            json.dump(plan, f)

        args = argparse.Namespace(plan_path=plan_file)
        exit_code, result = self._run_cmd(cmd_finalize, args)
        self.assertEqual(exit_code, 0)
        self.assertFalse(result["ok"])

    def test_finalize_with_auxiliary_roles(self) -> None:
        """Test finalize validates auxiliary roles."""
        plan_file = os.path.join(self.tmp_dir.name, "aux_plan.json")
        plan = load_plan(self.fixtures["minimal_plan"])
        plan["auxiliaryRoles"] = [
            {
                "name": "challenger",
                "type": "pre-execution",
                "goal": "Review plan",
                "model": "sonnet",
                "trigger": "before-execution",
            }
        ]
        with open(plan_file, "w") as f:
            json.dump(plan, f)

        args = argparse.Namespace(plan_path=plan_file)
        exit_code, result = self._run_cmd(cmd_finalize, args)
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])

    def test_finalize_invalid_auxiliary_role(self) -> None:
        """Test finalize rejects invalid auxiliary role."""
        plan_file = os.path.join(self.tmp_dir.name, "bad_aux_plan.json")
        plan = load_plan(self.fixtures["minimal_plan"])
        plan["auxiliaryRoles"] = [{"name": "bad", "type": "invalid-type"}]
        with open(plan_file, "w") as f:
            json.dump(plan, f)

        args = argparse.Namespace(plan_path=plan_file)
        exit_code, result = self._run_cmd(cmd_finalize, args)
        self.assertEqual(exit_code, 0)
        self.assertFalse(result["ok"])

    # ================================================================
    # Tests for cmd_validate_checks edge cases
    # ================================================================

    def test_validate_checks_empty_check(self) -> None:
        """Test validate-checks detects empty check commands."""
        plan_file = os.path.join(self.tmp_dir.name, "empty_check.json")
        plan = load_plan(self.fixtures["minimal_plan"])
        plan["roles"][0]["acceptanceCriteria"][0]["check"] = ""
        with open(plan_file, "w") as f:
            json.dump(plan, f)

        args = argparse.Namespace(plan_path=plan_file)
        exit_code, result = self._run_cmd(cmd_validate_checks, args)
        self.assertEqual(exit_code, 0)
        self.assertFalse(result["ok"])

    def test_validate_checks_python_syntax_error(self) -> None:
        """Test validate-checks detects Python syntax errors."""
        plan_file = os.path.join(self.tmp_dir.name, "syntax_err.json")
        plan = load_plan(self.fixtures["minimal_plan"])
        plan["roles"][0]["acceptanceCriteria"][0]["check"] = "python3 -c 'if x'"
        with open(plan_file, "w") as f:
            json.dump(plan, f)

        args = argparse.Namespace(plan_path=plan_file)
        exit_code, result = self._run_cmd(cmd_validate_checks, args)
        # validate-checks uses output_json (exit 0) with ok=false
        self.assertEqual(exit_code, 0)
        self.assertFalse(result["ok"])

    # ================================================================
    # Tests for cmd_health_check edge cases
    # ================================================================

    def test_health_check_missing_plan_not_healthy(self) -> None:
        """Test health-check reports unhealthy when plan.json is missing."""
        design_dir = os.path.join(self.tmp_dir.name, "no_plan")
        os.makedirs(design_dir, exist_ok=True)

        args = argparse.Namespace(design_dir=design_dir)
        exit_code, result = self._run_cmd(cmd_health_check, args)
        # health-check always exits 0 with ok=true, healthy=true/false
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertFalse(result["healthy"])
        self.assertGreater(len(result["issues"]), 0)

    def test_health_check_with_memory_and_reflection(self) -> None:
        """Test health-check validates memory.jsonl and reflection.jsonl."""
        design_dir = os.path.join(self.tmp_dir.name, "full_health")
        os.makedirs(design_dir, exist_ok=True)

        plan_file = os.path.join(design_dir, "plan.json")
        with open(plan_file, "w") as f:
            json.dump({"schemaVersion": 4}, f)

        memory_file = os.path.join(design_dir, "memory.jsonl")
        with open(memory_file, "w") as f:
            f.write(
                json.dumps(
                    {
                        "id": "1",
                        "category": "pattern",
                        "content": "test",
                        "timestamp": "2025-01-01T00:00:00Z",
                    }
                )
                + "\n"
            )

        reflection_file = os.path.join(design_dir, "reflection.jsonl")
        with open(reflection_file, "w") as f:
            f.write(
                json.dumps(
                    {
                        "id": "1",
                        "skill": "design",
                        "goal": "test",
                        "outcome": "completed",
                        "timestamp": "2025-01-01T00:00:00Z",
                    }
                )
                + "\n"
            )

        args = argparse.Namespace(design_dir=design_dir)
        exit_code, result = self._run_cmd(cmd_health_check, args)
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertTrue(result["healthy"])

    # ================================================================
    # Tests for cmd_plan_health_summary with data
    # ================================================================

    def test_plan_health_summary_with_data(self) -> None:
        """Test plan-health-summary with reflections and plan."""
        design_dir = os.path.join(self.tmp_dir.name, "health_data")
        os.makedirs(design_dir, exist_ok=True)

        with open(os.path.join(design_dir, "reflection.jsonl"), "w") as f:
            f.write(
                json.dumps(
                    {
                        "skill": "execute",
                        "outcome": "completed",
                        "goal": "Build API",
                        "goalAchieved": True,
                        "timestamp": "2025-01-01T00:00:00Z",
                        "evaluation": {
                            "doNextTime": ["Use typed schemas"],
                            "whatFailed": ["Timeout on role 2"],
                        },
                    }
                )
                + "\n"
            )

        plan = load_plan(self.fixtures["minimal_plan"])
        plan["roles"][0]["status"] = "completed"
        with open(os.path.join(design_dir, "plan.json"), "w") as f:
            json.dump(plan, f)

        args = argparse.Namespace(design_dir=design_dir)
        exit_code, result = self._run_cmd(cmd_plan_health_summary, args)
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertGreater(len(result["reflections"]), 0)
        self.assertGreater(len(result["recentRuns"]), 0)
        self.assertEqual(result["recentRuns"][0]["goal"], "Build API")
        self.assertEqual(result["recentRuns"][0]["doNextTime"], ["Use typed schemas"])
        self.assertIn("1/2", result["plan"])

    # ================================================================
    # Tests for additional algorithm coverage
    # ================================================================

    def test_memory_add_new_entry(self) -> None:
        """Test cmd_memory_add adds a new entry (not boost/decay)."""
        memory_file = os.path.join(self.tmp_dir.name, "new_mem.jsonl")
        with open(memory_file, "w"):
            pass

        args = argparse.Namespace(
            memory_path=memory_file,
            category="convention",
            keywords="python,stdlib",
            content="Use pathlib over os.path",
            source="review",
            goal_context="code quality",
            importance=7,
            boost=False,
            decay=False,
            id=None,
        )
        exit_code, result = self._run_cmd(cmd_memory_add, args)
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertIn("id", result)
        self.assertEqual(result["category"], "convention")

    def test_reflection_search_filters_by_skill(self) -> None:
        """Test reflection-search with skill filter excludes other skills."""
        reflection_file = os.path.join(self.tmp_dir.name, "multi_ref.jsonl")
        with open(reflection_file, "w") as f:
            f.write(
                json.dumps(
                    {
                        "id": "1",
                        "skill": "design",
                        "goal": "A",
                        "outcome": "completed",
                        "goalAchieved": True,
                        "timestamp": "2025-01-01T00:00:00Z",
                        "evaluation": {},
                    }
                )
                + "\n"
            )
            f.write(
                json.dumps(
                    {
                        "id": "2",
                        "skill": "execute",
                        "goal": "B",
                        "outcome": "failed",
                        "goalAchieved": False,
                        "timestamp": "2025-01-02T00:00:00Z",
                        "evaluation": {},
                    }
                )
                + "\n"
            )
            f.write(
                json.dumps(
                    {
                        "id": "3",
                        "skill": "design",
                        "goal": "C",
                        "outcome": "partial",
                        "goalAchieved": False,
                        "timestamp": "2025-01-03T00:00:00Z",
                        "evaluation": {},
                    }
                )
                + "\n"
            )

        args = argparse.Namespace(
            reflection_path=reflection_file, skill="execute", limit=10
        )
        exit_code, result = self._run_cmd(cmd_reflection_search, args)
        self.assertEqual(exit_code, 0)
        self.assertEqual(len(result["reflections"]), 1)
        self.assertEqual(result["reflections"][0]["skill"], "execute")

    def test_is_surface_only_checks(self) -> None:
        """Test _is_surface_only detection."""
        self.assertTrue(_is_surface_only("grep -q pattern file"))
        self.assertTrue(_is_surface_only("test -f file.txt"))
        self.assertFalse(_is_surface_only("python3 -m pytest tests/"))
        self.assertFalse(_is_surface_only("grep pattern && exit 1"))

    def test_validate_role_brief_missing_model(self) -> None:
        """Test _validate_role_brief detects missing model."""
        role = {"name": "test", "goal": "test", "scope": {"directories": ["src/"]}}
        errors = _validate_role_brief(role, 0)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("model" in e for e in errors))

    def test_compute_cascading_failures_direct(self) -> None:
        """Test _compute_cascading_failures directly."""
        roles = [
            {"name": "a", "status": "failed"},
            {"name": "b", "status": "pending"},
            {"name": "c", "status": "pending"},
        ]
        dep_indices = [[], [0], [1]]
        cascaded = _compute_cascading_failures(roles, dep_indices, [0])
        self.assertGreater(len(cascaded), 0)
        names = [c["name"] for c in cascaded]
        self.assertIn("b", names)

    def test_tokenize(self) -> None:
        """Test _tokenize produces lowercase tokens."""
        tokens = _tokenize("Hello World Python3")
        self.assertIn("hello", tokens)
        self.assertIn("world", tokens)
        self.assertIn("python3", tokens)

    def test_tokenize_empty(self) -> None:
        """Test _tokenize with empty input."""
        self.assertEqual(_tokenize(""), set())
        self.assertEqual(_tokenize(None), set())

    def test_check_cycle_no_cycle(self) -> None:
        """Test _check_cycle with no cycle."""
        self.assertFalse(_check_cycle([[], [0], [1]]))

    def test_check_cycle_with_cycle(self) -> None:
        """Test _check_cycle detects cycle."""
        self.assertTrue(_check_cycle([[1], [0]]))


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    """Entry point for plan.py CLI."""
    parser = argparse.ArgumentParser(
        description="Deterministic operations for .design/plan.json (schema v4)"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Query commands
    p = subparsers.add_parser(
        "team-name", help="Generate project-unique team name for a skill"
    )
    p.add_argument(
        "skill", help="Skill name (design|execute|research|reflect|simplify)"
    )
    p.set_defaults(func=cmd_team_name)

    p = subparsers.add_parser("status", help="Validate plan and return status counts")
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_status)

    p = subparsers.add_parser(
        "summary", help="Role count, depth summary, and model distribution"
    )
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_summary)

    p = subparsers.add_parser("overlap-matrix", help="Build directory overlap matrix")
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_overlap_matrix)

    p = subparsers.add_parser(
        "tasklist-data", help="Extract data for TaskList creation"
    )
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_tasklist_data)

    p = subparsers.add_parser("worker-pool", help="Compute worker pool from roles")
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_worker_pool)

    p = subparsers.add_parser("retry-candidates", help="Find retryable failed roles")
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_retry_candidates)

    p = subparsers.add_parser("circuit-breaker", help="Check cascade failure threshold")
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_circuit_breaker)

    p = subparsers.add_parser(
        "memory-search", help="Search memory for relevant entries"
    )
    p.add_argument("memory_path", nargs="?", default=".design/memory.jsonl")
    p.add_argument("--goal", type=str, help="Goal or role goal text")
    p.add_argument("--stack", type=str, help="Technology stack context")
    p.add_argument("--keywords", type=str, help="Additional search keywords")
    p.add_argument("--limit", type=int, default=5, help="Max results to return")
    p.set_defaults(func=cmd_memory_search)

    # Mutation commands
    p = subparsers.add_parser("resume-reset", help="Reset in_progress roles to pending")
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_resume_reset)

    p = subparsers.add_parser(
        "memory-add",
        help="Add a new memory entry or update importance of existing entry",
    )
    p.add_argument("memory_path", nargs="?", default=".design/memory.jsonl")
    p.add_argument(
        "--category",
        help="Memory category (pattern|mistake|convention|approach|failure|procedure)",
    )
    p.add_argument("--keywords", help="Comma-separated keywords")
    p.add_argument("--content", help="Memory content")
    p.add_argument("--source", help="Source of the memory")
    p.add_argument("--goal-context", help="Goal context for the memory")
    p.add_argument(
        "--importance",
        type=int,
        default=5,
        help="Importance rating 1-10 (10 = most important, default: 5)",
    )
    p.add_argument("--boost", action="store_true", help="Increase importance by 1")
    p.add_argument("--decay", action="store_true", help="Decrease importance by 1")
    p.add_argument("--id", help="Entry ID to update (required for --boost/--decay)")
    p.set_defaults(func=cmd_memory_add)

    p = subparsers.add_parser(
        "memory-feedback",
        help="Boost/decay memories based on role outcomes (reads JSON from stdin)",
    )
    p.add_argument("memory_path", nargs="?", default=".design/memory.jsonl")
    p.set_defaults(func=cmd_memory_feedback)

    p = subparsers.add_parser(
        "update-status", help="Batch update role statuses (reads JSON from stdin)"
    )
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_update_status)

    # Reflection commands
    p = subparsers.add_parser("reflection-add", help="Add a self-reflection entry")
    p.add_argument("reflection_path", nargs="?", default=".design/reflection.jsonl")
    p.add_argument(
        "--skill",
        required=True,
        help="Skill name (design|execute|research|reflect|simplify)",
    )
    p.add_argument("--goal", required=True, help="The goal that was pursued")
    p.add_argument(
        "--outcome",
        required=True,
        help="Outcome (completed|partial|failed|aborted)",
    )
    p.add_argument(
        "--goal-achieved",
        type=lambda x: x.lower() in ("true", "1", "yes"),
        default=False,
        help="Whether the goal was achieved (true/false)",
    )
    p.set_defaults(func=cmd_reflection_add)

    p = subparsers.add_parser("reflection-search", help="Search past reflections")
    p.add_argument("reflection_path", nargs="?", default=".design/reflection.jsonl")
    p.add_argument("--skill", type=str, help="Filter by skill name")
    p.add_argument("--limit", type=int, default=5, help="Max results to return")
    p.set_defaults(func=cmd_reflection_search)

    # Research commands
    p = subparsers.add_parser(
        "research-validate", help="Validate research.json schema and recommendations"
    )
    p.add_argument("research_path", nargs="?", default=".design/research.json")
    p.set_defaults(func=cmd_research_validate)

    p = subparsers.add_parser(
        "research-summary", help="Extract summary from research.json for display"
    )
    p.add_argument("research_path", nargs="?", default=".design/research.json")
    p.set_defaults(func=cmd_research_summary)

    # Validation commands
    p = subparsers.add_parser(
        "validate-checks", help="Validate acceptance criteria check commands"
    )
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_validate_checks)

    p = subparsers.add_parser(
        "expert-validate", help="Validate expert artifact JSON schema"
    )
    p.add_argument("artifact_path", help="Path to expert artifact JSON file")
    p.set_defaults(func=cmd_expert_validate)

    p = subparsers.add_parser(
        "reflection-validate",
        help="Validate reflection evaluation schema (reads JSON from stdin)",
    )
    p.set_defaults(func=cmd_reflection_validate)

    p = subparsers.add_parser(
        "validate-auxiliary-report",
        help="Validate auxiliary report JSON against type-specific schema",
    )
    p.add_argument("artifact_path", help="Path to auxiliary report JSON file")
    p.add_argument(
        "--type",
        required=True,
        choices=[
            "challenger",
            "scout",
            "integration-verifier",
            "regression-checker",
            "memory-curator",
        ],
        help="Auxiliary type",
    )
    p.set_defaults(func=cmd_validate_auxiliary_report)

    p = subparsers.add_parser(
        "worker-completion-validate",
        help="Validate worker completion report schema (reads JSON from stdin)",
    )
    p.set_defaults(func=cmd_worker_completion_validate)

    p = subparsers.add_parser(
        "memory-summary", help="Format memory injection summary for user display"
    )
    p.add_argument("memory_path", nargs="?", default=".design/memory.jsonl")
    p.add_argument("--goal", type=str, help="Goal or context for memory search")
    p.set_defaults(func=cmd_memory_summary)

    p = subparsers.add_parser(
        "memory-review", help="List all memories in human-readable format"
    )
    p.add_argument("memory_path", nargs="?", default=".design/memory.jsonl")
    p.add_argument("--category", help="Filter by category")
    p.add_argument("--keyword", help="Filter by keyword")
    p.set_defaults(func=cmd_memory_review)

    # Trace commands
    p = subparsers.add_parser("trace-add", help="Append one trace event to trace.jsonl")
    p.add_argument("trace_path", nargs="?", default=".design/trace.jsonl")
    p.add_argument("--session-id", required=True, help="Session ID (e.g., TEAM_NAME)")
    p.add_argument(
        "--event",
        required=True,
        help="Event type (spawn|completion|failure|respawn|skill-start|skill-complete)",
    )
    p.add_argument(
        "--skill",
        required=True,
        help="Skill name (design|execute|research|reflect|simplify)",
    )
    p.add_argument(
        "--agent", help="Agent name (optional for skill-start/skill-complete)"
    )
    p.add_argument(
        "--role", help="Agent role (expert|worker|auxiliary|lead)", default=None
    )
    p.add_argument(
        "--payload", help="JSON object with event-specific data", default=None
    )
    p.set_defaults(func=cmd_trace_add)

    p = subparsers.add_parser(
        "trace-search", help="Search trace events with optional filters"
    )
    p.add_argument("trace_path", nargs="?", default=".design/trace.jsonl")
    p.add_argument("--session-id", help="Filter by session ID")
    p.add_argument("--skill", help="Filter by skill name")
    p.add_argument("--event", help="Filter by event type")
    p.add_argument("--agent", help="Filter by agent name")
    p.add_argument("--limit", type=int, default=50, help="Max results to return")
    p.set_defaults(func=cmd_trace_search)

    p = subparsers.add_parser(
        "trace-summary", help="Format trace data for human-readable display"
    )
    p.add_argument("trace_path", nargs="?", default=".design/trace.jsonl")
    p.add_argument("--session-id", help="Filter to a single session")
    p.set_defaults(func=cmd_trace_summary)

    p = subparsers.add_parser(
        "trace-validate", help="Schema validation for trace.jsonl entries"
    )
    p.add_argument("trace_path", nargs="?", default=".design/trace.jsonl")
    p.set_defaults(func=cmd_trace_validate)

    # Archive command
    p = subparsers.add_parser(
        "archive", help="Archive .design/ to history/{timestamp}/"
    )
    p.add_argument("design_dir", help="Design directory to archive (e.g., .design)")
    p.set_defaults(func=cmd_archive)

    # Build commands
    p = subparsers.add_parser(
        "finalize", help="Validate structure and compute directory overlaps"
    )
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate structure, skip overlap computation",
    )
    p.set_defaults(func=cmd_finalize)

    # Health and diff commands
    p = subparsers.add_parser(
        "health-check", help="Validate .design/ directory integrity"
    )
    p.add_argument("design_dir", nargs="?", default=".design")
    p.set_defaults(func=cmd_health_check)

    p = subparsers.add_parser("plan-diff", help="Compare two plan.json files")
    p.add_argument("plan_a", help="First plan file")
    p.add_argument("plan_b", help="Second plan file")
    p.set_defaults(func=cmd_plan_diff)

    p = subparsers.add_parser(
        "plan-health-summary",
        help="Show lifecycle context from reflections and plan status",
    )
    p.add_argument("design_dir", nargs="?", default=".design")
    p.set_defaults(func=cmd_plan_health_summary)

    # Sync check command
    p = subparsers.add_parser(
        "sync-check",
        help="Check drift between shared protocol blocks across SKILL.md files",
    )
    p.add_argument(
        "skills_dir", nargs="?", default="skills/", help="Path to skills directory"
    )
    p.set_defaults(func=cmd_sync_check)

    # Self-test command
    p = subparsers.add_parser(
        "self-test", help="Run self-tests on all commands using synthetic fixtures"
    )
    p.set_defaults(func=cmd_self_test)

    # Test-internal command
    p = subparsers.add_parser(
        "test-internal",
        help="Run internal unit tests with in-process coverage measurement",
    )
    p.set_defaults(
        func=lambda args: unittest.main(argv=["plan.py"], exit=True, verbosity=2)
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
