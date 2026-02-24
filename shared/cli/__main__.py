"""Entry point for python3 -m cli. Dispatches to domain CLI modules."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from typing import Any, NoReturn


class _StdoutArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that routes all output to stdout instead of stderr."""

    def _print_message(self, message: str, file: Any = None) -> None:
        # argparse calls this for help and error messages; always use stdout.
        if message:
            sys.stdout.write(message)

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stdout)
        self.exit(2, f"{self.prog}: error: {message}\n")

    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        if message:
            sys.stdout.write(message)
        sys.exit(status)


def _build_parser() -> _StdoutArgumentParser:
    parser = _StdoutArgumentParser(
        prog="python3 -m cli",
        description="Multi-agent goal decomposition and execution system.",
    )
    subparsers = parser.add_subparsers(dest="domain", metavar="DOMAIN")
    _register_domains(subparsers)

    return parser


def _register_domains(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Attempt to import and register each domain CLI module.

    Missing modules are silently skipped — they will be added by later roles.
    """
    domain_modules = [
        "cli.cli.spec",
        "cli.cli.memory",
        "cli.cli.reflection",
        "cli.cli.trace",
        "cli.cli.research",
        "cli.cli.plan",
        "cli.cli.archive",
    ]

    for module_path in domain_modules:
        try:
            mod = importlib.import_module(module_path)
            mod.register(subparsers)
        except (ImportError, ModuleNotFoundError):
            pass


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.domain is None:
        parser.print_help(sys.stdout)
        sys.exit(0)

    # Each domain handler is responsible for its own output.
    handler = getattr(args, "func", None)
    if handler is None:
        parser.print_help(sys.stdout)
        sys.exit(0)

    result = handler(args)
    if result is not None:
        print(json.dumps(result, separators=(",", ":"), ensure_ascii=True))


try:
    main()
except SystemExit:
    raise
except Exception as exc:
    _envelope = {
        "ok": False,
        "error": "INTERNAL_UNHANDLED_EXCEPTION",
        "message": str(exc),
    }
    print(json.dumps(_envelope, separators=(",", ":"), ensure_ascii=True))
    sys.exit(1)
