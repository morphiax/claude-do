"""CLI commands for the trace store."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from cli.ops import trace
from cli.envelope import err


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register trace subcommands onto the root subparsers."""
    parser = subparsers.add_parser("trace", help="Trace store operations")
    sub = parser.add_subparsers(dest="trace_cmd", metavar="CMD")

    # add
    p_add = sub.add_parser("add", help="Append a trace event")
    p_add.add_argument("--root", required=True, help="Storage root directory")
    p_add.add_argument("--json", dest="json_data", required=True, help="JSON record")
    p_add.set_defaults(func=_cmd_add)


def _parse_json(raw: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    try:
        result: dict[str, Any] = json.loads(raw)
        return result, None
    except json.JSONDecodeError as exc:
        return None, err("TRACE_INVALID_JSON", f"invalid JSON: {exc}")


def _cmd_add(args: argparse.Namespace) -> dict[str, Any]:
    data, error = _parse_json(args.json_data)
    if error is not None:
        return error
    assert data is not None
    return trace.add(Path(args.root), data)
