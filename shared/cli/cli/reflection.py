"""CLI commands for the reflection store."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from cli.ops import reflection
from cli.envelope import err


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register reflection subcommands onto the root subparsers."""
    parser = subparsers.add_parser("reflection", help="Reflection store operations")
    sub = parser.add_subparsers(dest="reflection_cmd", metavar="CMD")
    parser.set_defaults(func=lambda a: parser.print_help())

    # add
    p_add = sub.add_parser("add", help="Add a reflection record")
    p_add.add_argument("--root", required=True, help="Storage root directory")
    p_add.add_argument("--json", dest="json_data", required=True, help="JSON record")
    p_add.set_defaults(func=_cmd_add)

    # list
    p_list = sub.add_parser("list", help="List reflection records")
    p_list.add_argument("--root", required=True, help="Storage root directory")
    p_list.add_argument("--lens", default=None, help="Filter by lens (product|process)")
    p_list.add_argument(
        "--urgency", default=None, help="Filter by urgency (immediate|deferred)"
    )
    p_list.add_argument(
        "--include-resolved",
        action="store_true",
        default=False,
        help="Include resolved findings in output",
    )
    p_list.set_defaults(func=_cmd_list)

    # resolve
    p_resolve = sub.add_parser("resolve", help="Resolve a reflection finding")
    p_resolve.add_argument("--root", required=True, help="Storage root directory")
    p_resolve.add_argument("--id", dest="finding_id", required=True, help="Finding ID to resolve")
    p_resolve.add_argument("--resolution", required=True, help="Resolution text")
    p_resolve.set_defaults(func=_cmd_resolve)


def _parse_json(raw: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    try:
        result: dict[str, Any] = json.loads(raw)
        return result, None
    except json.JSONDecodeError as exc:
        return None, err("REFLECTION_INVALID_JSON", f"invalid JSON: {exc}")


def _cmd_add(args: argparse.Namespace) -> dict[str, Any]:
    data, error = _parse_json(args.json_data)
    if error is not None:
        return error
    assert data is not None
    return reflection.add(Path(args.root), data)


def _cmd_list(args: argparse.Namespace) -> dict[str, Any]:
    return reflection.list_reflections(
        Path(args.root), args.lens, args.urgency, args.include_resolved
    )


def _cmd_resolve(args: argparse.Namespace) -> dict[str, Any]:
    return reflection.resolve(Path(args.root), args.finding_id, args.resolution)
