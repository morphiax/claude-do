"""Tests for the memory store."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from cli.ops.memory import add, boost, search, suppress


# ── helpers ──────────────────────────────────────────────────────────────────

def _base(tmp_path: Path) -> dict[str, Any]:
    return {
        "category": "design",
        "keywords": ["arch", "pattern"],
        "content": "Use layered architecture",
        "source": "meeting",
    }


# ── add ───────────────────────────────────────────────────────────────────────

def test_add_returns_id(tmp_path: Path) -> None:
    result = add(tmp_path, _base(tmp_path))
    assert result["ok"] is True
    assert "id" in result["data"]


def test_add_defaults_importance_to_3(tmp_path: Path) -> None:
    add(tmp_path, _base(tmp_path))
    records = (tmp_path / "memory.jsonl").read_text().strip().splitlines()
    record = json.loads(records[0])
    assert record["importance"] == 3


def test_add_respects_explicit_importance(tmp_path: Path) -> None:
    data = {**_base(tmp_path), "importance": 7}
    add(tmp_path, data)
    records = (tmp_path / "memory.jsonl").read_text().strip().splitlines()
    record = json.loads(records[0])
    assert record["importance"] == 7


def test_add_rejects_importance_below_3(tmp_path: Path) -> None:
    data = {**_base(tmp_path), "importance": 2}
    result = add(tmp_path, data)
    assert result["ok"] is False
    assert "IMPORTANCE" in result["error"]


def test_add_rejects_importance_1(tmp_path: Path) -> None:
    data = {**_base(tmp_path), "importance": 1}
    result = add(tmp_path, data)
    assert result["ok"] is False


def test_add_rejects_non_numeric_importance(tmp_path: Path) -> None:
    data = {**_base(tmp_path), "importance": "high"}
    result = add(tmp_path, data)
    assert result["ok"] is False
    assert "IMPORTANCE" in result["error"]


def test_add_rejects_boolean_importance(tmp_path: Path) -> None:
    data = {**_base(tmp_path), "importance": True}
    result = add(tmp_path, data)
    assert result["ok"] is False


def test_add_missing_required_field(tmp_path: Path) -> None:
    data = {"category": "x", "keywords": [], "content": "c"}
    result = add(tmp_path, data)
    assert result["ok"] is False
    assert "MISSING_FIELD" in result["error"]


def test_add_missing_category(tmp_path: Path) -> None:
    data = {"keywords": ["k"], "content": "c", "source": "s"}
    result = add(tmp_path, data)
    assert result["ok"] is False


def test_add_missing_content(tmp_path: Path) -> None:
    data = {"category": "x", "keywords": ["k"], "source": "s"}
    result = add(tmp_path, data)
    assert result["ok"] is False


# ── search ────────────────────────────────────────────────────────────────────

def test_search_finds_by_content(tmp_path: Path) -> None:
    add(tmp_path, _base(tmp_path))
    result = search(tmp_path, "layered")
    assert result["ok"] is True
    assert len(result["data"]["results"]) == 1


def test_search_finds_by_category(tmp_path: Path) -> None:
    add(tmp_path, _base(tmp_path))
    result = search(tmp_path, "design")
    assert result["ok"] is True
    assert len(result["data"]["results"]) == 1


def test_search_finds_by_keyword_list(tmp_path: Path) -> None:
    add(tmp_path, _base(tmp_path))
    result = search(tmp_path, "arch")
    assert result["ok"] is True
    assert len(result["data"]["results"]) == 1


def test_search_case_insensitive(tmp_path: Path) -> None:
    add(tmp_path, _base(tmp_path))
    result = search(tmp_path, "LAYERED")
    assert result["ok"] is True
    assert len(result["data"]["results"]) == 1


def test_search_no_match(tmp_path: Path) -> None:
    add(tmp_path, _base(tmp_path))
    result = search(tmp_path, "zzznomatch")
    assert result["ok"] is True
    assert result["data"]["results"] == []


def test_search_empty_store(tmp_path: Path) -> None:
    result = search(tmp_path, "anything")
    assert result["ok"] is True
    assert result["data"]["results"] == []


def test_search_deduplicates_by_id(tmp_path: Path) -> None:
    """After boost, only latest version of a record should appear."""
    r = add(tmp_path, _base(tmp_path))
    record_id = r["data"]["id"]
    boost(tmp_path, record_id, 2)
    result = search(tmp_path, "design")
    # Should have exactly 1 result (deduplicated)
    assert len(result["data"]["results"]) == 1
    assert result["data"]["results"][0]["importance"] == 5


# ── boost ─────────────────────────────────────────────────────────────────────

def test_boost_increments_importance(tmp_path: Path) -> None:
    r = add(tmp_path, _base(tmp_path))
    record_id = r["data"]["id"]
    result = boost(tmp_path, record_id, 2)
    assert result["ok"] is True
    assert result["data"]["importance"] == 5


def test_boost_clamps_at_10(tmp_path: Path) -> None:
    data = {**_base(tmp_path), "importance": 9}
    r = add(tmp_path, data)
    record_id = r["data"]["id"]
    result = boost(tmp_path, record_id, 5)
    assert result["ok"] is True
    assert result["data"]["importance"] == 10


def test_boost_not_found(tmp_path: Path) -> None:
    result = boost(tmp_path, "nonexistent-id", 1)
    assert result["ok"] is False
    assert "NOT_FOUND" in result["error"]


def test_boost_already_at_10(tmp_path: Path) -> None:
    data = {**_base(tmp_path), "importance": 10}
    r = add(tmp_path, data)
    record_id = r["data"]["id"]
    result = boost(tmp_path, record_id, 1)
    assert result["ok"] is True
    assert result["data"]["importance"] == 10


# ── suppress ──────────────────────────────────────────────────────────────────

def test_suppress_sets_importance_to_0(tmp_path: Path) -> None:
    r = add(tmp_path, _base(tmp_path))
    record_id = r["data"]["id"]
    result = suppress(tmp_path, record_id)
    assert result["ok"] is True
    assert result["data"]["importance"] == 0


def test_suppress_not_found(tmp_path: Path) -> None:
    result = suppress(tmp_path, "nonexistent-id")
    assert result["ok"] is False
    assert "NOT_FOUND" in result["error"]


def test_suppress_is_reflected_in_search(tmp_path: Path) -> None:
    r = add(tmp_path, _base(tmp_path))
    record_id = r["data"]["id"]
    suppress(tmp_path, record_id)
    results = search(tmp_path, "design")
    assert results["data"]["results"][0]["importance"] == 0
