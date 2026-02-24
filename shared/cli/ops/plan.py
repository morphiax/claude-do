"""Plan finalization: structural validation, DAG cycle detection, and execution helpers."""

from __future__ import annotations

import copy
import fnmatch
import glob
import os
from pathlib import Path
from typing import Any

from cli import envelope
from cli.store import atomic

REQUIRED_ROLE_FIELDS = [
    "name",
    "goal",
    "contract_ids",
    "scope",
    "expected_outputs",
    "context",
    "constraints",
    "verification",
    "assumptions",
    "rollback_triggers",
    "fallback",
    "model",
    "dependencies",
]

VALID_MODELS = {"opus", "sonnet", "haiku"}
ACCEPTED_SCHEMA_VERSIONS = {1, 2}


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_schema_version(plan: dict[str, Any]) -> dict[str, Any] | None:
    """Return error envelope if schema_version is invalid, else None."""
    version = plan.get("schema_version")
    if version not in ACCEPTED_SCHEMA_VERSIONS:
        code = f"bad_schema_{version}"
        return envelope.err(code, f"Unsupported schema_version: {version!r}")
    return None


def _validate_role_count(roles: list[dict[str, Any]]) -> dict[str, Any] | None:
    if len(roles) == 0:
        return envelope.err("PLAN_TOO_FEW_ROLES", "Plan must have at least 1 role.")
    if len(roles) > 8:
        return envelope.err("PLAN_TOO_MANY_ROLES", "Plan must have at most 8 roles.")
    return None


def _validate_unique_names(roles: list[dict[str, Any]]) -> dict[str, Any] | None:
    seen: set[str] = set()
    for role in roles:
        name = role.get("name", "")
        if name in seen:
            return envelope.err(
                "PLAN_DUPLICATE_NAME", f"Duplicate role name: {name!r}"
            )
        seen.add(name)
    return None


def _validate_required_fields(roles: list[dict[str, Any]]) -> dict[str, Any] | None:
    for role in roles:
        name = role.get("name", "<unnamed>")
        for field in REQUIRED_ROLE_FIELDS:
            if field not in role:
                return envelope.err(
                    "PLAN_MISSING_FIELD",
                    f"Role {name!r} is missing required field: {field!r}",
                )
        model = role.get("model")
        if model not in VALID_MODELS:
            return envelope.err(
                "PLAN_INVALID_MODEL",
                f'Role "{name}" has invalid model "{model}"',
            )
    return None


def _build_name_index(roles: list[dict[str, Any]]) -> dict[str, int]:
    return {role["name"]: i for i, role in enumerate(roles)}


def _validate_dag(roles: list[dict[str, Any]], name_index: dict[str, int]) -> dict[str, Any] | None:
    """DFS with three-color marking to detect cycles. Returns error or None."""
    n = len(roles)
    # 0=white, 1=gray, 2=black
    color = [0] * n

    def dfs(node: int) -> bool:
        """Return True if cycle detected."""
        color[node] = 1
        for dep_name in roles[node].get("dependencies", []):
            dep_idx = name_index.get(dep_name)
            if dep_idx is None:
                continue  # unresolvable deps caught separately
            if color[dep_idx] == 1:
                return True
            if color[dep_idx] == 0 and dfs(dep_idx):
                return True
        color[node] = 2
        return False

    for i in range(n):
        if color[i] == 0 and dfs(i):
            return envelope.err(
                "PLAN_CIRCULAR_DEPENDENCY",
                "Circular dependency detected among roles.",
            )
    return None


def _validate_resolvable_dependencies(
    roles: list[dict[str, Any]], name_index: dict[str, int]
) -> dict[str, Any] | None:
    for role in roles:
        name = role.get("name", "<unnamed>")
        for dep_name in role.get("dependencies", []):
            if dep_name not in name_index:
                return envelope.err(
                    "PLAN_UNRESOLVABLE_DEPENDENCY",
                    f"Role {name!r} depends on unknown role: {dep_name!r}",
                )
    return None


def _self_dep_check(roles: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Detect self-references before DAG check (they are cycles)."""
    for role in roles:
        name = role.get("name", "")
        for dep in role.get("dependencies", []):
            if dep == name:
                return envelope.err(
                    "PLAN_CIRCULAR_DEPENDENCY",
                    f"Role {name!r} depends on itself.",
                )
    return None


# ---------------------------------------------------------------------------
# Directory overlap computation
# ---------------------------------------------------------------------------


def _paths_overlap(a: str, b: str) -> bool:
    """Return True if path a and path b share a common prefix (one contains the other)."""
    pa = Path(a).resolve()
    pb = Path(b).resolve()
    try:
        pa.relative_to(pb)
        return True
    except ValueError:
        pass
    try:
        pb.relative_to(pa)
        return True
    except ValueError:
        pass
    return False


def _compute_overlaps(roles: list[dict[str, Any]]) -> list[list[int]]:
    """Return per-role list of overlapping role indices."""
    n = len(roles)
    overlaps: list[list[int]] = [[] for _ in range(n)]
    for i in range(n):
        scope_i = roles[i].get("scope", [])
        for j in range(i + 1, n):
            scope_j = roles[j].get("scope", [])
            if any(_paths_overlap(str(si), str(sj)) for si in scope_i for sj in scope_j):
                overlaps[i].append(j)
                overlaps[j].append(i)
    return overlaps


# ---------------------------------------------------------------------------
# Public finalize
# ---------------------------------------------------------------------------


def finalize(plan_data: dict[str, Any]) -> dict[str, Any]:
    """Validate and finalize a plan dict. Returns ok/err envelope.

    Does NOT mutate plan_data; returns a new plan in envelope data.
    """
    # Work on original for validation; build copy only after passing
    roles = plan_data.get("roles", [])

    checks = [
        _validate_schema_version(plan_data),
        _validate_role_count(roles),
        _validate_unique_names(roles),
        _validate_required_fields(roles),
    ]
    for check in checks:
        if check is not None:
            return check

    name_index = _build_name_index(roles)

    more_checks = [
        _self_dep_check(roles),
        _validate_resolvable_dependencies(roles, name_index),
        _validate_dag(roles, name_index),
    ]
    for check in more_checks:
        if check is not None:
            return check

    # Build new plan (deep copy so input is not mutated)
    new_plan = copy.deepcopy(plan_data)
    new_roles = new_plan["roles"]

    overlaps = _compute_overlaps(new_roles)

    for i, role in enumerate(new_roles):
        role["status"] = "pending"
        role["dep_indices"] = [
            name_index[dep_name] for dep_name in role.get("dependencies", [])
        ]
        role["directory_overlaps"] = overlaps[i]

    return envelope.ok(new_plan)


def finalize_file(path: Path | str) -> dict[str, Any]:
    """Read plan from file, finalize, write back atomically. Returns envelope."""
    path = Path(path)
    plan_data = atomic.read(path)
    if plan_data is None:
        return envelope.err("PLAN_FILE_NOT_FOUND", f"Plan file not found: {path}")
    result = finalize(plan_data)
    if result["ok"]:
        atomic.write(path, result["data"])
    return result


# ---------------------------------------------------------------------------
# Status transition
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"in_progress", "skipped"}),
    "in_progress": frozenset({"completed", "failed"}),
    "completed": frozenset(),
    "failed": frozenset(),
    "skipped": frozenset(),
}


def transition(path: Path | str, role_index: int, new_status: str) -> dict[str, Any]:
    """Update a role's status field in the plan file. Returns envelope."""
    path = Path(path)
    plan_data = atomic.read(path)
    if plan_data is None:
        return envelope.err("PLAN_FILE_NOT_FOUND", f"Plan file not found: {path}")
    roles = plan_data.get("roles", [])
    if role_index < 0 or role_index >= len(roles):
        return envelope.err(
            "PLAN_ROLE_INDEX_OUT_OF_RANGE",
            f"Role index {role_index} out of range (0-{len(roles) - 1}).",
        )
    current_status = roles[role_index].get("status", "pending")
    allowed = _VALID_TRANSITIONS.get(current_status, frozenset())
    if new_status not in allowed:
        return envelope.err(
            "PLAN_INVALID_TRANSITION",
            f"Cannot transition role {role_index} from {current_status!r} to {new_status!r}.",
        )
    plan_data["roles"][role_index]["status"] = new_status
    atomic.write(path, plan_data)
    return envelope.ok({"role_index": role_index, "new_status": new_status})


# ---------------------------------------------------------------------------
# Topological ordering (Kahn's algorithm)
# ---------------------------------------------------------------------------


def order(plan: dict[str, Any]) -> list[int]:
    """Return topologically sorted role indices using Kahn's algorithm."""
    roles = plan.get("roles", [])
    n = len(roles)
    in_degree = [0] * n
    adj: list[list[int]] = [[] for _ in range(n)]

    for i, role in enumerate(roles):
        for dep_idx in role.get("dep_indices", []):
            adj[dep_idx].append(i)
            in_degree[i] += 1

    queue = [i for i in range(n) if in_degree[i] == 0]
    result: list[int] = []
    while queue:
        # Use sorted to produce deterministic output
        queue.sort()
        node = queue.pop(0)
        result.append(node)
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    return result


# ---------------------------------------------------------------------------
# Scope helpers
# ---------------------------------------------------------------------------


def snapshot_scope(plan: dict[str, Any], role_index: int) -> list[str]:
    """Return list of existing files matching the role's scope patterns."""
    roles = plan.get("roles", [])
    role = roles[role_index]
    scope = role.get("scope", [])
    files: list[str] = []
    seen: set[str] = set()
    for pattern in scope:
        for match in glob.glob(str(pattern), recursive=True):
            if os.path.isfile(match) and match not in seen:
                files.append(match)
                seen.add(match)
    return sorted(files)


def scope_check(plan: dict[str, Any], role_index: int, file: str) -> bool:
    """Return True if file is within the role's declared scope patterns."""
    roles = plan.get("roles", [])
    role = roles[role_index]
    scope = role.get("scope", [])
    file_path = Path(file).resolve()
    for pattern in scope:
        pattern_path = Path(pattern)
        # If pattern is a directory or prefix, check containment
        resolved_pattern = pattern_path.resolve() if pattern_path.exists() else pattern_path
        try:
            file_path.relative_to(resolved_pattern)
            return True
        except ValueError:
            pass
        pattern_str = str(pattern)
        if fnmatch.fnmatch(str(file_path), pattern_str) or fnmatch.fnmatch(file, pattern_str):
            return True
    return False


# ---------------------------------------------------------------------------
# File delta
# ---------------------------------------------------------------------------


def file_delta(
    before_files: list[str], after_files: list[str]
) -> dict[str, list[str]]:
    """Compute added/removed/modified files between two snapshots.

    For simplicity, 'modified' is not tracked (no hash); added and removed
    are computed by set difference.
    """
    before_set = set(before_files)
    after_set = set(after_files)
    return {
        "added": sorted(after_set - before_set),
        "removed": sorted(before_set - after_set),
        "modified": [],
    }


# ---------------------------------------------------------------------------
# Unexpected outputs
# ---------------------------------------------------------------------------


def unexpected_outputs(
    plan: dict[str, Any], role_index: int, files: list[str]
) -> list[str]:
    """Return files not in the role's expected_outputs."""
    roles = plan.get("roles", [])
    role = roles[role_index]
    expected = set(role.get("expected_outputs", []))
    return [f for f in files if f not in expected]


# ---------------------------------------------------------------------------
# Cascade
# ---------------------------------------------------------------------------


def cascade(path: Path | str, role_index: int) -> dict[str, Any]:
    """Mark transitively dependent pending roles as skipped. Returns envelope."""
    path = Path(path)
    plan_data = atomic.read(path)
    if plan_data is None:
        return envelope.err("PLAN_FILE_NOT_FOUND", f"Plan file not found: {path}")

    roles = plan_data.get("roles", [])
    n = len(roles)

    # Build adjacency: which roles depend on a given role
    dependents: list[list[int]] = [[] for _ in range(n)]
    for i, role in enumerate(roles):
        for dep_idx in role.get("dep_indices", []):
            dependents[dep_idx].append(i)

    # Count pending roles before BFS
    pending_before = sum(1 for r in roles if r.get("status") == "pending")

    # BFS from role_index
    skipped: list[int] = []
    queue = list(dependents[role_index])
    visited: set[int] = set()
    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)
        if roles[node].get("status") == "pending":
            roles[node]["status"] = "skipped"
            skipped.append(node)
        queue.extend(dependents[node])

    abort = len(skipped) > pending_before / 2
    atomic.write(path, plan_data)
    return envelope.ok(
        {
            "skipped_indices": sorted(skipped),
            "pending_before": pending_before,
            "abort": abort,
        }
    )


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------


def coverage(plan_json: dict[str, Any], spec_json: dict[str, Any]) -> dict[str, Any]:
    """Cross-reference plan contract_ids against spec registry.

    Returns envelope with matched, unmatched, and uncovered contract ids.
    """
    # Collect all contract_ids from plan roles
    plan_contracts: set[str] = set()
    for role in plan_json.get("roles", []):
        for cid in role.get("contract_ids", []):
            plan_contracts.add(cid)

    # Collect spec contract ids — try common locations
    spec_contracts: set[str] = set()
    if isinstance(spec_json, dict):
        # Try contracts list at top level
        for item in spec_json.get("contracts", []):
            cid = item.get("id") or item.get("contract_id")
            if cid:
                spec_contracts.add(cid)
        # Try registry
        for item in spec_json.get("registry", []):
            cid = item.get("id") or item.get("contract_id")
            if cid:
                spec_contracts.add(cid)

    matched = sorted(plan_contracts & spec_contracts)
    unmatched = sorted(plan_contracts - spec_contracts)
    uncovered = sorted(spec_contracts - plan_contracts)

    return envelope.ok(
        {
            "matched": matched,
            "unmatched_in_plan": unmatched,
            "uncovered_in_spec": uncovered,
        }
    )


def execution_coverage(plan: dict[str, Any], spec_data: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute execution coverage for the execute skill.

    Args:
        plan: Plan dict with a ``roles`` list; each role has ``contract_ids``.
        spec_data: List of dicts with ``id`` and ``status`` keys.

    Returns:
        Envelope with keys: missing, pending, satisfied, roles_to_execute,
        roles_to_skip, has_work.
    """
    # Build id -> status lookup from spec_data
    registry: dict[str, str] = {
        item["id"]: item["status"] for item in spec_data if "id" in item
    }

    missing: list[str] = []
    pending: list[str] = []
    satisfied: list[str] = []
    roles_to_execute: list[int] = []
    roles_to_skip: list[int] = []

    for idx, role in enumerate(plan.get("roles", [])):
        contract_ids: list[str] = role.get("contract_ids", [])
        role_has_pending = False
        role_all_satisfied = True  # vacuously true for empty contract_ids

        for cid in contract_ids:
            if cid not in registry:
                missing.append(cid)
                role_all_satisfied = False
            elif registry[cid] == "satisfied":
                satisfied.append(cid)
            else:
                pending.append(cid)
                role_has_pending = True
                role_all_satisfied = False

        if role_has_pending:
            roles_to_execute.append(idx)
        elif role_all_satisfied:
            roles_to_skip.append(idx)

    return envelope.ok(
        {
            "missing": sorted(set(missing)),
            "pending": sorted(set(pending)),
            "satisfied": sorted(set(satisfied)),
            "roles_to_execute": roles_to_execute,
            "roles_to_skip": roles_to_skip,
            "has_work": len(pending) > 0,
        }
    )
