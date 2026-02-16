#!/usr/bin/env python3
"""plan.py - Deterministic operations for .design/plan.json manipulation.

Schema version 4: Role-based briefs with goal-directed execution.

Query commands (read-only):
  team-name, status, summary, overlap-matrix, tasklist-data, worker-pool,
  retry-candidates, circuit-breaker, memory-search, reflection-search

Mutation commands (modify plan.json):
  resume-reset, update-status, memory-add, reflection-add

Build commands (validation & enrichment):
  finalize

All commands output JSON to stdout with top-level 'ok' field.
Exit code: 0 for success, 1 for errors.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from collections import defaultdict, deque
from typing import TYPE_CHECKING, Any, NoReturn

if TYPE_CHECKING:
    pass


# ============================================================================
# Shared Utilities
# ============================================================================


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
    import hashlib

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


_GREP_ONLY_PATTERN = re.compile(r"^\s*(grep|egrep|fgrep|rg)\s", re.IGNORECASE)


def _is_grep_only(check: str) -> bool:
    """Return True if a check command is purely a grep/pattern-match."""
    # Strip leading shell constructs like `! ` (negation)
    stripped = re.sub(r"^[!\s]+", "", check.strip())
    return bool(_GREP_ONLY_PATTERN.match(stripped))


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
        elif not _is_grep_only(check):
            has_functional = True
    if criteria and not has_functional:
        issues.append(
            f"Role {idx} ({name}): all acceptance criteria are grep-only — "
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

    output_json(
        {
            "ok": True,
            "validated": True,
            "computedOverlaps": computed,
            "roleCount": len(plan.get("roles", [])),
            "auxiliaryCount": len(plan.get("auxiliaryRoles", [])),
        }
    )


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
    timestamp = entry.get("timestamp", current_time)
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
        "timestamp": entry.get("timestamp", 0),
        "goal_context": entry.get("goal_context", ""),
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
    valid_categories = {"pattern", "mistake", "convention", "approach", "failure"}
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


def cmd_memory_add(args: argparse.Namespace) -> NoReturn:
    """Add a new memory entry to memory.jsonl."""
    memory_path = args.memory_path
    category = args.category
    keywords_str = args.keywords or ""
    content = args.content
    source = args.source or "unknown"
    goal_context = args.goal_context or ""
    importance = args.importance

    # Validate importance range
    if importance < 1 or importance > 10:
        error_exit("Importance must be between 1 and 10 (inclusive)")

    # Validate and parse inputs
    keywords = _validate_memory_input(category, content, keywords_str)

    # Create entry
    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": time.time(),
        "category": category,
        "keywords": keywords,
        "content": content,
        "source": source,
        "goal_context": goal_context,
        "importance": importance,
    }

    # Append to JSONL file
    try:
        _ensure_memory_dir(memory_path)
        with open(memory_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        error_exit(f"Error writing memory file: {e}")

    output_json(
        {
            "ok": True,
            "id": entry["id"],
            "category": category,
            "keywords": keywords,
            "importance": importance,
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
        "timestamp": time.time(),
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
    entries.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

    output_json({"ok": True, "reflections": entries[:limit]})


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

    p = subparsers.add_parser("memory-add", help="Add a new memory entry")
    p.add_argument("memory_path", nargs="?", default=".design/memory.jsonl")
    p.add_argument("--category", required=True, help="Memory category")
    p.add_argument("--keywords", required=True, help="Comma-separated keywords")
    p.add_argument("--content", required=True, help="Memory content")
    p.add_argument("--source", help="Source of the memory")
    p.add_argument("--goal-context", help="Goal context for the memory")
    p.add_argument(
        "--importance",
        type=int,
        default=5,
        help="Importance rating 1-10 (10 = most important, default: 5)",
    )
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

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
