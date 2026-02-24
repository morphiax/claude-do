"""Tests for the archive operation."""

from __future__ import annotations

import json
import re
from pathlib import Path

from typing import Any

from cli.ops.archive import archive

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok(result: dict[str, Any]) -> dict[str, Any]:
    assert result["ok"] is True, f"Expected ok, got: {result}"
    data: dict[str, Any] = result["data"]
    return data


def _err(result: dict[str, Any]) -> dict[str, Any]:
    assert result["ok"] is False, f"Expected error, got: {result}"
    return result


def _make_dir(root: Path, name: str) -> Path:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "file.txt").write_text("content")
    return d


def _make_file(root: Path, name: str, content: str = "data") -> Path:
    p = root / name
    p.write_text(content)
    return p


# ---------------------------------------------------------------------------
# Basic archive with ephemeral dirs
# ---------------------------------------------------------------------------


class TestArchiveWithEphemeralDirs:
    def test_ephemeral_dirs_moved_to_history(self, tmp_path: Path) -> None:
        _make_dir(tmp_path, "plans")
        _make_dir(tmp_path, "workers")
        result = archive(tmp_path)
        data = _ok(result)
        assert set(data["archived"]) == {"plans", "workers"}
        assert not (tmp_path / "plans").exists()
        assert not (tmp_path / "workers").exists()

    def test_all_three_ephemeral_dirs_archived(self, tmp_path: Path) -> None:
        _make_dir(tmp_path, "plans")
        _make_dir(tmp_path, "experts")
        _make_dir(tmp_path, "workers")
        result = archive(tmp_path)
        data = _ok(result)
        assert set(data["archived"]) == {"plans", "experts", "workers"}

    def test_history_dir_contains_archived_artifacts(self, tmp_path: Path) -> None:
        _make_dir(tmp_path, "plans")
        result = archive(tmp_path)
        data = _ok(result)
        history_path = Path(data["history"])
        assert history_path.is_dir()
        assert (history_path / "plans").is_dir()
        assert (history_path / "plans" / "file.txt").exists()

    def test_history_path_under_history_subdir(self, tmp_path: Path) -> None:
        _make_dir(tmp_path, "plans")
        result = archive(tmp_path)
        data = _ok(result)
        history_path = Path(data["history"])
        # Should be root/history/<timestamp>
        assert history_path.parent == tmp_path / "history"

    def test_history_timestamp_format(self, tmp_path: Path) -> None:
        _make_dir(tmp_path, "plans")
        result = archive(tmp_path)
        data = _ok(result)
        history_path = Path(data["history"])
        ts = history_path.name
        # YYYYMMDD_HHMMSS
        assert re.match(r"^\d{8}_\d{6}$", ts), f"Unexpected timestamp format: {ts}"

    def test_persistent_files_survive(self, tmp_path: Path) -> None:
        _make_file(tmp_path, "specs.jsonl")
        _make_file(tmp_path, "memory.jsonl")
        _make_file(tmp_path, "reflections.jsonl")
        _make_file(tmp_path, "traces.jsonl")
        _make_file(tmp_path, "conventions.md")
        _make_file(tmp_path, "aesthetics.md")
        _make_dir(tmp_path, "plans")
        result = archive(tmp_path)
        _ok(result)
        assert (tmp_path / "specs.jsonl").exists()
        assert (tmp_path / "memory.jsonl").exists()
        assert (tmp_path / "reflections.jsonl").exists()
        assert (tmp_path / "traces.jsonl").exists()
        assert (tmp_path / "conventions.md").exists()
        assert (tmp_path / "aesthetics.md").exists()

    def test_persistent_research_dir_survives(self, tmp_path: Path) -> None:
        research = tmp_path / "research"
        research.mkdir()
        (research / "notes.md").write_text("research notes")
        _make_dir(tmp_path, "plans")
        result = archive(tmp_path)
        _ok(result)
        assert (tmp_path / "research").is_dir()
        assert (tmp_path / "research" / "notes.md").exists()


# ---------------------------------------------------------------------------
# No-op when no ephemeral dirs exist
# ---------------------------------------------------------------------------


class TestNoOpArchive:
    def test_no_ephemeral_dirs_returns_success(self, tmp_path: Path) -> None:
        result = archive(tmp_path)
        data = _ok(result)
        assert data["archived"] == []

    def test_no_ephemeral_dirs_message(self, tmp_path: Path) -> None:
        result = archive(tmp_path)
        data = _ok(result)
        assert "nothing to archive" in data["message"]

    def test_only_persistent_files_present_is_noop(self, tmp_path: Path) -> None:
        _make_file(tmp_path, "specs.jsonl")
        _make_file(tmp_path, "memory.jsonl")
        result = archive(tmp_path)
        data = _ok(result)
        assert data["archived"] == []
        assert (tmp_path / "specs.jsonl").exists()
        assert (tmp_path / "memory.jsonl").exists()


# ---------------------------------------------------------------------------
# Post-condition verification
# ---------------------------------------------------------------------------


class TestPostConditions:
    def test_result_ok_implies_postconditions_met(self, tmp_path: Path) -> None:
        _make_dir(tmp_path, "plans")
        _make_file(tmp_path, "specs.jsonl")
        result = archive(tmp_path)
        data = _ok(result)
        # Post-conditions: no ephemeral dirs, persistent files intact, history has artifacts.
        assert not (tmp_path / "plans").exists()
        assert (tmp_path / "specs.jsonl").exists()
        history_path = Path(data["history"])
        assert (history_path / "plans").is_dir()

    def test_partial_ephemeral_dirs_archived_correctly(self, tmp_path: Path) -> None:
        # Only one of the three ephemeral dirs exists.
        _make_dir(tmp_path, "experts")
        result = archive(tmp_path)
        data = _ok(result)
        assert data["archived"] == ["experts"]
        assert not (tmp_path / "experts").exists()

    def test_multiple_archives_create_separate_history_entries(
        self, tmp_path: Path
    ) -> None:
        import time

        _make_dir(tmp_path, "plans")
        result1 = archive(tmp_path)
        data1 = _ok(result1)

        # Re-create plans and archive again (sleep ensures different timestamp).
        time.sleep(1)
        _make_dir(tmp_path, "plans")
        result2 = archive(tmp_path)
        data2 = _ok(result2)

        assert data1["history"] != data2["history"]
        assert Path(data1["history"]).is_dir()
        assert Path(data2["history"]).is_dir()

    def test_workers_dir_content_preserved_in_history(self, tmp_path: Path) -> None:
        workers = tmp_path / "workers"
        workers.mkdir()
        (workers / "task.json").write_text('{"task": 1}')
        (workers / "nested").mkdir()
        (workers / "nested" / "deep.txt").write_text("deep")
        result = archive(tmp_path)
        data = _ok(result)
        history_path = Path(data["history"])
        assert (history_path / "workers" / "task.json").exists()
        assert (history_path / "workers" / "nested" / "deep.txt").exists()


# ---------------------------------------------------------------------------
# XC-43 / XC-44 contract entry-points (referenced by contract verification)
# Full coverage lives in tests/test_archive_contracts.py.
# ---------------------------------------------------------------------------


def _make_plan_file(root: Path, goal: str | None = "My goal") -> None:
    plans_dir = root / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan: dict[str, Any] = {"schema_version": 2, "roles": []}
    if goal is not None:
        plan["goal"] = goal
    (plans_dir / "current.json").write_text(json.dumps(plan))


def _history_entry(root: Path) -> Path:
    history = root / "history"
    entries = sorted(history.iterdir())
    assert len(entries) == 1
    return entries[0]


def test_plan_renamed_on_archive(tmp_path: Path) -> None:
    """XC-43: current.json is renamed to a goal-derived filename on archive."""
    _make_plan_file(tmp_path, goal="My important goal")
    _ok(archive(tmp_path))

    dest = _history_entry(tmp_path) / "plans"
    assert not (dest / "current.json").exists(), "current.json must be renamed"
    plan_files = list(dest.glob("*.json"))
    assert len(plan_files) == 1
    assert plan_files[0].name != "current.json"


def test_archive_summary_created(tmp_path: Path) -> None:
    """XC-44: ARCHIVE.md is created in the history destination directory."""
    _make_plan_file(tmp_path, goal="Summary test goal")
    _ok(archive(tmp_path))

    dest = _history_entry(tmp_path)
    assert (dest / "ARCHIVE.md").exists(), "ARCHIVE.md must be created in history destination"
    content = (dest / "ARCHIVE.md").read_text()
    assert "Summary test goal" in content, "ARCHIVE.md must contain the plan goal"
