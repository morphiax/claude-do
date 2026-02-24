"""CLI commands for plan finalization and execution helpers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from cli import envelope
from cli.ops import plan as ops_plan
from cli.store import atomic


def _cmd_finalize_file(args: argparse.Namespace) -> None:
    result = ops_plan.finalize_file(args.path)
    print(envelope.render(result))


def _cmd_order_file(args: argparse.Namespace) -> None:
    plan_data = atomic.read(Path(args.path))
    if plan_data is None:
        print(envelope.render(envelope.err("PLAN_FILE_NOT_FOUND", f"File not found: {args.path}")))
        return
    indices = ops_plan.order(plan_data)
    print(envelope.render(envelope.ok({"order": indices})))


def _cmd_transition(args: argparse.Namespace) -> None:
    result = ops_plan.transition(args.file, args.role_index, args.new_status)
    print(envelope.render(result))


def _cmd_snapshot_scope(args: argparse.Namespace) -> None:
    try:
        plan_data = json.loads(args.json)
    except json.JSONDecodeError as exc:
        print(envelope.render(envelope.err("PLAN_JSON_PARSE_ERROR", str(exc))))
        return
    files = ops_plan.snapshot_scope(plan_data, args.role_index)
    print(envelope.render(envelope.ok({"files": files})))


def _cmd_scope_check(args: argparse.Namespace) -> None:
    try:
        plan_data = json.loads(args.json)
    except json.JSONDecodeError as exc:
        print(envelope.render(envelope.err("PLAN_JSON_PARSE_ERROR", str(exc))))
        return
    result = ops_plan.scope_check(plan_data, args.role_index, args.file)
    print(envelope.render(envelope.ok({"in_scope": result})))


def _cmd_file_delta(args: argparse.Namespace) -> None:
    before = [f for f in args.before.split(",") if f] if args.before else []
    after = [f for f in args.after.split(",") if f] if args.after else []
    result = ops_plan.file_delta(before, after)
    print(envelope.render(envelope.ok(result)))


def _cmd_unexpected_outputs(args: argparse.Namespace) -> None:
    try:
        plan_data = json.loads(args.json)
    except json.JSONDecodeError as exc:
        print(envelope.render(envelope.err("PLAN_JSON_PARSE_ERROR", str(exc))))
        return
    files = [f for f in args.files.split(",") if f] if args.files else []
    result = ops_plan.unexpected_outputs(plan_data, args.role_index, files)
    print(envelope.render(envelope.ok({"unexpected": result})))


def _cmd_cascade(args: argparse.Namespace) -> None:
    result = ops_plan.cascade(args.file, args.role_index)
    print(envelope.render(result))


def _cmd_coverage(args: argparse.Namespace) -> None:
    try:
        plan_json = json.loads(args.plan_json)
        spec_json = json.loads(args.spec_json)
    except json.JSONDecodeError as exc:
        print(envelope.render(envelope.err("PLAN_JSON_PARSE_ERROR", str(exc))))
        return
    result = ops_plan.coverage(plan_json, spec_json)
    print(envelope.render(result))


def _cmd_execution_coverage(args: argparse.Namespace) -> None:
    try:
        plan_json = json.loads(args.plan_json)
        spec_json = json.loads(args.spec_json)
    except json.JSONDecodeError as exc:
        print(envelope.render(envelope.err("PLAN_JSON_PARSE_ERROR", str(exc))))
        return
    result = ops_plan.execution_coverage(plan_json, spec_json)
    print(envelope.render(result))


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the 'plan' subparser and all its sub-subcommands."""
    plan_parser = subparsers.add_parser("plan", help="Plan finalization and execution commands.")
    plan_sub = plan_parser.add_subparsers(dest="plan_cmd", metavar="COMMAND")

    # finalize-file
    p_ff = plan_sub.add_parser("finalize-file", help="Read, validate, and write a finalized plan.")
    p_ff.add_argument("path", help="Path to the plan JSON file.")
    p_ff.set_defaults(func=_cmd_finalize_file)

    # order-file
    p_of = plan_sub.add_parser("order-file", help="Return execution order for a finalized plan.")
    p_of.add_argument("path", help="Path to the finalized plan JSON file.")
    p_of.set_defaults(func=_cmd_order_file)

    # transition
    p_tr = plan_sub.add_parser("transition", help="Update a role's status in a plan file.")
    p_tr.add_argument("--file", required=True, help="Path to the plan JSON file.")
    p_tr.add_argument("--role-index", type=int, required=True, help="Index of the role.")
    p_tr.add_argument("--new-status", required=True, help="New status value.")
    p_tr.set_defaults(func=_cmd_transition)

    # snapshot-scope
    p_ss = plan_sub.add_parser("snapshot-scope", help="List existing files in a role's scope.")
    p_ss.add_argument("--json", required=True, dest="json", help="Plan JSON string.")
    p_ss.add_argument("--role-index", type=int, required=True, help="Role index.")
    p_ss.set_defaults(func=_cmd_snapshot_scope)

    # scope-check
    p_sc = plan_sub.add_parser("scope-check", help="Check if a file is in a role's scope.")
    p_sc.add_argument("--json", required=True, dest="json", help="Plan JSON string.")
    p_sc.add_argument("--role-index", type=int, required=True, help="Role index.")
    p_sc.add_argument("--file", required=True, help="File path to check.")
    p_sc.set_defaults(func=_cmd_scope_check)

    # file-delta
    p_fd = plan_sub.add_parser("file-delta", help="Compute added/removed files between snapshots.")
    p_fd.add_argument("--before", required=True, help="Comma-separated list of before files.")
    p_fd.add_argument("--after", required=True, help="Comma-separated list of after files.")
    p_fd.set_defaults(func=_cmd_file_delta)

    # unexpected-outputs
    p_uo = plan_sub.add_parser("unexpected-outputs", help="Check for files not in expected_outputs.")
    p_uo.add_argument("--json", required=True, dest="json", help="Plan JSON string.")
    p_uo.add_argument("--role-index", type=int, required=True, help="Role index.")
    p_uo.add_argument("--files", required=True, help="Comma-separated list of files.")
    p_uo.set_defaults(func=_cmd_unexpected_outputs)

    # cascade
    p_ca = plan_sub.add_parser("cascade", help="Mark transitively dependent pending roles as skipped.")
    p_ca.add_argument("--file", required=True, help="Path to the plan JSON file.")
    p_ca.add_argument("--role-index", type=int, required=True, help="Failed role index.")
    p_ca.set_defaults(func=_cmd_cascade)

    # coverage
    p_cv = plan_sub.add_parser("coverage", help="Cross-reference plan contract_ids against spec.")
    p_cv.add_argument("--plan-json", required=True, help="Plan JSON string.")
    p_cv.add_argument("--spec-json", required=True, help="Spec JSON string.")
    p_cv.set_defaults(func=_cmd_coverage)

    # execution-coverage
    p_ec = plan_sub.add_parser(
        "execution-coverage",
        help="Return execution coverage shape for the execute skill.",
    )
    p_ec.add_argument("--plan-json", required=True, help="Plan JSON string.")
    p_ec.add_argument("--spec-json", required=True, help="Spec JSON string (list of {id, status}).")
    p_ec.set_defaults(func=_cmd_execution_coverage)

    # Default handler when no sub-subcommand is given
    plan_parser.set_defaults(func=_plan_help(plan_parser))


def _plan_help(parser: argparse.ArgumentParser) -> Any:
    def _help(args: argparse.Namespace) -> None:
        parser.print_help()
    return _help
