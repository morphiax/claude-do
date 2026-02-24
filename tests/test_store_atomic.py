"""Tests for cli.store.atomic."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from cli.store.atomic import read, write


class TestWrite:
    def test_writes_correct_content(self, tmp_path: Path) -> None:
        p = tmp_path / "out.json"
        data = {"key": "value", "num": 42}
        write(p, data)
        assert p.exists()
        loaded = json.loads(p.read_text())
        assert loaded == data

    def test_no_temp_files_after_success(self, tmp_path: Path) -> None:
        p = tmp_path / "out.json"
        write(p, {"x": 1})
        files = list(tmp_path.iterdir())
        assert files == [p]

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "out.json"
        write(p, {"v": 1})
        write(p, {"v": 2})
        loaded = json.loads(p.read_text())
        assert loaded == {"v": 2}

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        p = tmp_path / "subdir" / "nested" / "out.json"
        write(p, {"created": True})
        assert p.exists()

    def test_no_temp_files_after_failure(self, tmp_path: Path) -> None:
        p = tmp_path / "out.json"

        # Patch os.replace to simulate a failure after writing
        import os
        real_replace = os.replace

        def failing_replace(src: str, _dst: str) -> None:
            raise OSError("simulated replace failure")

        with patch("cli.store.atomic.os.replace", side_effect=failing_replace):
            with pytest.raises(OSError, match="simulated replace failure"):
                write(p, {"x": 1})

        # No temp files should remain
        remaining = list(tmp_path.iterdir())
        assert remaining == []

class TestRead:
    def test_read_existing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "data.json"
        p.write_text(json.dumps({"hello": "world"}))
        result = read(p)
        assert result == {"hello": "world"}

    def test_read_nonexistent_returns_none(self, tmp_path: Path) -> None:
        p = tmp_path / "missing.json"
        assert read(p) is None


# ---------------------------------------------------------------------------
# IE-25: atomic.write() indented formatting
# ---------------------------------------------------------------------------


class TestIndent:
    def test_output_contains_newlines(self, tmp_path: Path) -> None:
        p = tmp_path / "out.json"
        write(p, {"key": "value"})
        text = p.read_text()
        assert "\n" in text

    def test_output_contains_spaces(self, tmp_path: Path) -> None:
        p = tmp_path / "out.json"
        write(p, {"key": "value"})
        text = p.read_text()
        assert " " in text

    def test_output_is_valid_json(self, tmp_path: Path) -> None:
        p = tmp_path / "out.json"
        data = {"alpha": 1, "beta": [1, 2, 3]}
        write(p, data)
        loaded = json.loads(p.read_text())
        assert loaded == data

    def test_output_uses_indent_2(self, tmp_path: Path) -> None:
        p = tmp_path / "out.json"
        write(p, {"x": 1})
        text = p.read_text()
        # indent=2 produces lines starting with exactly two spaces for top-level keys
        assert "  " in text

    def test_nested_objects_indented(self, tmp_path: Path) -> None:
        p = tmp_path / "out.json"
        write(p, {"outer": {"inner": "val"}})
        text = p.read_text()
        # Nested key must appear on its own indented line
        lines = text.splitlines()
        inner_lines = [l for l in lines if "inner" in l]
        assert inner_lines, "expected 'inner' key on its own line"
        # At least 4 spaces of indentation for a nested key with indent=2
        assert inner_lines[0].startswith("    ")

    def test_not_minified(self, tmp_path: Path) -> None:
        p = tmp_path / "out.json"
        write(p, {"a": 1, "b": 2})
        text = p.read_text()
        # Minified JSON would fit on one line with no newlines
        assert text.count("\n") > 0
