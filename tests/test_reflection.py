"""Tests for the reflection store."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cli.ops.reflection import add, list_reflections, resolve


# ── helpers ───────────────────────────────────────────────────────────────────

def _base() -> dict[str, Any]:
    return {
        "type": "retrospective",
        "outcome": "positive",
        "lens": "process",
        "urgency": "deferred",
    }


# ── add ───────────────────────────────────────────────────────────────────────

def test_add_returns_id(tmp_path: Path) -> None:
    result = add(tmp_path, _base())
    assert result["ok"] is True
    assert "id" in result["data"]


def test_add_missing_type(tmp_path: Path) -> None:
    data = {k: v for k, v in _base().items() if k != "type"}
    result = add(tmp_path, data)
    assert result["ok"] is False
    assert "MISSING_FIELD" in result["error"]


def test_add_missing_outcome(tmp_path: Path) -> None:
    data = {k: v for k, v in _base().items() if k != "outcome"}
    result = add(tmp_path, data)
    assert result["ok"] is False


def test_add_missing_lens(tmp_path: Path) -> None:
    data = {k: v for k, v in _base().items() if k != "lens"}
    result = add(tmp_path, data)
    assert result["ok"] is False


def test_add_missing_urgency(tmp_path: Path) -> None:
    data = {k: v for k, v in _base().items() if k != "urgency"}
    result = add(tmp_path, data)
    assert result["ok"] is False


def test_add_invalid_lens(tmp_path: Path) -> None:
    data = {**_base(), "lens": "technical"}
    result = add(tmp_path, data)
    assert result["ok"] is False
    assert "LENS" in result["error"]


def test_add_invalid_urgency(tmp_path: Path) -> None:
    data = {**_base(), "urgency": "sometime"}
    result = add(tmp_path, data)
    assert result["ok"] is False
    assert "URGENCY" in result["error"]


def test_add_product_lens(tmp_path: Path) -> None:
    data = {**_base(), "lens": "product"}
    result = add(tmp_path, data)
    assert result["ok"] is True


def test_add_immediate_urgency(tmp_path: Path) -> None:
    data = {**_base(), "urgency": "immediate"}
    result = add(tmp_path, data)
    assert result["ok"] is True


def test_add_failures_without_fix_proposals_rejected(tmp_path: Path) -> None:
    data = {**_base(), "failures": ["build broke"], "fix_proposals": []}
    result = add(tmp_path, data)
    assert result["ok"] is False
    assert "FIX_PROPOSALS" in result["error"]


def test_add_failures_with_fix_proposals_accepted(tmp_path: Path) -> None:
    data = {
        **_base(),
        "failures": ["build broke"],
        "fix_proposals": ["add pre-commit hook"],
    }
    result = add(tmp_path, data)
    assert result["ok"] is True


def test_add_empty_failures_no_fix_proposals_accepted(tmp_path: Path) -> None:
    data = {**_base(), "failures": [], "fix_proposals": []}
    result = add(tmp_path, data)
    assert result["ok"] is True


def test_add_no_failures_no_fix_proposals_accepted(tmp_path: Path) -> None:
    result = add(tmp_path, _base())
    assert result["ok"] is True


# ── list_reflections ───────────────────────────────────────────────────────────

def test_list_all(tmp_path: Path) -> None:
    add(tmp_path, _base())
    add(tmp_path, {**_base(), "lens": "product"})
    result = list_reflections(tmp_path)
    assert result["ok"] is True
    assert len(result["data"]["results"]) == 2


def test_list_filter_by_lens(tmp_path: Path) -> None:
    add(tmp_path, _base())
    add(tmp_path, {**_base(), "lens": "product"})
    result = list_reflections(tmp_path, lens="product")
    assert result["ok"] is True
    assert len(result["data"]["results"]) == 1
    assert result["data"]["results"][0]["lens"] == "product"


def test_list_filter_by_urgency(tmp_path: Path) -> None:
    add(tmp_path, _base())
    add(tmp_path, {**_base(), "urgency": "immediate"})
    result = list_reflections(tmp_path, urgency="immediate")
    assert result["ok"] is True
    assert len(result["data"]["results"]) == 1
    assert result["data"]["results"][0]["urgency"] == "immediate"


def test_list_filter_by_lens_and_urgency(tmp_path: Path) -> None:
    add(tmp_path, _base())
    add(tmp_path, {**_base(), "lens": "product", "urgency": "immediate"})
    add(tmp_path, {**_base(), "lens": "product", "urgency": "deferred"})
    result = list_reflections(tmp_path, lens="product", urgency="immediate")
    assert result["ok"] is True
    assert len(result["data"]["results"]) == 1


def test_list_empty_store(tmp_path: Path) -> None:
    result = list_reflections(tmp_path)
    assert result["ok"] is True
    assert result["data"]["results"] == []


def test_list_no_match(tmp_path: Path) -> None:
    add(tmp_path, _base())  # lens=process, urgency=deferred
    result = list_reflections(tmp_path, lens="product")
    assert result["ok"] is True
    assert result["data"]["results"] == []


def _resolve(root: Path, finding_id: str, resolution_text: str) -> dict[str, Any]:
    return resolve(root, finding_id, resolution_text)


# ── TestResolve ────────────────────────────────────────────────────────────────

class TestResolve:
    def _root(self, tmp_path: Path) -> Path:
        root = tmp_path / ".do"
        root.mkdir()
        return root

    def _add_finding(self, root: Path) -> str:
        result = add(root, _base())
        assert result["ok"] is True
        finding_id: str = result["data"]["id"]
        return finding_id

    def test_resolve_returns_ok_envelope(self, tmp_path: Path) -> None:
        root = self._root(tmp_path)
        finding_id = self._add_finding(root)
        result = _resolve(root, finding_id, "addressed in next sprint")
        assert result["ok"] is True
        assert "data" in result

    def test_resolve_data_contains_finding_id(self, tmp_path: Path) -> None:
        root = self._root(tmp_path)
        finding_id = self._add_finding(root)
        result = _resolve(root, finding_id, "addressed in next sprint")
        assert result["data"]["finding_id"] == finding_id

    def test_resolve_data_contains_resolution_text(self, tmp_path: Path) -> None:
        root = self._root(tmp_path)
        finding_id = self._add_finding(root)
        resolution_text = "fixed by deploying hotfix v1.2"
        result = _resolve(root, finding_id, resolution_text)
        assert result["data"]["resolution"] == resolution_text

    def test_resolve_data_contains_timestamp(self, tmp_path: Path) -> None:
        root = self._root(tmp_path)
        finding_id = self._add_finding(root)
        result = _resolve(root, finding_id, "handled")
        assert "timestamp" in result["data"]

    def test_resolve_appends_resolution_record_to_jsonl(self, tmp_path: Path) -> None:
        import json

        root = self._root(tmp_path)
        finding_id = self._add_finding(root)
        _resolve(root, finding_id, "done")
        jsonl_path = root / "reflections.jsonl"
        records = [json.loads(line) for line in jsonl_path.read_text().splitlines()]
        resolution_records = [r for r in records if r.get("type") == "resolution"]
        assert len(resolution_records) == 1

    def test_resolve_record_references_finding_id(self, tmp_path: Path) -> None:
        import json

        root = self._root(tmp_path)
        finding_id = self._add_finding(root)
        _resolve(root, finding_id, "resolved")
        jsonl_path = root / "reflections.jsonl"
        records = [json.loads(line) for line in jsonl_path.read_text().splitlines()]
        resolution_records = [r for r in records if r.get("type") == "resolution"]
        assert resolution_records[0]["finding_id"] == finding_id

    def test_resolve_unknown_finding_id_returns_error(self, tmp_path: Path) -> None:
        root = self._root(tmp_path)
        result = _resolve(root, "nonexistent-id-xyz", "some resolution")
        assert result["ok"] is False
        assert result["error"] == "REFLECTION_NOT_FOUND"

    def test_resolve_unknown_finding_id_has_message(self, tmp_path: Path) -> None:
        root = self._root(tmp_path)
        result = _resolve(root, "nonexistent-id-xyz", "some resolution")
        assert "message" in result

    def test_resolve_does_not_write_on_missing_finding(self, tmp_path: Path) -> None:
        import json

        root = self._root(tmp_path)
        self._add_finding(root)
        _resolve(root, "nonexistent-id-xyz", "some resolution")
        jsonl_path = root / "reflections.jsonl"
        records = [json.loads(line) for line in jsonl_path.read_text().splitlines()]
        resolution_records = [r for r in records if r.get("type") == "resolution"]
        assert len(resolution_records) == 0


# ── TestListFiltering ──────────────────────────────────────────────────────────

class TestListFiltering:
    def _root(self, tmp_path: Path) -> Path:
        root = tmp_path / ".do"
        root.mkdir()
        return root

    def _add_finding(self, root: Path) -> str:
        result = add(root, _base())
        assert result["ok"] is True
        finding_id: str = result["data"]["id"]
        return finding_id

    def test_list_excludes_resolved_findings_by_default(self, tmp_path: Path) -> None:
        root = self._root(tmp_path)
        finding_id = self._add_finding(root)
        _resolve(root, finding_id, "closed")
        result = list_reflections(root)
        assert result["ok"] is True
        ids = [r["id"] for r in result["data"]["results"]]
        assert finding_id not in ids

    def test_list_excludes_only_resolved_findings(self, tmp_path: Path) -> None:
        root = self._root(tmp_path)
        resolved_id = self._add_finding(root)
        open_id = self._add_finding(root)
        _resolve(root, resolved_id, "closed")
        result = list_reflections(root)
        assert result["ok"] is True
        ids = [r["id"] for r in result["data"]["results"]]
        assert resolved_id not in ids
        assert open_id in ids

    def test_list_include_resolved_shows_all_findings(self, tmp_path: Path) -> None:
        root = self._root(tmp_path)
        finding_id = self._add_finding(root)
        _resolve(root, finding_id, "closed")
        result = list_reflections(root, include_resolved=True)
        assert result["ok"] is True
        ids = [r["id"] for r in result["data"]["results"]]
        assert finding_id in ids

    def test_list_include_resolved_false_excludes_resolved(self, tmp_path: Path) -> None:
        root = self._root(tmp_path)
        finding_id = self._add_finding(root)
        _resolve(root, finding_id, "closed")
        result = list_reflections(root, include_resolved=False)
        assert result["ok"] is True
        ids = [r["id"] for r in result["data"]["results"]]
        assert finding_id not in ids

    def test_list_include_resolved_shows_mixed(self, tmp_path: Path) -> None:
        root = self._root(tmp_path)
        resolved_id = self._add_finding(root)
        open_id = self._add_finding(root)
        _resolve(root, resolved_id, "closed")
        result = list_reflections(root, include_resolved=True)
        assert result["ok"] is True
        ids = [r["id"] for r in result["data"]["results"]]
        assert resolved_id in ids
        assert open_id in ids

    def test_list_no_resolved_findings_behaves_normally(self, tmp_path: Path) -> None:
        root = self._root(tmp_path)
        finding_id = self._add_finding(root)
        result = list_reflections(root)
        assert result["ok"] is True
        ids = [r["id"] for r in result["data"]["results"]]
        assert finding_id in ids

    def test_list_all_resolved_returns_empty_by_default(self, tmp_path: Path) -> None:
        root = self._root(tmp_path)
        finding_id = self._add_finding(root)
        _resolve(root, finding_id, "closed")
        result = list_reflections(root)
        assert result["ok"] is True
        assert result["data"]["results"] == []

    def test_list_all_resolved_returns_all_with_include_resolved(self, tmp_path: Path) -> None:
        root = self._root(tmp_path)
        finding_id = self._add_finding(root)
        _resolve(root, finding_id, "closed")
        result = list_reflections(root, include_resolved=True)
        assert result["ok"] is True
        assert len(result["data"]["results"]) == 1
