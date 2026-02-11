#!/usr/bin/env python3
"""plan.py - Deterministic operations for .design/plan.json manipulation.

Query commands (read-only):
  validate, status-counts, summary, overlap-matrix, tasklist-data, worker-pool,
  extract-fields, model-distribution, retry-candidates, collect-files,
  circuit-breaker, extract-task

Mutation commands (modify plan.json):
  resume-reset, update-status

Build commands (validation & enrichment):
  validate-structure, assemble-prompts, compute-overlaps

All commands output JSON to stdout with top-level 'ok' field.
Exit code: 0 for success, 1 for errors.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
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


def compute_depths(tasks: list[dict[str, Any]]) -> dict[int, int]:
    """Compute dependency depth for each task. Returns dict {taskIndex: depth}."""
    depths: dict[int, int] = {}

    def get_depth(index: int, visited: set[int] | None = None) -> int:
        if visited is None:
            visited = set()

        if index in depths:
            return depths[index]

        if index in visited:
            # Cycle detected - return a large depth
            return 999

        task = tasks[index]
        blocked_by = task.get("blockedBy", [])

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

    for i in range(len(tasks)):
        if i not in depths:
            get_depth(i)

    return depths


def get_transitive_deps(
    tasks: list[dict[str, Any]], start_indices: list[int]
) -> set[int]:
    """Get all tasks transitively depending on start_indices (forward closure)."""
    # Build reverse dependency graph
    reverse_deps: dict[int, list[int]] = defaultdict(list)
    for i, task in enumerate(tasks):
        for dep in task.get("blockedBy", []):
            reverse_deps[dep].append(i)

    # BFS from start_indices through reverse edges
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

    # Remove the start indices themselves
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


def cmd_validate(args: argparse.Namespace) -> NoReturn:
    """Validate plan.json schema and structure."""
    plan_path = args.plan_path

    if not os.path.exists(plan_path):
        output_json({"ok": False, "error": "not_found"})

    try:
        with open(plan_path) as f:
            plan = json.load(f)
    except (json.JSONDecodeError, OSError):
        output_json({"ok": False, "error": "invalid_json"})

    schema_version = plan.get("schemaVersion")
    if schema_version != 3:
        output_json(
            {"ok": False, "error": "bad_schema", "schemaVersion": schema_version}
        )

    tasks = plan.get("tasks", [])
    if not tasks:
        output_json({"ok": False, "error": "empty_tasks"})

    output_json({"ok": True, "schemaVersion": schema_version, "taskCount": len(tasks)})


def cmd_status_counts(args: argparse.Namespace) -> NoReturn:
    """Count tasks by status and detect resume state."""
    plan = load_plan(args.plan_path)
    tasks = plan.get("tasks", [])

    counts: dict[str, int] = defaultdict(int)
    for task in tasks:
        status = task.get("status", "pending")
        counts[status] += 1

    total = len(tasks)
    is_resume = any(status != "pending" for status in counts)

    output_json(
        {"ok": True, "counts": dict(counts), "total": total, "isResume": is_resume}
    )


def cmd_summary(args: argparse.Namespace) -> NoReturn:
    """Compute taskCount, maxDepth, and depthSummary."""
    plan = load_plan(args.plan_path)
    tasks = plan.get("tasks", [])
    goal = plan.get("goal", "")

    task_count = len(tasks)
    depths = compute_depths(tasks)
    max_depth = max(depths.values()) if depths else 0

    # Build depth summary
    depth_summary: dict[str, list[str]] = defaultdict(list)
    for i, task in enumerate(tasks):
        depth = depths.get(i, 1)
        model = task.get("agent", {}).get("model", "")
        subject = task.get("subject", "")
        depth_summary[str(depth)].append(f"Task {i}: {subject} ({model})")

    # Model distribution
    model_counts: dict[str, int] = defaultdict(int)
    for task in tasks:
        model = task.get("agent", {}).get("model", "unknown")
        model_counts[model] += 1

    model_dist = ", ".join(
        f"{count} {model}" for model, count in sorted(model_counts.items())
    )

    output_json(
        {
            "ok": True,
            "goal": goal,
            "taskCount": task_count,
            "maxDepth": max_depth,
            "depthSummary": dict(depth_summary),
            "modelDistribution": model_dist,
        }
    )


def cmd_overlap_matrix(args: argparse.Namespace) -> NoReturn:
    """Build fileOverlapMatrix from task fileOverlaps fields."""
    plan = load_plan(args.plan_path)
    tasks = plan.get("tasks", [])

    matrix: dict[str, list[int]] = {}
    for i, task in enumerate(tasks):
        overlaps = task.get("fileOverlaps", [])
        if overlaps:
            matrix[str(i)] = overlaps

    output_json({"ok": True, "matrix": matrix})


def cmd_tasklist_data(args: argparse.Namespace) -> NoReturn:
    """Extract fields needed for TaskCreate calls."""
    plan = load_plan(args.plan_path)
    tasks = plan.get("tasks", [])

    result = []
    for i, task in enumerate(tasks):
        result.append(
            {
                "planIndex": i,
                "subject": task.get("subject", ""),
                "description": task.get("description", ""),
                "activeForm": task.get("activeForm", ""),
                "blockedBy": task.get("blockedBy", []),
                "status": task.get("status", "pending"),
            }
        )

    output_json({"ok": True, "tasks": result})


def _slugify_role(role: str) -> str:
    """Convert agent role to kebab-case slug for worker naming."""
    slug = role.lower()
    slug = re.sub(r"[_\s]+", "-", slug)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug)
    return slug.strip("-") or "worker"


def _most_common_model(tasks: list[dict[str, Any]], indices: list[int]) -> str:
    """Return the most common agent.model among the given task indices."""
    model_counts: dict[str, int] = defaultdict(int)
    for idx in indices:
        m = tasks[idx].get("agent", {}).get("model", "sonnet")
        model_counts[m] += 1
    return max(model_counts, key=lambda k: model_counts[k])


def _deduplicate_slug(slug: str, used_slugs: set[str]) -> str:
    """Return a unique slug by appending numeric suffixes if needed."""
    if slug not in used_slugs:
        return slug
    suffix = 2
    while f"{slug}-{suffix}" in used_slugs:
        suffix += 1
    return f"{slug}-{suffix}"


def cmd_worker_pool(args: argparse.Namespace) -> NoReturn:
    """Compute optimal worker count and role assignments from dependency graph."""
    plan = load_plan(args.plan_path)
    tasks = plan.get("tasks", [])

    # Collect pending tasks grouped by role
    role_tasks: dict[str, list[int]] = defaultdict(list)
    for i, task in enumerate(tasks):
        if task.get("status", "pending") != "pending":
            continue
        role = task.get("agent", {}).get("role", f"worker-{i}")
        role_tasks[role].append(i)

    if not role_tasks:
        output_json({"ok": True, "workers": [], "maxConcurrency": 0, "totalWorkers": 0})

    # Compute max dependency graph width
    depths = compute_depths(tasks)
    depth_groups: dict[int, list[int]] = defaultdict(list)
    for i, task in enumerate(tasks):
        if task.get("status", "pending") == "pending":
            depth_groups[depths.get(i, 1)].append(i)
    max_width = max((len(g) for g in depth_groups.values()), default=1)

    # Worker count = min(max_width, unique_roles, cap)
    worker_count = min(max_width, len(role_tasks), 8)

    # Sort roles by task count descending, take top N
    sorted_roles = sorted(role_tasks.items(), key=lambda x: len(x[1]), reverse=True)

    workers = []
    used_slugs: set[str] = set()
    for role_name, task_indices in sorted_roles[:worker_count]:
        model = _most_common_model(tasks, task_indices)
        slug = _deduplicate_slug(_slugify_role(role_name), used_slugs)
        used_slugs.add(slug)

        workers.append(
            {
                "name": slug,
                "role": role_name,
                "model": model,
                "taskCount": len(task_indices),
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


def cmd_extract_fields(args: argparse.Namespace) -> NoReturn:
    """Extract specific top-level fields from any JSON file."""
    json_path = args.json_path
    fields = args.fields

    if not os.path.exists(json_path):
        error_exit(f"File not found: {json_path}")

    try:
        with open(json_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        error_exit(f"Invalid JSON: {e}")

    result = {}
    for field in fields:
        if field in data:
            result[field] = data[field]

    output_json({"ok": True, "fields": result})


def cmd_model_distribution(args: argparse.Namespace) -> NoReturn:
    """Count tasks by agent.model value."""
    plan = load_plan(args.plan_path)
    tasks = plan.get("tasks", [])

    distribution: dict[str, int] = defaultdict(int)
    for task in tasks:
        model = task.get("agent", {}).get("model", "unknown")
        distribution[model] += 1

    formatted = ", ".join(
        f"{count} {model}" for model, count in sorted(distribution.items())
    )

    output_json(
        {"ok": True, "distribution": dict(distribution), "formatted": formatted}
    )


def cmd_retry_candidates(args: argparse.Namespace) -> NoReturn:
    """Find failed tasks with attempts < 3, extract prompt + failure context."""
    plan = load_plan(args.plan_path)
    tasks = plan.get("tasks", [])

    retryable = []
    for i, task in enumerate(tasks):
        status = task.get("status")
        attempts = task.get("attempts", 0)

        if status == "failed" and attempts < 3:
            agent = task.get("agent", {})
            retryable.append(
                {
                    "planIndex": i,
                    "subject": task.get("subject", ""),
                    "attempts": attempts,
                    "result": task.get("result", ""),
                    "prompt": task.get("prompt", ""),
                    "model": agent.get("model", ""),
                    "fallback": agent.get("fallback"),
                }
            )

    output_json({"ok": True, "retryable": retryable})


def cmd_collect_files(args: argparse.Namespace) -> NoReturn:
    """Collect create/modify files from specified completed tasks."""
    plan = load_plan(args.plan_path)
    tasks = plan.get("tasks", [])

    indices: list[int] = []
    if args.indices:
        indices = [int(x) for x in args.indices.split(",")]

    create_files: list[str] = []
    modify_files: list[str] = []

    for i in indices:
        if i >= len(tasks):
            continue

        task = tasks[i]
        if task.get("status") != "completed":
            continue

        metadata = task.get("metadata", {})
        files = metadata.get("files", {})

        create_files.extend(files.get("create", []))
        modify_files.extend(files.get("modify", []))

    # Remove duplicates while preserving order
    seen: set[str] = set()
    all_files: list[str] = []
    for f in create_files + modify_files:
        if f not in seen:
            seen.add(f)
            all_files.append(f)

    output_json(
        {
            "ok": True,
            "create": create_files,
            "modify": modify_files,
            "allFiles": all_files,
        }
    )


def cmd_circuit_breaker(args: argparse.Namespace) -> NoReturn:
    """Check if >50% of remaining tasks would be skipped by cascading failures."""
    plan = load_plan(args.plan_path)
    tasks = plan.get("tasks", [])

    total_tasks = len(tasks)
    pending_count = sum(1 for t in tasks if t.get("status") == "pending")

    # Find failed/blocked tasks
    failed_indices = [
        i for i, t in enumerate(tasks) if t.get("status") in ("failed", "blocked")
    ]

    # Compute transitive dependents
    would_skip = get_transitive_deps(tasks, failed_indices)
    would_be_skipped = len(
        [i for i in would_skip if tasks[i].get("status") == "pending"]
    )

    # Apply threshold: totalTasks > 3 AND wouldBeSkipped >= 50% of pending
    should_abort = (
        total_tasks > 3
        and pending_count > 0
        and would_be_skipped >= pending_count * 0.5
    )

    reason = ""
    if should_abort:
        reason = (
            f"Circuit breaker: {would_be_skipped}/{pending_count} "
            "pending tasks would be skipped"
        )

    output_json(
        {
            "ok": True,
            "totalTasks": total_tasks,
            "pendingCount": pending_count,
            "wouldBeSkipped": would_be_skipped,
            "shouldAbort": should_abort,
            "reason": reason,
        }
    )


def cmd_extract_task(args: argparse.Namespace) -> NoReturn:
    """Extract single task + plan context to .design/worker-task-{N}.json."""
    plan_path = args.plan_path
    plan_index = args.plan_index

    plan = load_plan(plan_path)
    tasks = plan.get("tasks", [])

    if plan_index >= len(tasks):
        error_exit(
            f"Task index {plan_index} out of range (plan has {len(tasks)} tasks)"
        )

    task = tasks[plan_index]

    # Extract plan-level context
    plan_context = plan.get("context", {})
    context = {
        "stack": plan_context.get("stack", ""),
        "conventions": plan_context.get("conventions", ""),
        "testCommand": plan_context.get("testCommand"),
        "buildCommand": plan_context.get("buildCommand"),
        "lsp": plan_context.get("lsp", {}),
    }

    # Build worker task file
    worker_data = {"planIndex": plan_index, "task": task, "context": context}

    # Write to .design/worker-task-{N}.json
    design_dir = os.path.dirname(plan_path)
    worker_path = os.path.join(design_dir, f"worker-task-{plan_index}.json")

    try:
        with open(worker_path, "w") as f:
            json.dump(worker_data, f, indent=2)

        size_bytes = os.path.getsize(worker_path)

        output_json({"ok": True, "path": worker_path, "sizeBytes": size_bytes})
    except OSError as e:
        error_exit(f"Failed to write worker task file: {e}")


# ============================================================================
# Mutation Commands
# ============================================================================


def cmd_resume_reset(args: argparse.Namespace) -> NoReturn:
    """Reset in_progress tasks to pending, increment attempts, report files."""
    plan_path = args.plan_path
    plan = load_plan(plan_path)
    tasks = plan.get("tasks", [])

    reset_tasks = []

    for i, task in enumerate(tasks):
        status = task.get("status")

        if status == "in_progress":
            # Reset to pending
            task["status"] = "pending"
            task["attempts"] = task.get("attempts", 0) + 1

            # Collect files to revert/delete
            metadata = task.get("metadata", {})
            files = metadata.get("files", {})

            reset_tasks.append(
                {
                    "planIndex": i,
                    "subject": task.get("subject", ""),
                    "filesToRevert": files.get("modify", []),
                    "filesToDelete": files.get("create", []),
                }
            )

    # Check if no pending tasks remain
    no_work_remaining = all(t.get("status") != "pending" for t in tasks)

    # Write updated plan
    atomic_write(plan_path, plan)

    output_json(
        {"ok": True, "resetTasks": reset_tasks, "noWorkRemaining": no_work_remaining}
    )


def _trim_dict_fields(d: dict[str, Any], keep_fields: set[str]) -> None:
    """Remove fields from dict that aren't in keep_fields."""
    keys_to_remove = [k for k in list(d.keys()) if k not in keep_fields]
    for k in keys_to_remove:
        del d[k]


def _trim_task_fields(
    task: dict[str, Any],
    keep_fields: set[str],
    keep_metadata_fields: set[str],
    keep_agent_fields: set[str],
) -> None:
    """Remove non-essential fields from a completed task."""
    _trim_dict_fields(task, keep_fields)

    if "metadata" in task:
        _trim_dict_fields(task["metadata"], keep_metadata_fields)

    if "agent" in task:
        _trim_dict_fields(task["agent"], keep_agent_fields)


def _apply_status_update(
    task: dict[str, Any],
    update: dict[str, Any],
    idx: int,
    updated: list[int],
    newly_failed: list[int],
    trimmed: list[int],
    plan: dict[str, Any],
) -> None:
    """Apply a single status update to a task."""
    keep_fields = {"subject", "status", "result", "metadata", "blockedBy", "agent"}
    keep_metadata_fields = {"files"}
    keep_agent_fields = {"role", "model"}

    new_status = update.get("status")

    if new_status:
        task["status"] = new_status
        updated.append(idx)

        if new_status in ("failed", "blocked"):
            newly_failed.append(idx)

    if "result" in update:
        task["result"] = update["result"]

    if new_status == "completed":
        _trim_task_fields(task, keep_fields, keep_metadata_fields, keep_agent_fields)
        trimmed.append(idx)

        if "progress" not in plan:
            plan["progress"] = {}
        if "completedTasks" not in plan["progress"]:
            plan["progress"]["completedTasks"] = []

        if idx not in plan["progress"]["completedTasks"]:
            plan["progress"]["completedTasks"].append(idx)


def _compute_cascading_failures(
    tasks: list[dict[str, Any]], newly_failed: list[int]
) -> list[dict[str, Any]]:
    """Compute which tasks should be skipped due to cascading failures."""
    cascaded: list[dict[str, Any]] = []
    if not newly_failed:
        return cascaded

    affected = get_transitive_deps(tasks, newly_failed)

    for idx in affected:
        if tasks[idx].get("status") == "pending":
            tasks[idx]["status"] = "skipped"

            for failed_idx in newly_failed:
                blocked_by = tasks[idx].get("blockedBy", [])
                if failed_idx in blocked_by:
                    cascaded.append(
                        {
                            "planIndex": idx,
                            "status": "skipped",
                            "reason": f"dependency on failed/blocked task {failed_idx}",
                        }
                    )
                    break

    return cascaded


def cmd_update_status(args: argparse.Namespace) -> NoReturn:
    """Batch update task statuses with progressive trimming and cascading failures."""
    plan_path = args.plan_path
    plan = load_plan(plan_path)
    tasks = plan.get("tasks", [])

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
        idx = update.get("planIndex")
        if idx is None or idx >= len(tasks):
            continue

        _apply_status_update(
            tasks[idx], update, idx, updated, newly_failed, trimmed, plan
        )

    cascaded = _compute_cascading_failures(tasks, newly_failed)

    atomic_write(plan_path, plan)

    output_json(
        {"ok": True, "updated": updated, "cascaded": cascaded, "trimmed": trimmed}
    )


# ============================================================================
# Build Commands
# ============================================================================


def _check_cycle(tasks: list[dict[str, Any]]) -> bool:
    """Check for cycles in blockedBy dependencies."""
    visited: set[int] = set()
    stack: set[int] = set()

    def visit(idx: int) -> bool:
        if idx in stack:
            return True
        if idx in visited:
            return False

        visited.add(idx)
        stack.add(idx)

        for dep in tasks[idx].get("blockedBy", []):
            if dep < len(tasks) and visit(dep):
                return True

        stack.remove(idx)
        return False

    return any(i not in visited and visit(i) for i in range(len(tasks)))


def _check_file_conflicts(tasks: list[dict[str, Any]]) -> list[str]:
    """Check for concurrent tasks modifying same files."""
    issues: list[str] = []
    file_writers: dict[str, list[int]] = defaultdict(list)

    for i, task in enumerate(tasks):
        files = task.get("metadata", {}).get("files", {})
        for f in files.get("modify", []) + files.get("create", []):
            file_writers[f].append(i)

    for f, writers in file_writers.items():
        if len(writers) <= 1:
            continue

        for i in range(len(writers)):
            for j in range(i + 1, len(writers)):
                idx1, idx2 = writers[i], writers[j]
                deps1 = get_transitive_deps(tasks, [idx1])
                deps2 = get_transitive_deps(tasks, [idx2])

                if idx2 not in deps1 and idx1 not in deps2:
                    issues.append(
                        f"File conflict: tasks {idx1} and {idx2} "
                        f"both modify {f} concurrently"
                    )
    return issues


def _check_task_count(tasks: list[dict[str, Any]]) -> list[str]:
    """Check if task count is valid."""
    issues: list[str] = []
    if len(tasks) == 0:
        issues.append("No tasks in plan")
    elif len(tasks) > 20:
        issues.append(f"Too many tasks: {len(tasks)} (max 20)")
    return issues


def _check_blocked_by_indices(tasks: list[dict[str, Any]]) -> list[str]:
    """Check if all blockedBy indices are valid."""
    issues: list[str] = []
    for i, task in enumerate(tasks):
        for dep in task.get("blockedBy", []):
            if dep >= len(tasks):
                issues.append(f"Task {i} has invalid blockedBy: {dep} >= {len(tasks)}")
    return issues


def _check_assumption_coverage(tasks: list[dict[str, Any]]) -> list[str]:
    """Check if blocking assumptions have rollback triggers."""
    issues: list[str] = []
    for i, task in enumerate(tasks):
        assumptions = task.get("agent", {}).get("assumptions", [])
        triggers = task.get("agent", {}).get("rollbackTriggers", [])
        blocking_count = sum(1 for a in assumptions if a.get("severity") == "blocking")
        if blocking_count > 0 and not triggers:
            issues.append(f"Task {i} has blocking assumptions but no rollback triggers")
    return issues


def _check_critical_path_depth(tasks: list[dict[str, Any]]) -> list[str]:
    """Check if critical path depth is within limits."""
    depths = compute_depths(tasks)
    max_depth = max(depths.values()) if depths else 0
    if max_depth > 8:
        return [f"Critical path depth too high: {max_depth} (max 8)"]
    return []


def cmd_validate_structure(args: argparse.Namespace) -> NoReturn:
    """Run 7 structural checks on plan.json."""
    plan = load_plan(args.plan_path)
    tasks = plan.get("tasks", [])
    issues: list[str] = []

    issues.extend(_check_task_count(tasks))
    issues.extend(_check_blocked_by_indices(tasks))

    if _check_cycle(tasks):
        issues.append("Cycle detected in blockedBy dependencies")

    issues.extend(_check_file_conflicts(tasks))
    issues.extend(_check_assumption_coverage(tasks))
    issues.extend(_check_critical_path_depth(tasks))

    output_json({"ok": len(issues) == 0, "issues": issues})


def _format_assumptions(assumptions: list[dict[str, Any]]) -> str:
    """Format assumptions as compact checklist lines."""
    if not assumptions:
        return ""
    lines = []
    for a in assumptions:
        sev = "BLOCKING" if a.get("severity") == "blocking" else "warning"
        lines.append(f"- [{sev}] {a.get('claim', '')}: `{a.get('verify', '')}`")
    return "\n".join(lines)


def _format_acceptance(criteria: list[dict[str, Any]]) -> str:
    """Format acceptance criteria as compact checklist lines."""
    if not criteria:
        return ""
    return "\n".join(
        f"- {ac.get('criterion', '')}: `{ac.get('check', '')}`" for ac in criteria
    )


def _format_files_section(metadata: dict[str, Any]) -> str:
    """Format file create/modify metadata into a single line."""
    files = metadata.get("files", {})
    create = files.get("create", [])
    modify = files.get("modify", [])
    if not create and not modify:
        return ""
    file_lines = []
    if create:
        file_lines.append(f"Create: {', '.join(create)}")
    if modify:
        file_lines.append(f"Modify: {', '.join(modify)}")
    return "**Files**: " + " | ".join(file_lines)


def _format_context_files(agent: dict[str, Any]) -> str:
    """Format contextFiles into a read-first section."""
    context_files = agent.get("contextFiles", [])
    if not context_files:
        return ""
    cf_lines = [
        f"- {cf.get('path', '')} ({cf.get('reason', '')})" for cf in context_files
    ]
    return "**Read first**:\n" + "\n".join(cf_lines)


def _format_agent_sections(agent: dict[str, Any]) -> list[str]:
    """Format agent constraints, rollback triggers, and acceptance criteria."""
    parts: list[str] = []

    assumptions = _format_assumptions(agent.get("assumptions", []))
    if assumptions:
        parts.append(f"**Pre-checks** (BLOCKING = stop if fails):\n{assumptions}")

    constraints = agent.get("constraints", [])
    if constraints:
        parts.append("**Constraints**: " + "; ".join(constraints))

    rollback = agent.get("rollbackTriggers", [])
    if rollback:
        parts.append("**Stop if**: " + " | ".join(rollback))

    acceptance = _format_acceptance(agent.get("acceptanceCriteria", []))
    if acceptance:
        parts.append(f"**Done when**:\n{acceptance}")

    return parts


def _assemble_task_prompt(
    task: dict[str, Any],
    agent: dict[str, Any],
    metadata: dict[str, Any],
    context: dict[str, Any],
) -> str:
    """Assemble a concise task brief for workers."""
    parts = [
        f"**Role**: {agent.get('role', 'Agent')}",
        f"**Task**: {task.get('subject', '')}",
        task.get("description", ""),
    ]

    approach = agent.get("approach", "")
    if approach:
        parts.append(f"**Approach**: {approach}")

    for section in (_format_files_section(metadata), _format_context_files(agent)):
        if section:
            parts.append(section)

    parts.extend(_format_agent_sections(agent))

    stack = context.get("stack", "")
    conventions = context.get("conventions", "")
    if stack or conventions:
        parts.append(f"**Project**: {stack}. {conventions}".strip())

    return "\n\n".join(parts)


def cmd_assemble_prompts(args: argparse.Namespace) -> NoReturn:
    """Assemble concise task briefs for all tasks and update plan.json."""
    plan_path = args.plan_path
    plan = load_plan(plan_path)
    tasks = plan.get("tasks", [])
    context = plan.get("context", {})

    assembled_count = 0

    for task in tasks:
        if "prompt" in task:
            continue

        agent = task.get("agent", {})
        metadata = task.get("metadata", {})

        task["prompt"] = _assemble_task_prompt(task, agent, metadata, context)
        assembled_count += 1

    atomic_write(plan_path, plan)
    output_json({"ok": True, "assembled": assembled_count})


def cmd_compute_overlaps(args: argparse.Namespace) -> NoReturn:
    """Compute fileOverlaps for concurrent task pairs based on file intersection."""
    plan_path = args.plan_path
    plan = load_plan(plan_path)
    tasks = plan.get("tasks", [])

    # For each task, compute its file set
    task_files: list[set[str]] = []
    for task in tasks:
        files = task.get("metadata", {}).get("files", {})
        all_files = set(files.get("create", []) + files.get("modify", []))
        task_files.append(all_files)

    # Compute fileOverlaps: tasks that could run concurrently and touch same files
    for i, task in enumerate(tasks):
        overlaps: list[int] = []

        for j in range(len(tasks)):
            if i == j:
                continue

            # Get transitive closure to check dependency relationship
            i_transitive = get_transitive_deps(tasks, [i])
            j_transitive = get_transitive_deps(tasks, [j])

            # If not in each other's dependency chains and files overlap, conflict
            if (
                j not in i_transitive
                and i not in j_transitive
                and task_files[i] & task_files[j]
            ):
                overlaps.append(j)

        task["fileOverlaps"] = overlaps

    # Write updated plan
    atomic_write(plan_path, plan)

    output_json({"ok": True, "computed": len(tasks)})


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    """Entry point for plan.py CLI."""
    parser = argparse.ArgumentParser(
        description="Deterministic operations for .design/plan.json"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Query commands
    p = subparsers.add_parser(
        "validate", help="Validate plan.json schema and structure"
    )
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_validate)

    p = subparsers.add_parser("status-counts", help="Count tasks by status")
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_status_counts)

    p = subparsers.add_parser(
        "summary", help="Compute task count, max depth, and depth summary"
    )
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_summary)

    p = subparsers.add_parser("overlap-matrix", help="Build file overlap matrix")
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_overlap_matrix)

    p = subparsers.add_parser(
        "tasklist-data", help="Extract data for TaskList creation"
    )
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_tasklist_data)

    p = subparsers.add_parser(
        "worker-pool", help="Compute optimal worker pool from dependency graph"
    )
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_worker_pool)

    p = subparsers.add_parser(
        "extract-fields", help="Extract specific fields from JSON file"
    )
    p.add_argument("json_path", help="Path to JSON file")
    p.add_argument("fields", nargs="+", help="Field names to extract")
    p.set_defaults(func=cmd_extract_fields)

    p = subparsers.add_parser("model-distribution", help="Count tasks by model")
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_model_distribution)

    p = subparsers.add_parser("retry-candidates", help="Find retryable failed tasks")
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_retry_candidates)

    p = subparsers.add_parser(
        "collect-files", help="Collect files from completed tasks"
    )
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.add_argument("--indices", help="Comma-separated task indices")
    p.set_defaults(func=cmd_collect_files)

    p = subparsers.add_parser("circuit-breaker", help="Check cascade failure threshold")
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_circuit_breaker)

    p = subparsers.add_parser("extract-task", help="Extract single task to worker file")
    p.add_argument("plan_index", type=int, help="Task index to extract")
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_extract_task)

    # Mutation commands
    p = subparsers.add_parser("resume-reset", help="Reset in_progress tasks to pending")
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_resume_reset)

    p = subparsers.add_parser(
        "update-status", help="Batch update task statuses (reads JSON from stdin)"
    )
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_update_status)

    # Build commands
    p = subparsers.add_parser(
        "validate-structure", help="Run 7 structural validation checks"
    )
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_validate_structure)

    p = subparsers.add_parser(
        "assemble-prompts", help="Assemble concise task briefs for all tasks"
    )
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_assemble_prompts)

    p = subparsers.add_parser(
        "compute-overlaps", help="Compute fileOverlaps for all tasks"
    )
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_compute_overlaps)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
