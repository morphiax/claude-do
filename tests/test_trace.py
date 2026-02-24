"""Tests for the trace store."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from cli.ops.trace import add


# ── add ───────────────────────────────────────────────────────────────────────

def test_add_returns_id(tmp_path: Path) -> None:
    result = add(tmp_path, {"event": "design_start"})
    assert result["ok"] is True
    assert "id" in result["data"]


def test_add_persists_to_jsonl(tmp_path: Path) -> None:
    add(tmp_path, {"event": "design_start"})
    lines = (tmp_path / "traces.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["event"] == "design_start"


def test_add_missing_event(tmp_path: Path) -> None:
    result = add(tmp_path, {"other": "field"})
    assert result["ok"] is False
    assert "MISSING_FIELD" in result["error"]


def test_add_includes_timestamp(tmp_path: Path) -> None:
    add(tmp_path, {"event": "x"})
    record = json.loads((tmp_path / "traces.jsonl").read_text().strip())
    assert "timestamp" in record


def test_add_includes_id(tmp_path: Path) -> None:
    add(tmp_path, {"event": "x"})
    record = json.loads((tmp_path / "traces.jsonl").read_text().strip())
    assert "id" in record


def test_add_extra_fields_preserved(tmp_path: Path) -> None:
    add(tmp_path, {"event": "task_complete", "task_id": "abc-123", "duration_ms": 42})
    record = json.loads((tmp_path / "traces.jsonl").read_text().strip())
    assert record["task_id"] == "abc-123"
    assert record["duration_ms"] == 42


def test_add_multiple_events_appended(tmp_path: Path) -> None:
    add(tmp_path, {"event": "start"})
    add(tmp_path, {"event": "end"})
    lines = (tmp_path / "traces.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2


def test_add_write_failure_does_not_crash(tmp_path: Path) -> None:
    """Write failures must not raise — warning included in envelope."""
    import cli.store.jsonl as jsonl_mod
    with patch.object(jsonl_mod, "append", side_effect=OSError("disk full")):
        result = add(tmp_path, {"event": "smoke"})
    assert result["ok"] is True
    assert "warning" in result["data"]


def test_add_write_failure_includes_warning(tmp_path: Path) -> None:
    import cli.store.jsonl as jsonl_mod
    with patch.object(jsonl_mod, "append", side_effect=OSError("disk full")):
        result = add(tmp_path, {"event": "smoke"})
    assert "disk full" in result["data"]["warning"]


def test_add_immutable_consecutive_ids_differ(tmp_path: Path) -> None:
    r1 = add(tmp_path, {"event": "a"})
    r2 = add(tmp_path, {"event": "b"})
    assert r1["data"]["id"] != r2["data"]["id"]
