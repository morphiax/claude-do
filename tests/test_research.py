"""Tests for the research store."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cli.ops.research import add, list_research, search


# ── helpers ───────────────────────────────────────────────────────────────────

def _base() -> dict[str, Any]:
    return {
        "topic": "LLM context window management",
        "findings": "Chunking strategies improve recall by 40%",
    }


# ── add ───────────────────────────────────────────────────────────────────────

def test_add_returns_id(tmp_path: Path) -> None:
    result = add(tmp_path, _base())
    assert result["ok"] is True
    assert "id" in result["data"]


def test_add_creates_json_file(tmp_path: Path) -> None:
    result = add(tmp_path, _base())
    artifact_id = result["data"]["id"]
    expected = tmp_path / "research" / f"{artifact_id}.json"
    assert expected.exists()


def test_add_json_file_contains_record(tmp_path: Path) -> None:
    result = add(tmp_path, _base())
    artifact_id = result["data"]["id"]
    content = json.loads((tmp_path / "research" / f"{artifact_id}.json").read_text())
    assert content["topic"] == _base()["topic"]
    assert content["findings"] == _base()["findings"]


def test_add_missing_topic(tmp_path: Path) -> None:
    data = {"findings": "some findings"}
    result = add(tmp_path, data)
    assert result["ok"] is False
    assert "MISSING_FIELD" in result["error"]


def test_add_missing_findings(tmp_path: Path) -> None:
    data = {"topic": "some topic"}
    result = add(tmp_path, data)
    assert result["ok"] is False
    assert "MISSING_FIELD" in result["error"]


def test_add_extra_fields_preserved(tmp_path: Path) -> None:
    data = {**_base(), "source_url": "https://example.com", "confidence": "high"}
    result = add(tmp_path, data)
    artifact_id = result["data"]["id"]
    content = json.loads((tmp_path / "research" / f"{artifact_id}.json").read_text())
    assert content["source_url"] == "https://example.com"
    assert content["confidence"] == "high"


def test_add_includes_timestamp(tmp_path: Path) -> None:
    result = add(tmp_path, _base())
    artifact_id = result["data"]["id"]
    content = json.loads((tmp_path / "research" / f"{artifact_id}.json").read_text())
    assert "timestamp" in content


def test_add_multiple_artifacts_separate_files(tmp_path: Path) -> None:
    add(tmp_path, _base())
    add(tmp_path, {**_base(), "topic": "second topic"})
    files = list((tmp_path / "research").glob("*.json"))
    assert len(files) == 2


# ── search ────────────────────────────────────────────────────────────────────

def test_search_by_topic(tmp_path: Path) -> None:
    add(tmp_path, _base())
    result = search(tmp_path, "LLM")
    assert result["ok"] is True
    assert len(result["data"]["results"]) == 1


def test_search_by_findings(tmp_path: Path) -> None:
    add(tmp_path, _base())
    result = search(tmp_path, "Chunking")
    assert result["ok"] is True
    assert len(result["data"]["results"]) == 1


def test_search_case_insensitive(tmp_path: Path) -> None:
    add(tmp_path, _base())
    result = search(tmp_path, "llm")
    assert result["ok"] is True
    assert len(result["data"]["results"]) == 1


def test_search_no_match(tmp_path: Path) -> None:
    add(tmp_path, _base())
    result = search(tmp_path, "zzznomatch")
    assert result["ok"] is True
    assert result["data"]["results"] == []


def test_search_empty_store(tmp_path: Path) -> None:
    result = search(tmp_path, "anything")
    assert result["ok"] is True
    assert result["data"]["results"] == []


def test_search_multiple_artifacts(tmp_path: Path) -> None:
    add(tmp_path, _base())
    add(tmp_path, {"topic": "vector databases", "findings": "HNSW outperforms IVF"})
    result = search(tmp_path, "context")
    assert result["ok"] is True
    assert len(result["data"]["results"]) == 1


# ── list_research ─────────────────────────────────────────────────────────────

def test_list_returns_all(tmp_path: Path) -> None:
    add(tmp_path, _base())
    add(tmp_path, {"topic": "t2", "findings": "f2"})
    result = list_research(tmp_path)
    assert result["ok"] is True
    assert len(result["data"]["results"]) == 2


def test_list_empty_store(tmp_path: Path) -> None:
    result = list_research(tmp_path)
    assert result["ok"] is True
    assert result["data"]["results"] == []


def test_list_single_artifact(tmp_path: Path) -> None:
    add(tmp_path, _base())
    result = list_research(tmp_path)
    assert result["ok"] is True
    assert len(result["data"]["results"]) == 1
    assert result["data"]["results"][0]["topic"] == _base()["topic"]
