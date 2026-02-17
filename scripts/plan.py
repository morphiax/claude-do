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
  finalize, expert-validate, reflection-validate

Archive command:
  archive

All commands output JSON to stdout with top-level 'ok' field.
Exit code: 0 for success, 1 for errors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
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
    if not os.path.exists(path):
        error_exit(f"Plan file not found: {path}")

    try:
        with open(path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        error_exit(f"Invalid JSON in plan file: {e}")
    except OSError as e:
        error_exit(f"Error reading plan file: {e}")


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


def resolve_dependencies(
    roles: list[dict[str, Any]], name_index: dict[str, int]
) -> list[list[int]]:
    """Resolve scope.dependencies (role names) to index lists."""
    resolved = []
    for role in roles:
        deps = role.get("scope", {}).get("dependencies", [])
        resolved.append([name_index[d] for d in deps if d in name_index])
    return resolved


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


def cmd_status(args: argparse.Namespace) -> NoReturn:
    """Validate plan and return status counts."""
    plan_path = args.plan_path

    if not os.path.exists(plan_path):
        error_exit("not_found")

    try:
        with open(plan_path) as f:
            plan = json.load(f)
    except (json.JSONDecodeError, OSError):
        error_exit("invalid_json")

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
    plan = load_plan(args.plan_path)
    roles = plan.get("roles", [])
    goal = plan.get("goal", "")

    name_index = build_name_index(roles)
    dep_indices = resolve_dependencies(roles, name_index)

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


def cmd_overlap_matrix(args: argparse.Namespace) -> NoReturn:
    """Compute directory overlap matrix between roles."""
    plan = load_plan(args.plan_path)
    roles = plan.get("roles", [])
    name_index = build_name_index(roles)
    dep_indices = resolve_dependencies(roles, name_index)

    # Collect directories + patterns per role
    role_dirs: list[set[str]] = []
    for role in roles:
        scope = role.get("scope", {})
        dirs = set(scope.get("directories", []))
        dirs.update(scope.get("patterns", []))
        role_dirs.append(dirs)

    matrix: dict[str, list[int]] = {}
    for i in range(len(roles)):
        overlaps: list[int] = []
        for j in range(len(roles)):
            if i == j:
                continue
            # Check directory overlap (prefix match or exact match)
            if _dirs_overlap(role_dirs[i], role_dirs[j]):
                # Only flag if no existing dependency ordering
                i_deps = set(_transitive_closure(dep_indices, i))
                j_deps = set(_transitive_closure(dep_indices, j))
                if j not in i_deps and i not in j_deps:
                    overlaps.append(j)
        if overlaps:
            matrix[str(i)] = overlaps

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
    plan = load_plan(args.plan_path)
    roles = plan.get("roles", [])
    name_index = build_name_index(roles)
    dep_indices = resolve_dependencies(roles, name_index)

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
    plan = load_plan(args.plan_path)
    roles = plan.get("roles", [])
    name_index = build_name_index(roles)
    dep_indices = resolve_dependencies(roles, name_index)

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
    plan = load_plan(args.plan_path)
    roles = plan.get("roles", [])
    name_index = build_name_index(roles)
    dep_indices = resolve_dependencies(roles, name_index)

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
    plan = load_plan(plan_path)
    roles = plan.get("roles", [])
    name_index = build_name_index(roles)
    dep_indices = resolve_dependencies(roles, name_index)

    try:
        updates = json.load(sys.stdin)
    except json.JSONDecodeError:
        error_exit("Invalid JSON in stdin")

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

    role_dirs: list[set[str]] = []
    for role in roles:
        scope = role.get("scope", {})
        dirs = set(scope.get("directories", []))
        dirs.update(scope.get("patterns", []))
        role_dirs.append(dirs)

    for i, role in enumerate(roles):
        overlaps: list[int] = []
        i_closure = set(_transitive_closure(dep_indices, i))
        for j in range(len(roles)):
            if i == j:
                continue
            j_closure = set(_transitive_closure(dep_indices, j))
            if (
                j not in i_closure
                and i not in j_closure
                and _dirs_overlap(role_dirs[i], role_dirs[j])
            ):
                overlaps.append(j)
        role["directoryOverlaps"] = overlaps

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


def _find_closing_quote(check: str, start_pos: int, quote_char: str) -> int:
    """Find matching closing quote. Returns index or -1 if not found."""
    end_pos = start_pos + 1
    if quote_char == "'":
        # Single quotes: find next single quote
        while end_pos < len(check):
            if check[end_pos] == "'":
                return end_pos
            end_pos += 1
    else:
        # Double quotes: find next unescaped double quote
        while end_pos < len(check):
            if check[end_pos] == "\\" and end_pos + 1 < len(check):
                end_pos += 2  # Skip escaped character
                continue
            if check[end_pos] == '"':
                return end_pos
            end_pos += 1
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
) -> tuple[list[str], list[str]]:
    """Check JSONL file validity. Returns (issues, warnings)."""
    issues = []
    warnings = []

    if not os.path.exists(file_path):
        return (issues, warnings)

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
                    missing = required_fields - set(entry.keys())
                    if missing:
                        warnings.append(
                            f"{file_label} line {line_num}: missing fields {missing}"
                        )
                except json.JSONDecodeError:
                    warnings.append(f"{file_label} line {line_num}: invalid JSON")
    except OSError as e:
        issues.append(f"Cannot read {file_label}: {e}")

    return (issues, warnings)


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
    mem_issues, mem_warnings = _check_jsonl_file(
        memory_path, {"id", "category", "content", "timestamp"}, "memory.jsonl"
    )
    all_issues.extend(mem_issues)
    all_warnings.extend(mem_warnings)

    # Check reflection.jsonl
    reflection_path = os.path.join(design_dir, "reflection.jsonl")
    ref_issues, ref_warnings = _check_jsonl_file(
        reflection_path,
        {"id", "skill", "goal", "outcome", "timestamp"},
        "reflection.jsonl",
    )
    all_issues.extend(ref_issues)
    all_warnings.extend(ref_warnings)

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
    added = len([c for c in criteria_b if c not in criteria_a])
    removed = len([c for c in criteria_a if c not in criteria_b])
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


def _load_memory_entries(memory_path: str) -> list[dict[str, Any]]:
    """Load and parse JSONL entries from memory file."""
    entries: list[dict[str, Any]] = []
    with open(memory_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # Skip malformed lines
    return entries


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

    if not os.path.exists(memory_path):
        output_json({"ok": True, "memories": []})

    query_tokens = _tokenize(query)
    if not query_tokens:
        output_json({"ok": True, "memories": []})

    try:
        entries = _load_memory_entries(memory_path)
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


def _ensure_memory_dir(memory_path: str) -> None:
    """Create parent directory for memory file if needed."""
    memory_dir = os.path.dirname(memory_path)
    if memory_dir and not os.path.exists(memory_dir):
        os.makedirs(memory_dir)


def _update_memory_importance(memory_path: str, entry_id: str, boost: bool) -> NoReturn:
    """Update importance of an existing memory entry."""
    if not os.path.exists(memory_path):
        error_exit(f"Memory file not found: {memory_path}")

    try:
        entries = _load_memory_entries(memory_path)
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
        _ensure_memory_dir(memory_path)
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
        _ensure_memory_dir(memory_path)
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

    if skill not in ("design", "execute", "improve", "reflect"):
        error_exit(f"Invalid skill '{skill}'. Must be one of: design, execute, improve")

    if outcome not in ("completed", "partial", "failed", "aborted"):
        error_exit(
            f"Invalid outcome '{outcome}'. "
            "Must be one of: completed, partial, failed, aborted"
        )

    if not goal:
        error_exit("Goal is required")

    # Read evaluation from stdin (JSON object)
    try:
        evaluation = json.load(sys.stdin)
    except json.JSONDecodeError:
        error_exit("Invalid JSON in stdin (expected evaluation object)")

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
        reflection_dir = os.path.dirname(reflection_path)
        if reflection_dir and not os.path.exists(reflection_dir):
            os.makedirs(reflection_dir)
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
        entries: list[dict[str, Any]] = []
        with open(reflection_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if skill_filter and entry.get("skill") != skill_filter:
                        continue
                    entries.append(entry)
                except json.JSONDecodeError:
                    pass
    except OSError as e:
        error_exit(f"Error reading reflection file: {e}")

    # Sort by timestamp descending (most recent first)
    entries.sort(key=lambda x: _parse_timestamp(x.get("timestamp", 0)), reverse=True)

    output_json({"ok": True, "reflections": entries[:limit]})


# ============================================================================
# Validation Commands
# ============================================================================


def cmd_expert_validate(args: argparse.Namespace) -> NoReturn:
    """Validate expert artifact JSON against minimal required schema.

    Required fields: summary, verificationProperties
    """
    artifact_path = args.artifact_path

    if not os.path.exists(artifact_path):
        error_exit(f"Artifact file not found: {artifact_path}")

    try:
        with open(artifact_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        error_exit(f"Invalid JSON in artifact: {e}")
    except OSError as e:
        error_exit(f"Error reading artifact: {e}")

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


def cmd_reflection_validate(args: argparse.Namespace) -> NoReturn:
    """Validate reflection evaluation JSON against minimal schema.

    Reads evaluation JSON from stdin.
    Required fields: whatWorked, whatFailed, doNextTime (all arrays)
    """
    _ = args  # Unused but required for dispatch compatibility
    try:
        evaluation = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        error_exit(f"Invalid JSON in evaluation: {e}")

    # Check required fields
    missing = []
    for field in ["whatWorked", "whatFailed", "doNextTime"]:
        if field not in evaluation:
            missing.append(field)

    if missing:
        error_exit(f"Missing required fields: {', '.join(missing)}")

    # Validate all required fields are arrays
    invalid = []
    for field in ["whatWorked", "whatFailed", "doNextTime"]:
        if not isinstance(evaluation.get(field), list):
            invalid.append(field)

    if invalid:
        error_exit(f"Fields must be arrays: {', '.join(invalid)}")

    output_json({"ok": True, "valid": True})


def _load_memories(memory_path: str) -> list[dict[str, Any]]:
    """Load memories from JSONL file."""
    memories = []
    try:
        with open(memory_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    memories.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return memories


def _score_and_format_memories(
    memories: list[dict[str, Any]], goal: str
) -> list[dict[str, Any]]:
    """Score memories by relevance and format for display."""

    def score_memory(mem: dict[str, Any]) -> float:
        content = mem.get("content", "").lower()
        keywords = mem.get("keywords", "")
        # Handle keywords as string or list
        if isinstance(keywords, list):
            keywords_str = " ".join(keywords).lower()
        else:
            keywords_str = str(keywords).lower()
        importance = mem.get("importance", 5)

        # Count keyword matches
        query_tokens = goal.lower().split()
        matches = sum(
            1 for token in query_tokens if token in content or token in keywords_str
        )

        # Recency decay (10% per 30 days)
        timestamp = _parse_timestamp(mem.get("timestamp", 0))
        if timestamp:
            age_days = (time.time() - timestamp) / 86400
            recency_factor = max(0.1, 1.0 - (age_days / 30) * 0.1)
        else:
            recency_factor = 1.0

        return matches * recency_factor * (importance / 10)

    # Score and sort
    scored = [(mem, score_memory(mem)) for mem in memories]
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
    memories = _load_memories(memory_path)
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


def _read_handoff_summary(design_dir: str) -> str:
    """Read first 5 lines of handoff.md as summary."""
    handoff_path = os.path.join(design_dir, "handoff.md")
    if not os.path.exists(handoff_path):
        return ""

    try:
        with open(handoff_path) as f:
            lines = [line.strip() for line in f if line.strip()]
            return "\n".join(lines[:5])
    except OSError:
        return ""


def _read_recent_reflections(design_dir: str) -> list[str]:
    """Read last 2 reflections and format as summaries."""
    reflection_path = os.path.join(design_dir, "reflection.jsonl")
    if not os.path.exists(reflection_path):
        return []

    try:
        with open(reflection_path) as f:
            entries = []
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            entries.sort(
                key=lambda x: _parse_timestamp(x.get("timestamp", 0)), reverse=True
            )
            recent = entries[:2]

            summaries = []
            for ref in recent:
                skill = ref.get("skill", "unknown")
                outcome = ref.get("outcome", "unknown")
                status = "succeeded" if ref.get("goalAchieved", False) else "failed"
                summaries.append(f"{skill}: {outcome} ({status})")
            return summaries
    except OSError:
        return []


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
    """Generate lifecycle context summary from handoff.md and recent reflections.

    Shows users where they are in the workflow lifecycle.
    """
    design_dir = args.design_dir

    handoff_summary = _read_handoff_summary(design_dir)
    reflection_summaries = _read_recent_reflections(design_dir)
    plan_status = _read_plan_status(design_dir)

    output_json(
        {
            "ok": True,
            "handoff": handoff_summary,
            "reflections": reflection_summaries,
            "plan": plan_status,
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
        all_memories = _load_memory_entries(memory_path)
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


def cmd_archive(args: argparse.Namespace) -> NoReturn:
    """Archive .design/ directory to history/{timestamp}/.

    Preserves persistent files: memory.jsonl, reflection.jsonl, handoff.md, history/
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
    persistent = {"memory.jsonl", "reflection.jsonl", "handoff.md", "history"}

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


def cmd_self_test(args: argparse.Namespace) -> NoReturn:
    """Run self-tests on all commands using synthetic fixtures.

    Creates a temporary directory with test fixtures, runs each command
    via subprocess to validate the full CLI path, and reports results.
    """
    _ = args  # Unused but required for dispatch signature

    # Track results
    results: list[dict[str, Any]] = []
    passed = 0
    failed = 0

    # Create temp directory for fixtures
    tmp_dir = tempfile.mkdtemp(prefix="plan-self-test-")

    try:
        # Get path to this script
        script_path = os.path.abspath(__file__)

        # Create fixtures
        fixtures = _create_fixtures(tmp_dir)

        # Run tests
        tests = [
            ("team-name", lambda: _test_team_name(script_path)),
            ("status", lambda: _test_status(script_path, fixtures["minimal_plan"])),
            ("summary", lambda: _test_summary(script_path, fixtures["minimal_plan"])),
            (
                "overlap-matrix",
                lambda: _test_overlap_matrix(script_path, fixtures["minimal_plan"]),
            ),
            (
                "tasklist-data",
                lambda: _test_tasklist_data(script_path, fixtures["minimal_plan"]),
            ),
            (
                "worker-pool",
                lambda: _test_worker_pool(script_path, fixtures["minimal_plan"]),
            ),
            (
                "retry-candidates",
                lambda: _test_retry_candidates(script_path, fixtures["failed_plan"]),
            ),
            (
                "circuit-breaker",
                lambda: _test_circuit_breaker(script_path, fixtures["failed_plan"]),
            ),
            (
                "memory-search",
                lambda: _test_memory_search(script_path, fixtures["memory_file"]),
            ),
            (
                "memory-add",
                lambda: _test_memory_add(script_path, fixtures["memory_file"]),
            ),
            (
                "memory-add --boost",
                lambda: _test_memory_boost(script_path, fixtures["memory_file"]),
            ),
            (
                "memory-add --decay",
                lambda: _test_memory_decay(script_path, fixtures["memory_file"]),
            ),
            (
                "memory-summary",
                lambda: _test_memory_summary(script_path, fixtures["memory_file"]),
            ),
            (
                "memory-review",
                lambda: _test_memory_review(script_path, fixtures["memory_file"]),
            ),
            (
                "reflection-add",
                lambda: _test_reflection_add(script_path, fixtures["reflection_file"]),
            ),
            (
                "reflection-search",
                lambda: _test_reflection_search(
                    script_path, fixtures["reflection_file"]
                ),
            ),
            ("reflection-validate", lambda: _test_reflection_validate(script_path)),
            (
                "validate-checks (valid)",
                lambda: _test_validate_checks_valid(
                    script_path, fixtures["minimal_plan"]
                ),
            ),
            (
                "validate-checks (invalid)",
                lambda: _test_validate_checks_invalid(
                    script_path, fixtures["bad_check_plan"]
                ),
            ),
            (
                "expert-validate",
                lambda: _test_expert_validate(script_path, fixtures["expert_artifact"]),
            ),
            (
                "update-status",
                lambda: _test_update_status(script_path, fixtures["minimal_plan"]),
            ),
            (
                "resume-reset",
                lambda: _test_resume_reset(script_path, fixtures["in_progress_plan"]),
            ),
            ("finalize", lambda: _test_finalize(script_path, fixtures["unfin_plan"])),
            (
                "health-check",
                lambda: _test_health_check(script_path, fixtures["design_dir"]),
            ),
            (
                "plan-diff",
                lambda: _test_plan_diff(
                    script_path, fixtures["minimal_plan"], fixtures["modified_plan"]
                ),
            ),
            (
                "plan-health-summary",
                lambda: _test_plan_health_summary(script_path, fixtures["design_dir"]),
            ),
            ("archive", lambda: _test_archive(script_path, fixtures["archive_dir"])),
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
            {"ok": True, "passed": passed, "failed": failed, "results": results}
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

    handoff_content = (
        "# Session Handoff\n\nGoal: Build API\nStatus: 2/2 roles completed"
    )
    with open(os.path.join(design_dir, "handoff.md"), "w") as f:
        f.write(handoff_content)

    # Archive directory (for testing archive command)
    archive_dir = os.path.join(tmp_dir, "test_archive")
    os.makedirs(archive_dir, exist_ok=True)

    # Create some files to archive
    shutil.copy(minimal_plan_path, os.path.join(archive_dir, "plan.json"))
    shutil.copy(expert_artifact_path, os.path.join(archive_dir, "expert-test.json"))

    # Add persistent files that should NOT be archived
    shutil.copy(memory_file_path, os.path.join(archive_dir, "memory.jsonl"))

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
                        "criterion": "Broken Python",
                        "check": 'python3 -c "print(f\'bad {d["x"]}\')"',
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


def _test_team_name(script_path: str) -> None:
    """Test team-name command."""
    output = _run_command(script_path, ["team-name", "design"])
    assert output.get("ok") is True, f"team-name failed: {output}"
    assert "teamName" in output, "team-name missing teamName field"
    assert output["teamName"].startswith("do-design-"), (
        f"Invalid team name pattern: {output['teamName']}"
    )


def _test_status(script_path: str, plan_path: str) -> None:
    """Test status command."""
    output = _run_command(script_path, ["status", plan_path])
    assert output.get("ok") is True, f"status failed: {output}"
    assert output.get("roleCount") == 2, (
        f"Expected 2 roles, got {output.get('roleCount')}"
    )
    assert "pending" in output.get("counts", {}), "status missing counts.pending"


def _test_summary(script_path: str, plan_path: str) -> None:
    """Test summary command."""
    output = _run_command(script_path, ["summary", plan_path])
    assert output.get("ok") is True, f"summary failed: {output}"
    assert output.get("roleCount") == 2, (
        f"Expected 2 roles, got {output.get('roleCount')}"
    )
    assert "maxDepth" in output, "summary missing maxDepth"


def _test_overlap_matrix(script_path: str, plan_path: str) -> None:
    """Test overlap-matrix command."""
    output = _run_command(script_path, ["overlap-matrix", plan_path])
    assert output.get("ok") is True, f"overlap-matrix failed: {output}"
    assert "matrix" in output, "overlap-matrix missing matrix field"
    assert isinstance(output["matrix"], dict), "overlap-matrix matrix is not a dict"


def _test_tasklist_data(script_path: str, plan_path: str) -> None:
    """Test tasklist-data command."""
    output = _run_command(script_path, ["tasklist-data", plan_path])
    assert output.get("ok") is True, f"tasklist-data failed: {output}"
    assert len(output.get("roles", [])) == 2, "tasklist-data should return 2 roles"
    # Role 1 depends on role 0
    assert 0 in output["roles"][1].get("blockedBy", []), (
        "Role 1 should be blocked by role 0"
    )


def _test_worker_pool(script_path: str, plan_path: str) -> None:
    """Test worker-pool command."""
    output = _run_command(script_path, ["worker-pool", plan_path])
    assert output.get("ok") is True, f"worker-pool failed: {output}"
    assert "totalWorkers" in output, "worker-pool missing totalWorkers"
    # Only role 0 is runnable (role 1 depends on it)
    assert output["totalWorkers"] >= 1, (
        "worker-pool should find at least 1 runnable worker"
    )


def _test_retry_candidates(script_path: str, plan_path: str) -> None:
    """Test retry-candidates command."""
    output = _run_command(script_path, ["retry-candidates", plan_path])
    assert output.get("ok") is True, f"retry-candidates failed: {output}"
    assert "retryable" in output, "retry-candidates missing retryable field"
    assert len(output["retryable"]) == 1, "Should find 1 retryable role (failed role 0)"


def _test_circuit_breaker(script_path: str, plan_path: str) -> None:
    """Test circuit-breaker command."""
    output = _run_command(script_path, ["circuit-breaker", plan_path])
    assert output.get("ok") is True, f"circuit-breaker failed: {output}"
    assert "shouldAbort" in output, "circuit-breaker missing shouldAbort field"
    assert isinstance(output["shouldAbort"], bool), "shouldAbort must be bool"


def _test_memory_search(script_path: str, memory_path: str) -> None:
    """Test memory-search command."""
    output = _run_command(
        script_path, ["memory-search", memory_path, "--goal", "api rest"]
    )
    assert output.get("ok") is True, f"memory-search failed: {output}"
    assert "memories" in output, "memory-search missing memories field"
    assert len(output["memories"]) > 0, "memory-search should find at least 1 match"


def _test_memory_add(script_path: str, memory_path: str) -> None:
    """Test memory-add command."""
    output = _run_command(
        script_path,
        [
            "memory-add",
            memory_path,
            "--category",
            "pattern",
            "--keywords",
            "test,self-test",
            "--content",
            "Self-test validates all commands",
            "--importance",
            "5",
        ],
    )
    assert output.get("ok") is True, f"memory-add failed: {output}"
    assert "id" in output, "memory-add missing id field"

    # Verify entry was actually added
    with open(memory_path) as f:
        lines = f.readlines()
    last_entry = json.loads(lines[-1])
    assert last_entry["content"] == "Self-test validates all commands", (
        "Memory entry not added correctly"
    )


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


def _test_memory_summary(script_path: str, memory_path: str) -> None:
    """Test memory-summary command."""
    output = _run_command(script_path, ["memory-summary", memory_path, "--goal", "api"])
    assert output.get("ok") is True, f"memory-summary failed: {output}"
    assert "count" in output, "memory-summary missing count field"
    assert "entries" in output, "memory-summary missing entries field"


def _test_memory_review(script_path: str, memory_path: str) -> None:
    """Test memory-review command."""
    output = _run_command(
        script_path, ["memory-review", memory_path, "--category", "pattern"]
    )
    assert output.get("ok") is True, f"memory-review failed: {output}"
    assert "memories" in output, "memory-review missing memories field"
    # All returned memories should have category=pattern
    for mem in output["memories"]:
        assert mem.get("category") == "pattern", (
            f"Expected category=pattern, got {mem.get('category')}"
        )


def _test_reflection_add(script_path: str, reflection_path: str) -> None:
    """Test reflection-add command."""
    evaluation = {
        "whatWorked": ["Good planning"],
        "whatFailed": ["Time estimates"],
        "doNextTime": ["Buffer more time"],
    }

    output = _run_command(
        script_path,
        [
            "reflection-add",
            reflection_path,
            "--skill",
            "execute",
            "--goal",
            "Test goal",
            "--outcome",
            "completed",
            "--goal-achieved",
            "true",
        ],
        stdin_data=json.dumps(evaluation),
    )
    assert output.get("ok") is True, f"reflection-add failed: {output}"
    assert "id" in output, "reflection-add missing id field"


def _test_reflection_search(script_path: str, reflection_path: str) -> None:
    """Test reflection-search command."""
    output = _run_command(
        script_path, ["reflection-search", reflection_path, "--skill", "execute"]
    )
    assert output.get("ok") is True, f"reflection-search failed: {output}"
    assert "reflections" in output, "reflection-search missing reflections field"
    # All returned reflections should have skill=execute
    for refl in output["reflections"]:
        assert refl.get("skill") == "execute", (
            f"Expected skill=execute, got {refl.get('skill')}"
        )


def _test_reflection_validate(script_path: str) -> None:
    """Test reflection-validate command."""
    valid_evaluation = {
        "whatWorked": ["Good"],
        "whatFailed": ["Bad"],
        "doNextTime": ["Better"],
    }

    output = _run_command(
        script_path, ["reflection-validate"], stdin_data=json.dumps(valid_evaluation)
    )
    assert output.get("ok") is True, (
        f"reflection-validate failed with valid input: {output}"
    )
    assert output.get("valid") is True, "reflection-validate should report valid=True"

    # Test invalid input
    invalid_evaluation = {"incomplete": "data"}
    output = _run_command(
        script_path, ["reflection-validate"], stdin_data=json.dumps(invalid_evaluation)
    )
    assert output.get("ok") is False, "reflection-validate should reject invalid input"


def _test_validate_checks_valid(script_path: str, plan_path: str) -> None:
    """Test validate-checks command with valid plan."""
    output = _run_command(script_path, ["validate-checks", plan_path])
    assert output.get("ok") is True, f"validate-checks failed on valid plan: {output}"
    assert "results" in output, "validate-checks missing results field"


def _test_validate_checks_invalid(script_path: str, plan_path: str) -> None:
    """Test validate-checks command with invalid Python syntax."""
    output = _run_command(script_path, ["validate-checks", plan_path])
    assert output.get("ok") is False, (
        "validate-checks should fail on plan with bad syntax"
    )
    assert "results" in output, "validate-checks missing results field"
    # Should find at least one invalid check
    invalid_checks = [r for r in output["results"] if not r.get("valid")]
    assert len(invalid_checks) > 0, "Should detect at least one invalid check"


def _test_expert_validate(script_path: str, artifact_path: str) -> None:
    """Test expert-validate command."""
    output = _run_command(script_path, ["expert-validate", artifact_path])
    assert output.get("ok") is True, f"expert-validate failed: {output}"
    assert output.get("valid") is True, (
        "expert-validate should report valid=True for valid artifact"
    )


def _test_update_status(script_path: str, plan_path: str) -> None:
    """Test update-status command."""
    updates = [{"roleIndex": 0, "status": "in_progress"}]

    output = _run_command(
        script_path, ["update-status", plan_path], stdin_data=json.dumps(updates)
    )
    assert output.get("ok") is True, f"update-status failed: {output}"
    assert 0 in output.get("updated", []), "Role 0 should be in updated list"

    # Verify the change was persisted
    with open(plan_path) as f:
        plan = json.load(f)
    assert plan["roles"][0]["status"] == "in_progress", "Role 0 status was not updated"


def _test_resume_reset(script_path: str, plan_path: str) -> None:
    """Test resume-reset command."""
    output = _run_command(script_path, ["resume-reset", plan_path])
    assert output.get("ok") is True, f"resume-reset failed: {output}"
    assert "resetRoles" in output, "resume-reset missing resetRoles field"

    # Verify role was reset
    with open(plan_path) as f:
        plan = json.load(f)
    assert plan["roles"][0]["status"] == "pending", "Role 0 should be reset to pending"
    assert plan["roles"][0]["attempts"] == 1, "Role 0 attempts should be incremented"


def _test_finalize(script_path: str, plan_path: str) -> None:
    """Test finalize command."""
    output = _run_command(script_path, ["finalize", plan_path])
    assert output.get("ok") is True, f"finalize failed: {output}"
    assert output.get("validated") is True, "finalize should report validated=True"

    # Verify plan was enriched
    with open(plan_path) as f:
        plan = json.load(f)
    assert "status" in plan["roles"][0], "finalize should add status field"
    assert "directoryOverlaps" in plan["roles"][0], (
        "finalize should add directoryOverlaps"
    )


def _test_health_check(script_path: str, design_dir: str) -> None:
    """Test health-check command."""
    output = _run_command(script_path, ["health-check", design_dir])
    assert output.get("ok") is True, f"health-check failed: {output}"
    assert "healthy" in output, "health-check missing healthy field"


def _test_plan_diff(script_path: str, plan_a: str, plan_b: str) -> None:
    """Test plan-diff command."""
    output = _run_command(script_path, ["plan-diff", plan_a, plan_b])
    assert output.get("ok") is True, f"plan-diff failed: {output}"
    assert "summary" in output, "plan-diff missing summary field"
    assert "modifiedRoles" in output, "plan-diff missing modifiedRoles field"


def _test_plan_health_summary(script_path: str, design_dir: str) -> None:
    """Test plan-health-summary command."""
    output = _run_command(script_path, ["plan-health-summary", design_dir])
    assert output.get("ok") is True, f"plan-health-summary failed: {output}"
    assert "handoff" in output, "plan-health-summary missing handoff field"
    assert "reflections" in output, "plan-health-summary missing reflections field"


def _test_archive(script_path: str, archive_dir: str) -> None:
    """Test archive command."""
    output = _run_command(script_path, ["archive", archive_dir])
    assert output.get("ok") is True, f"archive failed: {output}"
    assert "archivedTo" in output or "message" in output, (
        "archive missing archivedTo or message field"
    )

    # Verify persistent files remain
    assert os.path.exists(os.path.join(archive_dir, "memory.jsonl")), (
        "memory.jsonl should not be archived"
    )

    # Verify non-persistent files were moved
    assert not os.path.exists(os.path.join(archive_dir, "plan.json")), (
        "plan.json should be archived"
    )


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
    p.add_argument("skill", help="Skill name (design|execute|improve)")
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
        "update-status", help="Batch update role statuses (reads JSON from stdin)"
    )
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_update_status)

    # Reflection commands
    p = subparsers.add_parser("reflection-add", help="Add a self-reflection entry")
    p.add_argument("reflection_path", nargs="?", default=".design/reflection.jsonl")
    p.add_argument("--skill", required=True, help="Skill name (design|execute|improve)")
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
        help="Show lifecycle context from handoff and reflections",
    )
    p.add_argument("design_dir", nargs="?", default=".design")
    p.set_defaults(func=cmd_plan_health_summary)

    # Self-test command
    p = subparsers.add_parser(
        "self-test", help="Run self-tests on all commands using synthetic fixtures"
    )
    p.set_defaults(func=cmd_self_test)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
