"""CLI commands for the behavioral spec registry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from cli import envelope
from cli.ops import spec as ops


def _parse_json_arg(value: str, flag: str) -> dict[str, Any]:
    """Parse a JSON string argument, exiting with error on failure."""
    try:
        result = json.loads(value)
        if not isinstance(result, dict):
            print(
                envelope.render(
                    envelope.err("SPEC_INVALID_JSON", f"--{flag} must be a JSON object")
                )
            )
            sys.exit(1)
        return result
    except json.JSONDecodeError as e:
        print(
            envelope.render(
                envelope.err("SPEC_INVALID_JSON", f"--{flag} is not valid JSON: {e}")
            )
        )
        sys.exit(1)


def _cmd_register(args: argparse.Namespace) -> None:
    content = _parse_json_arg(args.json, "json")
    result = ops.register(Path(args.root), args.id, args.type, content)
    print(envelope.render(result))


def _cmd_list(args: argparse.Namespace) -> None:
    result = ops.list_specs(Path(args.root))
    print(envelope.render(result))


def _cmd_satisfy(args: argparse.Namespace) -> None:
    proof = _parse_json_arg(args.json, "json")
    result = ops.satisfy(Path(args.root), args.id, proof)
    print(envelope.render(result))


def _cmd_preflight(args: argparse.Namespace) -> None:
    result = ops.preflight(Path(args.root))
    print(envelope.render(result))


def _cmd_divergence(args: argparse.Namespace) -> None:
    result = ops.divergence(Path(args.root), Path(args.spec_doc))
    print(envelope.render(result))


def _cmd_coverage(args: argparse.Namespace) -> None:
    ids = [i.strip() for i in args.ids.split(",") if i.strip()]
    result = ops.coverage(Path(args.root), ids)
    print(envelope.render(result))


def _cmd_tighten(args: argparse.Namespace) -> None:
    new_content = _parse_json_arg(args.json, "json")
    result = ops.tighten(Path(args.root), args.id, new_content)
    print(envelope.render(result))


def _cmd_count(args: argparse.Namespace) -> None:
    result = ops.count(Path(args.root))
    print(envelope.render(result))


def register(subparsers: Any) -> None:
    """Register the 'spec' domain subparser with all sub-commands."""
    spec_parser = subparsers.add_parser("spec", help="Behavioral spec registry")
    spec_sub = spec_parser.add_subparsers(dest="spec_cmd", metavar="COMMAND")

    # register
    p_register = spec_sub.add_parser("register", help="Register a new contract")
    p_register.add_argument("--root", required=True, help="Root directory")
    p_register.add_argument("--id", required=True, help="Contract ID")
    p_register.add_argument(
        "--type", required=True, choices=["execute", "review"], help="Contract type"
    )
    p_register.add_argument("--json", required=True, help="Content as JSON object")
    p_register.set_defaults(func=_cmd_register)

    # list
    p_list = spec_sub.add_parser("list", help="List all contracts")
    p_list.add_argument("--root", required=True, help="Root directory")
    p_list.set_defaults(func=_cmd_list)

    # satisfy
    p_satisfy = spec_sub.add_parser("satisfy", help="Record contract satisfaction")
    p_satisfy.add_argument("--root", required=True, help="Root directory")
    p_satisfy.add_argument("--id", required=True, help="Contract ID")
    p_satisfy.add_argument("--json", required=True, help="Proof as JSON object")
    p_satisfy.set_defaults(func=_cmd_satisfy)

    # preflight
    p_preflight = spec_sub.add_parser("preflight", help="Re-verify all satisfied contracts")
    p_preflight.add_argument("--root", required=True, help="Root directory")
    p_preflight.set_defaults(func=_cmd_preflight)

    # divergence
    p_divergence = spec_sub.add_parser("divergence", help="Detect doc/registry mismatches")
    p_divergence.add_argument("--root", required=True, help="Root directory")
    p_divergence.add_argument("--spec-doc", required=True, dest="spec_doc", help="Path to spec document")
    p_divergence.set_defaults(func=_cmd_divergence)

    # coverage
    p_coverage = spec_sub.add_parser("coverage", help="Check coverage for given IDs")
    p_coverage.add_argument("--root", required=True, help="Root directory")
    p_coverage.add_argument("--ids", required=True, help="Comma-separated contract IDs")
    p_coverage.set_defaults(func=_cmd_coverage)

    # tighten
    p_tighten = spec_sub.add_parser("tighten", help="Update contract content")
    p_tighten.add_argument("--root", required=True, help="Root directory")
    p_tighten.add_argument("--id", required=True, help="Contract ID")
    p_tighten.add_argument("--json", required=True, help="New content as JSON object")
    p_tighten.set_defaults(func=_cmd_tighten)

    # count
    p_count = spec_sub.add_parser("count", help="Count registered contracts")
    p_count.add_argument("--root", required=True, help="Root directory")
    p_count.set_defaults(func=_cmd_count)

    # Make spec_parser set func to show help when no sub-command given
    spec_parser.set_defaults(func=lambda a: spec_parser.print_help())
