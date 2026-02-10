#!/usr/bin/env python3
"""plan.py - Deterministic operations for .design/plan.json (design skill version).

Query commands (read-only):
  validate, status-counts, summary, extract-fields, model-distribution

Build commands (validation & enrichment):
  validate-structure, assemble-prompts, compute-overlaps

All commands output JSON to stdout with top-level 'ok' field.
Exit code: 0 for success, 1 for errors.
"""

from __future__ import annotations

import argparse
import json
import os
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

        if index >= len(tasks):
            # Invalid index - return a large depth
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


def _build_preflight_section(assumptions: list[dict[str, Any]]) -> str:
    """Build pre-flight section from assumptions."""
    if not assumptions:
        return ""

    checks = []
    for assumption in assumptions:
        severity = assumption.get("severity", "warning")
        label = "blocking" if severity == "blocking" else "warning"
        checks.append(
            f"- [ ] [{label}] {assumption.get('claim', '')}: "
            f"`{assumption.get('verify', '')}`"
        )

    return (
        "## Pre-flight\n"
        "Verify before starting. If BLOCKING check fails, "
        "return BLOCKED: followed by the reason.\n" + "\n".join(checks) + "\n"
    )


def _build_context_section(
    context_files: list[dict[str, Any]], context: dict[str, Any]
) -> str:
    """Build context section from context files and plan context."""
    if not context_files:
        return ""

    lines = [f"- {cf.get('path', '')} — {cf.get('reason', '')}" for cf in context_files]
    return (
        "## Context\n"
        "Read before implementing:\n"
        + "\n".join(lines)
        + "\n"
        + f"Project: {context.get('stack', '')}. "
        f"Conventions: {context.get('conventions', '')}.\n"
        f"Test: {context.get('testCommand', 'N/A')}\n"
    )


def _build_optional_sections(agent: dict[str, Any]) -> dict[str, str]:
    """Build optional sections (constraints, approach, rollback)."""
    sections: dict[str, str] = {}

    constraints = agent.get("constraints", [])
    sections["constraints"] = (
        ("Constraints:\n" + "\n".join(f"- {c}" for c in constraints) + "\n")
        if constraints
        else ""
    )

    approach = agent.get("approach", "")
    sections["approach"] = f"Approach: {approach}\n" if approach else ""

    rollback = agent.get("rollbackTriggers", [])
    sections["rollback"] = (
        (
            "\nRollback triggers — STOP immediately if any occur:\n"
            + "\n".join(f"- {t}" for t in rollback)
            + "\n"
        )
        if rollback
        else ""
    )

    return sections


def _build_acceptance_section(acceptance_criteria: list[dict[str, Any]]) -> str:
    """Build acceptance criteria section."""
    if not acceptance_criteria:
        return ""

    checks = [
        f"- [ ] {ac.get('criterion', '')}: `{ac.get('check', '')}`"
        for ac in acceptance_criteria
    ]
    return (
        "## After implementing\n"
        "1. Verify acceptance criteria:\n" + "\n".join(checks) + "\n"
        "   Fix failures before proceeding.\n"
        "2. Do NOT stage or commit — the lead handles git after the batch completes.\n"
    )


def _assemble_task_prompt(
    task: dict[str, Any],
    agent: dict[str, Any],
    metadata: dict[str, Any],
    context: dict[str, Any],
) -> str:
    """Assemble full S1-S9 prompt for a single task."""
    role = agent.get("role", "Agent")

    preflight = _build_preflight_section(agent.get("assumptions", []))
    context_section = _build_context_section(agent.get("contextFiles", []), context)

    files_create = metadata.get("files", {}).get("create", [])
    files_modify = metadata.get("files", {}).get("modify", [])
    task_section = (
        f"## Task: {task.get('subject', '')}\n"
        f"{task.get('description', '')}\n"
        f"Files to create: {', '.join(files_create) or '(none)'}\n"
        f"Files to modify: {', '.join(files_modify) or '(none)'}\n"
    )

    optional = _build_optional_sections(agent)
    acceptance = _build_acceptance_section(agent.get("acceptanceCriteria", []))

    output_section = (
        "\n## Output format\n"
        "The FINAL line of your output MUST be one of:\n"
        "- COMPLETED: {one-line summary}\n"
        "- FAILED: {reason}\n"
        "- BLOCKED: {reason}\n"
        "\n"
        "Do NOT write log files. Your FINAL status line is the only output "
        "consumed by the orchestrator."
    )

    return (
        f"You are a {role}\n\n"
        f"{preflight}\n"
        f"{context_section}\n"
        f"{task_section}\n"
        f"{optional['constraints']}\n"
        f"{optional['approach']}\n"
        f"{optional['rollback']}\n"
        f"{acceptance}\n"
        f"{output_section}"
    ).strip()


def cmd_assemble_prompts(args: argparse.Namespace) -> NoReturn:
    """Assemble S1-S9 template for all tasks and update plan.json."""
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
        description="Deterministic operations for .design/plan.json (design skill)"
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

    p = subparsers.add_parser(
        "extract-fields", help="Extract specific fields from JSON file"
    )
    p.add_argument("json_path", help="Path to JSON file")
    p.add_argument("fields", nargs="+", help="Field names to extract")
    p.set_defaults(func=cmd_extract_fields)

    p = subparsers.add_parser("model-distribution", help="Count tasks by model")
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_model_distribution)

    # Build commands
    p = subparsers.add_parser(
        "validate-structure", help="Run 7 structural validation checks"
    )
    p.add_argument("plan_path", nargs="?", default=".design/plan.json")
    p.set_defaults(func=cmd_validate_structure)

    p = subparsers.add_parser(
        "assemble-prompts", help="Assemble S1-S9 prompts for all tasks"
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
