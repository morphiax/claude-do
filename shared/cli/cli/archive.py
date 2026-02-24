"""CLI commands for the archive operation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cli import envelope
from cli.ops import archive as ops_archive


def _cmd_archive(args: Any) -> None:
    result = ops_archive.archive(Path(args.root))
    print(envelope.render(result))


def register(subparsers: Any) -> None:
    """Register the 'archive' domain subparser."""
    archive_parser = subparsers.add_parser(
        "archive", help="Archive ephemeral state to history"
    )
    archive_parser.add_argument(
        "--root", required=True, help="Root directory containing state to archive"
    )
    archive_parser.set_defaults(func=_cmd_archive)
