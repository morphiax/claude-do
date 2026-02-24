"""Contract tests for archive discoverability (XC-43, XC-44).

These tests assert behavioral contracts only — no implementation code from
cli/ops/archive.py is consulted during authorship.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from typing import Any

from cli.ops.archive import archive


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok(result: dict[str, Any]) -> dict[str, Any]:
    assert result["ok"] is True, f"Expected ok, got: {result}"
    data: dict[str, Any] = result["data"]
    return data


def _make_plan(root: Path, goal: str | None = "My goal", roles: list[dict[str, Any]] | None = None) -> Path:
    """Write a minimal valid plan to .do/plans/current.json."""
    plans_dir = root / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan: dict[str, Any] = {"schema_version": 2, "roles": roles or []}
    if goal is not None:
        plan["goal"] = goal
    plan_file = plans_dir / "current.json"
    plan_file.write_text(json.dumps(plan))
    return plan_file


def _make_persistent(root: Path) -> None:
    """Create the persistent files archive must not touch."""
    (root / "spec.md").write_text("# spec")
    (root / "spec.jsonl").write_text("")


def _history_dir(root: Path) -> Path:
    """Return the single history entry directory created after one archive call."""
    history = root / "history"
    entries = sorted(history.iterdir()) if history.exists() else []
    assert len(entries) == 1, f"Expected exactly one history entry, got: {entries}"
    return entries[0]


# ---------------------------------------------------------------------------
# XC-43: Plan is renamed on archive based on goal
# ---------------------------------------------------------------------------


class TestPlanRenamedOnArchive:
    """XC-43 — current.json is renamed to <sanitized-goal>.json in the archive."""

    def test_plan_renamed_on_archive(self, tmp_path: Path) -> None:
        """Core contract: current.json becomes a goal-derived filename."""
        root = tmp_path
        _make_persistent(root)
        _make_plan(root, goal="My important goal")
        _ok(archive(root))

        dest = _history_dir(root) / "plans"
        assert not (dest / "current.json").exists(), "current.json must be renamed"
        plan_files = list(dest.glob("*.json"))
        assert len(plan_files) == 1, f"Expected exactly one plan file, got: {plan_files}"
        assert plan_files[0].name != "current.json"

    def test_sanitized_name_is_lowercase(self, tmp_path: Path) -> None:
        root = tmp_path
        _make_persistent(root)
        _make_plan(root, goal="My Important Goal")
        _ok(archive(root))

        dest = _history_dir(root) / "plans"
        plan_files = list(dest.glob("*.json"))
        assert len(plan_files) == 1
        assert plan_files[0].stem == plan_files[0].stem.lower(), "Filename must be lowercase"

    def test_spaces_replaced_with_hyphens(self, tmp_path: Path) -> None:
        root = tmp_path
        _make_persistent(root)
        _make_plan(root, goal="build a thing")
        _ok(archive(root))

        dest = _history_dir(root) / "plans"
        plan_files = list(dest.glob("*.json"))
        assert len(plan_files) == 1
        assert " " not in plan_files[0].stem, "Spaces must not appear in the filename"
        assert "-" in plan_files[0].stem, "Spaces should be replaced with hyphens"

    def test_punctuation_replaced_with_hyphens(self, tmp_path: Path) -> None:
        root = tmp_path
        _make_persistent(root)
        _make_plan(root, goal="build: a.thing, now!")
        _ok(archive(root))

        dest = _history_dir(root) / "plans"
        plan_files = list(dest.glob("*.json"))
        assert len(plan_files) == 1
        stem = plan_files[0].stem
        # Only hyphens and alphanumeric characters should appear
        assert all(c.isalnum() or c == "-" for c in stem), (
            f"Unexpected characters in filename stem: {stem!r}"
        )

    def test_goal_truncated_to_approximately_60_chars(self, tmp_path: Path) -> None:
        root = tmp_path
        _make_persistent(root)
        long_goal = "a" * 120
        _make_plan(root, goal=long_goal)
        _ok(archive(root))

        dest = _history_dir(root) / "plans"
        plan_files = list(dest.glob("*.json"))
        assert len(plan_files) == 1
        # Allow some slack around the 60-char target (e.g., up to 70).
        assert len(plan_files[0].stem) <= 70, (
            f"Filename stem should be truncated near 60 chars, got {len(plan_files[0].stem)}"
        )

    def test_missing_goal_falls_back_to_unnamed_plan(self, tmp_path: Path) -> None:
        root = tmp_path
        _make_persistent(root)
        _make_plan(root, goal=None)  # no "goal" key in plan
        _ok(archive(root))

        dest = _history_dir(root) / "plans"
        plan_files = list(dest.glob("*.json"))
        assert len(plan_files) == 1
        assert plan_files[0].name == "unnamed-plan.json", (
            f"Expected unnamed-plan.json, got {plan_files[0].name}"
        )

    def test_empty_goal_falls_back_to_unnamed_plan(self, tmp_path: Path) -> None:
        root = tmp_path
        _make_persistent(root)
        _make_plan(root, goal="")
        _ok(archive(root))

        dest = _history_dir(root) / "plans"
        plan_files = list(dest.glob("*.json"))
        assert len(plan_files) == 1
        assert plan_files[0].name == "unnamed-plan.json", (
            f"Expected unnamed-plan.json, got {plan_files[0].name}"
        )

    def test_filesystem_unsafe_slashes_removed(self, tmp_path: Path) -> None:
        root = tmp_path
        _make_persistent(root)
        _make_plan(root, goal="build/destroy")
        _ok(archive(root))

        dest = _history_dir(root) / "plans"
        plan_files = list(dest.glob("*.json"))
        assert len(plan_files) == 1
        assert "/" not in plan_files[0].stem, "Slashes must be removed from filename"

    def test_filesystem_unsafe_colons_removed(self, tmp_path: Path) -> None:
        root = tmp_path
        _make_persistent(root)
        _make_plan(root, goal="step:one")
        _ok(archive(root))

        dest = _history_dir(root) / "plans"
        plan_files = list(dest.glob("*.json"))
        assert len(plan_files) == 1
        assert ":" not in plan_files[0].stem, "Colons must be removed from filename"

    def test_filesystem_unsafe_nulls_removed(self, tmp_path: Path) -> None:
        root = tmp_path
        _make_persistent(root)
        _make_plan(root, goal="goal\x00here")
        _ok(archive(root))

        dest = _history_dir(root) / "plans"
        plan_files = list(dest.glob("*.json"))
        assert len(plan_files) == 1
        assert "\x00" not in plan_files[0].stem, "Null bytes must be removed from filename"

    def test_whitespace_only_goal_falls_back_to_unnamed_plan(self, tmp_path: Path) -> None:
        root = tmp_path
        _make_persistent(root)
        _make_plan(root, goal="   ")
        _ok(archive(root))

        dest = _history_dir(root) / "plans"
        plan_files = list(dest.glob("*.json"))
        assert len(plan_files) == 1
        assert plan_files[0].name == "unnamed-plan.json", (
            f"Expected unnamed-plan.json for whitespace-only goal, got {plan_files[0].name}"
        )


# ---------------------------------------------------------------------------
# XC-44: Archive summary file is generated
# ---------------------------------------------------------------------------


class TestArchiveSummaryCreated:
    """XC-44 — ARCHIVE.md is written to the history destination directory."""

    def test_archive_summary_created(self, tmp_path: Path) -> None:
        """Core contract: ARCHIVE.md exists in the archive destination."""
        root = tmp_path
        _make_persistent(root)
        _make_plan(root, goal="Test goal")
        _ok(archive(root))

        dest = _history_dir(root)
        assert (dest / "ARCHIVE.md").exists(), "ARCHIVE.md must be created in history destination"

    def test_summary_contains_timestamp(self, tmp_path: Path) -> None:
        root = tmp_path
        _make_persistent(root)
        _make_plan(root, goal="Test goal")
        _ok(archive(root))

        dest = _history_dir(root)
        content = (dest / "ARCHIVE.md").read_text()
        # The timestamp should appear in the summary; the history dir name is the timestamp.
        ts = dest.name
        assert ts in content, f"ARCHIVE.md must contain the archive timestamp ({ts})"

    def test_summary_contains_plan_goal(self, tmp_path: Path) -> None:
        root = tmp_path
        _make_persistent(root)
        _make_plan(root, goal="Deploy the widget service")
        _ok(archive(root))

        dest = _history_dir(root)
        content = (dest / "ARCHIVE.md").read_text()
        assert "Deploy the widget service" in content, (
            "ARCHIVE.md must contain the plan goal"
        )

    def test_summary_contains_role_names(self, tmp_path: Path) -> None:
        root = tmp_path
        _make_persistent(root)
        roles = [
            {"name": "researcher", "status": "complete"},
            {"name": "implementer", "status": "complete"},
        ]
        _make_plan(root, goal="Some goal", roles=roles)
        _ok(archive(root))

        dest = _history_dir(root)
        content = (dest / "ARCHIVE.md").read_text()
        assert "researcher" in content, "ARCHIVE.md must list role names"
        assert "implementer" in content, "ARCHIVE.md must list role names"

    def test_summary_contains_role_terminal_statuses(self, tmp_path: Path) -> None:
        root = tmp_path
        _make_persistent(root)
        roles = [
            {"name": "analyst", "status": "complete"},
            {"name": "reviewer", "status": "failed"},
        ]
        _make_plan(root, goal="Some goal", roles=roles)
        _ok(archive(root))

        dest = _history_dir(root)
        content = (dest / "ARCHIVE.md").read_text()
        assert "complete" in content, "ARCHIVE.md must include terminal role statuses"
        assert "failed" in content, "ARCHIVE.md must include terminal role statuses"

    def test_summary_contains_contract_ids(self, tmp_path: Path) -> None:
        root = tmp_path
        _make_persistent(root)
        roles = [
            {"name": "worker", "status": "complete", "contract_ids": ["XC-10", "XC-11"]},
        ]
        _make_plan(root, goal="Some goal", roles=roles)
        _ok(archive(root))

        dest = _history_dir(root)
        content = (dest / "ARCHIVE.md").read_text()
        assert "XC-10" in content, "ARCHIVE.md must include contract IDs"
        assert "XC-11" in content, "ARCHIVE.md must include contract IDs"

    def test_summary_contains_file_inventory(self, tmp_path: Path) -> None:
        root = tmp_path
        _make_persistent(root)
        _make_plan(root, goal="Some goal")
        # Add an extra file in the workers dir to include in inventory.
        workers_dir = root / "workers"
        workers_dir.mkdir()
        (workers_dir / "output.json").write_text('{"result": "done"}')
        _ok(archive(root))

        dest = _history_dir(root)
        content = (dest / "ARCHIVE.md").read_text()
        # The inventory should reference at least one archived file/directory.
        assert any(
            keyword in content
            for keyword in ("plans", "workers", "output.json", "current.json")
        ), "ARCHIVE.md must contain a file inventory referencing archived artifacts"

    def test_summary_is_markdown(self, tmp_path: Path) -> None:
        root = tmp_path
        _make_persistent(root)
        _make_plan(root, goal="Check markdown format")
        _ok(archive(root))

        dest = _history_dir(root)
        content = (dest / "ARCHIVE.md").read_text()
        # Markdown files should contain at least one heading marker.
        assert "#" in content, "ARCHIVE.md should contain markdown headings"
