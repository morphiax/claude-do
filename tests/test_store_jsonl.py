"""Tests for cli.store.jsonl."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli.store.jsonl import append, read


class TestRead:
    def test_nonexistent_file_returns_empty(self, tmp_path: Path) -> None:
        result = read(tmp_path / "no_such_file.jsonl")
        assert result == []

    def test_empty_file_returns_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.jsonl"
        p.write_text("")
        assert read(p) == []

    def test_reads_valid_records(self, tmp_path: Path) -> None:
        p = tmp_path / "data.jsonl"
        records = [{"id": "1", "value": "a"}, {"id": "2", "value": "b"}]
        p.write_text("\n".join(json.dumps(r) for r in records) + "\n")
        result = read(p)
        assert result == records

    def test_skips_corrupt_middle_line(self, tmp_path: Path) -> None:
        p = tmp_path / "data.jsonl"
        p.write_text(
            json.dumps({"id": "1"}) + "\n"
            + "this is not json\n"
            + json.dumps({"id": "2"}) + "\n"
        )
        result = read(p)
        assert len(result) == 2
        assert result[0]["id"] == "1"
        assert result[1]["id"] == "2"

    def test_skips_corrupt_first_line(self, tmp_path: Path) -> None:
        p = tmp_path / "data.jsonl"
        p.write_text(
            "CORRUPT LINE\n"
            + json.dumps({"id": "1"}) + "\n"
            + json.dumps({"id": "2"}) + "\n"
        )
        result = read(p)
        assert len(result) == 2
        assert result[0]["id"] == "1"

    def test_skips_corrupt_last_line(self, tmp_path: Path) -> None:
        p = tmp_path / "data.jsonl"
        p.write_text(
            json.dumps({"id": "1"}) + "\n"
            + json.dumps({"id": "2"}) + "\n"
            + "{{bad json}}\n"
        )
        result = read(p)
        assert len(result) == 2
        assert result[-1]["id"] == "2"

    def test_skips_blank_lines(self, tmp_path: Path) -> None:
        p = tmp_path / "data.jsonl"
        p.write_text(
            json.dumps({"id": "1"}) + "\n"
            + "\n"
            + json.dumps({"id": "2"}) + "\n"
        )
        result = read(p)
        assert len(result) == 2

    def test_all_corrupt_returns_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "data.jsonl"
        p.write_text("bad\nworse\n{broken\n")
        assert read(p) == []


class TestAppend:
    def test_creates_file_if_missing(self, tmp_path: Path) -> None:
        p = tmp_path / "new.jsonl"
        assert not p.exists()
        append(p, {"key": "value"})
        assert p.exists()

    def test_appended_record_is_readable(self, tmp_path: Path) -> None:
        p = tmp_path / "data.jsonl"
        record = {"id": "abc", "name": "test"}
        append(p, record)
        result = read(p)
        assert result == [record]

    def test_multiple_appends_preserve_order(self, tmp_path: Path) -> None:
        p = tmp_path / "data.jsonl"
        records = [{"seq": i} for i in range(5)]
        for r in records:
            append(p, r)
        result = read(p)
        assert result == records

    def test_append_uses_compact_json(self, tmp_path: Path) -> None:
        p = tmp_path / "data.jsonl"
        append(p, {"a": 1, "b": 2})
        line = p.read_text().strip()
        # Compact: no spaces around separators
        assert " " not in line

    def test_each_record_on_own_line(self, tmp_path: Path) -> None:
        p = tmp_path / "data.jsonl"
        append(p, {"n": 1})
        append(p, {"n": 2})
        lines = [l for l in p.read_text().splitlines() if l.strip()]
        assert len(lines) == 2
