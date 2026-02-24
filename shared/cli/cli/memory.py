"""CLI commands for the memory store."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from cli.ops import memory
from cli.envelope import err


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register memory subcommands onto the root subparsers."""
    parser = subparsers.add_parser("memory", help="Memory store operations")
    sub = parser.add_subparsers(dest="memory_cmd", metavar="CMD")

    # add
    p_add = sub.add_parser("add", help="Add a memory record")
    p_add.add_argument("--root", required=True, help="Storage root directory")
    p_add.add_argument("--json", dest="json_data", required=True, help="JSON record")
    p_add.set_defaults(func=_cmd_add)

    # search
    p_search = sub.add_parser("search", help="Search memory records")
    p_search.add_argument("--root", required=True, help="Storage root directory")
    p_search.add_argument("--keyword", required=True, help="Search keyword")
    p_search.set_defaults(func=_cmd_search)

    # boost
    p_boost = sub.add_parser("boost", help="Boost memory importance")
    p_boost.add_argument("--root", required=True, help="Storage root directory")
    p_boost.add_argument("--id", required=True, help="Record ID")
    p_boost.add_argument("--amount", required=True, type=int, help="Amount to boost")
    p_boost.set_defaults(func=_cmd_boost)

    # suppress
    p_suppress = sub.add_parser("suppress", help="Suppress a memory record")
    p_suppress.add_argument("--root", required=True, help="Storage root directory")
    p_suppress.add_argument("--id", required=True, help="Record ID")
    p_suppress.set_defaults(func=_cmd_suppress)


def _parse_json(raw: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    try:
        result: dict[str, Any] = json.loads(raw)
        return result, None
    except json.JSONDecodeError as exc:
        return None, err("MEMORY_INVALID_JSON", f"invalid JSON: {exc}")


def _cmd_add(args: argparse.Namespace) -> dict[str, Any]:
    data, error = _parse_json(args.json_data)
    if error is not None:
        return error
    assert data is not None
    return memory.add(Path(args.root), data)


def _cmd_search(args: argparse.Namespace) -> dict[str, Any]:
    return memory.search(Path(args.root), args.keyword)


def _cmd_boost(args: argparse.Namespace) -> dict[str, Any]:
    return memory.boost(Path(args.root), args.id, args.amount)


def _cmd_suppress(args: argparse.Namespace) -> dict[str, Any]:
    return memory.suppress(Path(args.root), args.id)
