"""End-to-end integration tests that invoke python3 -m cli as a subprocess.

Critical requirement: stderr must ALWAYS be empty for every command.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PY = sys.executable
_SHARED = str(Path(__file__).resolve().parent.parent / "shared")


def _env() -> dict[str, str]:
    """Build subprocess environment with shared/ on PYTHONPATH."""
    env = os.environ.copy()
    env["PYTHONPATH"] = _SHARED + os.pathsep + env.get("PYTHONPATH", "")
    return env


def run(*args: str, cwd: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run python3 -m cli with the given args, capturing stdout and stderr."""
    return subprocess.run(  # noqa: S603
        [_PY, "-m", "cli", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=_env(),
    )


def assert_no_stderr(result: subprocess.CompletedProcess[str]) -> None:
    assert result.stderr == "", (
        f"Expected empty stderr, got:\n{result.stderr!r}\nstdout was:\n{result.stdout!r}"
    )


def parse_json(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    assert_no_stderr(result)
    parsed: dict[str, Any] = json.loads(result.stdout.strip())
    return parsed


def assert_ok(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    data = parse_json(result)
    assert data.get("ok") is True, f"Expected ok=True, got: {data}"
    return data


def assert_err(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    data = parse_json(result)
    assert data.get("ok") is False, f"Expected ok=False, got: {data}"
    return data


# ---------------------------------------------------------------------------
# Basic invocation
# ---------------------------------------------------------------------------


class TestHelpOutput:
    def test_help_exits_zero(self) -> None:
        result = run("--help")
        assert result.returncode == 0

    def test_help_produces_stdout(self) -> None:
        result = run("--help")
        assert result.stdout.strip() != ""

    def test_help_stderr_empty(self) -> None:
        result = run("--help")
        assert_no_stderr(result)

    def test_all_domains_in_help(self) -> None:
        result = run("--help")
        domains = ["spec", "memory", "reflection", "trace", "research", "plan", "archive"]
        for domain in domains:
            assert domain in result.stdout, f"Domain {domain!r} not in help output"


# ---------------------------------------------------------------------------
# Spec commands
# ---------------------------------------------------------------------------


class TestSpecCommands:
    def test_spec_list_empty(self, tmp_path: Path) -> None:
        result = run("spec", "list", "--root", str(tmp_path))
        assert result.returncode == 0
        data = assert_ok(result)
        assert data["data"] == []

    def test_spec_register(self, tmp_path: Path) -> None:
        result = run(
            "spec",
            "register",
            "--root",
            str(tmp_path),
            "--id",
            "T-1",
            "--type",
            "execute",
            "--json",
            '{"command":"true"}',
        )
        assert result.returncode == 0
        data = assert_ok(result)
        assert data["data"]["id"] == "T-1"

    def test_spec_list_after_register(self, tmp_path: Path) -> None:
        run(
            "spec",
            "register",
            "--root",
            str(tmp_path),
            "--id",
            "T-1",
            "--type",
            "execute",
            "--json",
            '{"command":"true"}',
        )
        result = run("spec", "list", "--root", str(tmp_path))
        assert result.returncode == 0
        data = assert_ok(result)
        ids = [s["id"] for s in data["data"]]
        assert "T-1" in ids


# ---------------------------------------------------------------------------
# Memory commands
# ---------------------------------------------------------------------------


class TestMemoryCommands:
    def test_memory_add(self, tmp_path: Path) -> None:
        payload = json.dumps(
            {
                "category": "design",
                "keywords": ["test"],
                "content": "test memory",
                "source": "test",
            }
        )
        result = run("memory", "add", "--root", str(tmp_path), "--json", payload)
        assert result.returncode == 0
        assert_ok(result)

    def test_memory_search(self, tmp_path: Path) -> None:
        payload = json.dumps(
            {
                "category": "design",
                "keywords": ["test"],
                "content": "test memory item",
                "source": "test",
            }
        )
        run("memory", "add", "--root", str(tmp_path), "--json", payload)
        result = run("memory", "search", "--root", str(tmp_path), "--keyword", "test")
        assert result.returncode == 0
        assert_ok(result)

    def test_memory_search_stderr_empty(self, tmp_path: Path) -> None:
        result = run("memory", "search", "--root", str(tmp_path), "--keyword", "test")
        assert_no_stderr(result)


# ---------------------------------------------------------------------------
# Trace commands
# ---------------------------------------------------------------------------


class TestTraceCommands:
    def test_trace_add(self, tmp_path: Path) -> None:
        result = run(
            "trace",
            "add",
            "--root",
            str(tmp_path),
            "--json",
            '{"event":"test"}',
        )
        assert result.returncode == 0
        assert_ok(result)

    def test_trace_add_stderr_empty(self, tmp_path: Path) -> None:
        result = run(
            "trace",
            "add",
            "--root",
            str(tmp_path),
            "--json",
            '{"event":"test"}',
        )
        assert_no_stderr(result)


# ---------------------------------------------------------------------------
# Reflection commands
# ---------------------------------------------------------------------------


class TestReflectionCommands:
    def test_reflection_add_valid(self, tmp_path: Path) -> None:
        payload = json.dumps(
            {
                "type": "retro",
                "outcome": "success",
                "lens": "product",
                "urgency": "deferred",
            }
        )
        result = run("reflection", "add", "--root", str(tmp_path), "--json", payload)
        assert result.returncode == 0
        assert_ok(result)

    def test_reflection_add_stderr_empty(self, tmp_path: Path) -> None:
        payload = json.dumps(
            {
                "type": "retro",
                "outcome": "success",
                "lens": "product",
                "urgency": "deferred",
            }
        )
        result = run("reflection", "add", "--root", str(tmp_path), "--json", payload)
        assert_no_stderr(result)


# ---------------------------------------------------------------------------
# Plan commands
# ---------------------------------------------------------------------------


class TestPlanCommands:
    def _make_valid_plan(self, tmp_path: Path) -> Path:
        plan = {
            "schema_version": 1,
            "goal": "test goal",
            "roles": [
                {
                    "name": "worker",
                    "goal": "do the work",
                    "contract_ids": [],
                    "scope": ["cli/"],
                    "expected_outputs": ["cli/out.py"],
                    "context": "some context",
                    "constraints": ["no breaking changes"],
                    "verification": "run tests",
                    "assumptions": [],
                    "rollback_triggers": [],
                    "fallback": "skip",
                    "model": "sonnet",
                    "dependencies": [],
                }
            ],
        }
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(plan))
        return plan_file

    def test_plan_finalize_file(self, tmp_path: Path) -> None:
        plan_file = self._make_valid_plan(tmp_path)
        result = run("plan", "finalize-file", str(plan_file))
        assert result.returncode == 0
        assert_ok(result)

    def test_plan_finalize_file_stderr_empty(self, tmp_path: Path) -> None:
        plan_file = self._make_valid_plan(tmp_path)
        result = run("plan", "finalize-file", str(plan_file))
        assert_no_stderr(result)


# ---------------------------------------------------------------------------
# Archive commands
# ---------------------------------------------------------------------------


class TestArchiveCommand:
    def test_archive_empty_root(self, tmp_path: Path) -> None:
        result = run("archive", "--root", str(tmp_path))
        assert result.returncode == 0
        data = assert_ok(result)
        assert data["data"]["archived"] == []

    def test_archive_with_ephemeral_dirs(self, tmp_path: Path) -> None:
        (tmp_path / "plans").mkdir()
        result = run("archive", "--root", str(tmp_path))
        assert result.returncode == 0
        data = assert_ok(result)
        assert "plans" in data["data"]["archived"]

    def test_archive_stderr_empty(self, tmp_path: Path) -> None:
        result = run("archive", "--root", str(tmp_path))
        assert_no_stderr(result)


# ---------------------------------------------------------------------------
# Invalid commands
# ---------------------------------------------------------------------------


class TestInvalidCommands:
    def test_unknown_domain_exits_nonzero(self) -> None:
        result = run("nonexistent-domain")
        assert result.returncode != 0

    def test_unknown_domain_stderr_empty(self) -> None:
        result = run("nonexistent-domain")
        assert_no_stderr(result)

    def test_unknown_domain_error_on_stdout(self) -> None:
        result = run("nonexistent-domain")
        assert result.stdout.strip() != "", "Expected error message on stdout"

    def test_exit_code_2_for_invalid_command(self) -> None:
        result = run("nonexistent-domain")
        assert result.returncode == 2


# ---------------------------------------------------------------------------
# Full workflow
# ---------------------------------------------------------------------------


class TestFullWorkflow:
    def test_register_satisfy_preflight_archive(self, tmp_path: Path) -> None:
        """Register a spec, satisfy it, run preflight, archive, verify persistence."""
        root = tmp_path / ".do"
        root.mkdir()

        # Register a spec.
        reg = run(
            "spec",
            "register",
            "--root",
            str(root),
            "--id",
            "WF-1",
            "--type",
            "execute",
            "--json",
            '{"command":"true"}',
        )
        assert reg.returncode == 0
        assert_ok(reg)

        # Satisfy the spec.
        proof = json.dumps({"output": "done", "exit_code": 0})
        sat = run(
            "spec",
            "satisfy",
            "--root",
            str(root),
            "--id",
            "WF-1",
            "--json",
            proof,
        )
        assert sat.returncode == 0
        assert_ok(sat)

        # Preflight: all satisfied specs re-verified.
        pre = run("spec", "preflight", "--root", str(root))
        assert pre.returncode == 0
        assert_ok(pre)

        # Create an ephemeral plans dir before archive.
        plans_dir = root / "plans"
        plans_dir.mkdir()
        (plans_dir / "plan.json").write_text('{"schema_version":1}')

        # Archive.
        arch = run("archive", "--root", str(root))
        assert arch.returncode == 0
        arch_data = assert_ok(arch)
        assert "plans" in arch_data["data"]["archived"]

        # Persistent files survive: specs.jsonl must still exist.
        assert (root / "specs.jsonl").exists()

        # No ephemeral dirs remain.
        assert not (root / "plans").exists()

    def test_stderr_empty_throughout_workflow(self, tmp_path: Path) -> None:
        root = tmp_path / ".do"
        root.mkdir()

        steps = [
            run("spec", "list", "--root", str(root)),
            run(
                "spec",
                "register",
                "--root",
                str(root),
                "--id",
                "WF-2",
                "--type",
                "execute",
                "--json",
                '{"command":"echo hi"}',
            ),
            run("archive", "--root", str(root)),
        ]
        for step in steps:
            assert_no_stderr(step)
