"""CLI commands for the research store."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from cli.ops import research
from cli.envelope import err


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register research subcommands onto the root subparsers."""
    parser = subparsers.add_parser("research", help="Research store operations")
    sub = parser.add_subparsers(dest="research_cmd", metavar="CMD")

    # add
    p_add = sub.add_parser("add", help="Add a research artifact")
    p_add.add_argument("--root", required=True, help="Storage root directory")
    p_add.add_argument("--json", dest="json_data", required=True, help="JSON record")
    p_add.set_defaults(func=_cmd_add)

    # search
    p_search = sub.add_parser("search", help="Search research artifacts")
    p_search.add_argument("--root", required=True, help="Storage root directory")
    p_search.add_argument("--keyword", required=True, help="Search keyword")
    p_search.set_defaults(func=_cmd_search)

    # list
    p_list = sub.add_parser("list", help="List all research artifacts")
    p_list.add_argument("--root", required=True, help="Storage root directory")
    p_list.set_defaults(func=_cmd_list)


def _parse_json(raw: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    try:
        result: dict[str, Any] = json.loads(raw)
        return result, None
    except json.JSONDecodeError as exc:
        return None, err("RESEARCH_INVALID_JSON", f"invalid JSON: {exc}")


def _cmd_add(args: argparse.Namespace) -> dict[str, Any]:
    data, error = _parse_json(args.json_data)
    if error is not None:
        return error
    assert data is not None
    return research.add(Path(args.root), data)


def _cmd_search(args: argparse.Namespace) -> dict[str, Any]:
    return research.search(Path(args.root), args.keyword)


def _cmd_list(args: argparse.Namespace) -> dict[str, Any]:
    return research.list_research(Path(args.root))
