"""Tests for spec-integrity behavioral contracts.

Covers SL-14: divergence() regex must match letter-suffix contract IDs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cli.ops import spec as ops


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok(result: dict[str, Any]) -> Any:
    assert result["ok"] is True, f"Expected ok, got: {result}"
    return result["data"]


def _register(root: Path, contract_id: str) -> None:
    """Register a contract in the spec registry."""
    ops.register(
        root,
        contract_id,
        "review",
        {"question": f"Is {contract_id} satisfied?", "artifact": f"{contract_id}.txt"},
    )


def _write_doc(tmp_path: Path, content: str) -> Path:
    """Write a spec document and return its path."""
    doc = tmp_path / "spec.md"
    doc.write_text(content)
    return doc


# ---------------------------------------------------------------------------
# SL-14: Divergence regex matches letter-suffix contract IDs
# ---------------------------------------------------------------------------


class TestDivergenceLetterSuffixIds:
    """SL-14: The divergence regex must match [XX-Na] style IDs."""

    def test_letter_suffix_in_both_is_not_orphaned(self, root: Path, tmp_path: Path) -> None:
        """EC-4a in both spec.md and registry must not appear in orphaned."""
        _register(root, "EC-4a")
        doc = _write_doc(tmp_path, "This contract [EC-4a] defines the execution boundary.")

        data = _ok(ops.divergence(root, doc))

        assert "EC-4a" not in data["orphaned"]
        assert "EC-4a" not in data["unregistered"]

    def test_letter_suffix_in_spec_only_is_unregistered(self, root: Path, tmp_path: Path) -> None:
        """EC-4b found in spec but absent from registry lands in unregistered."""
        doc = _write_doc(tmp_path, "See [EC-4b] for retry behaviour.")

        data = _ok(ops.divergence(root, doc))

        assert "EC-4b" in data["unregistered"]

    def test_letter_suffix_only_in_registry_is_orphaned(self, root: Path, tmp_path: Path) -> None:
        """EC-4c registered but absent from spec.md lands in orphaned."""
        _register(root, "EC-4c")
        doc = _write_doc(tmp_path, "No mention of EC-4c here.")

        data = _ok(ops.divergence(root, doc))

        assert "EC-4c" in data["orphaned"]

    def test_multiple_letter_suffix_ids_none_orphaned(self, root: Path, tmp_path: Path) -> None:
        """EC-4a, EC-4b, EC-4c all in both spec and registry — none orphaned."""
        for cid in ("EC-4a", "EC-4b", "EC-4c"):
            _register(root, cid)
        doc = _write_doc(tmp_path, "Contracts [EC-4a], [EC-4b], and [EC-4c] govern execution.")

        data = _ok(ops.divergence(root, doc))

        assert data["unregistered"] == []
        assert data["orphaned"] == []

    def test_standard_ids_still_work(self, root: Path, tmp_path: Path) -> None:
        """Standard IDs [DC-1] and [SL-14] match alongside letter-suffix IDs."""
        for cid in ("DC-1", "SL-14", "EC-4a"):
            _register(root, cid)
        doc = _write_doc(tmp_path, "Standard [DC-1] and [SL-14] alongside [EC-4a].")

        data = _ok(ops.divergence(root, doc))

        assert data["unregistered"] == []
        assert data["orphaned"] == []

    def test_mix_with_orphans_and_unregistered(self, root: Path, tmp_path: Path) -> None:
        """Mix: some matched, some spec-only, some registry-only."""
        for cid in ("DC-1", "EC-4a", "EC-4b"):
            _register(root, cid)
        doc = _write_doc(tmp_path, "See [DC-1] and [EC-4a] for details. Also mentions [SL-99].")

        data = _ok(ops.divergence(root, doc))

        assert "SL-99" in data["unregistered"]
        assert "EC-4b" in data["orphaned"]
        assert "DC-1" not in data["orphaned"]
        assert "EC-4a" not in data["orphaned"]

    def test_letter_suffix_distinct_from_bare_number(self, root: Path, tmp_path: Path) -> None:
        """EC-4 and EC-4a are distinct; registering EC-4 does not match [EC-4a]."""
        _register(root, "EC-4")
        doc = _write_doc(tmp_path, "Contract [EC-4a] applies here.")

        data = _ok(ops.divergence(root, doc))

        assert "EC-4a" in data["unregistered"]
        assert "EC-4" in data["orphaned"]

    def test_multi_letter_suffix(self, root: Path, tmp_path: Path) -> None:
        """IDs with two trailing letters (EC-4ab) are extracted and matched."""
        _register(root, "EC-4ab")
        doc = _write_doc(tmp_path, "Extended contract [EC-4ab] covers edge cases.")

        data = _ok(ops.divergence(root, doc))

        assert data["unregistered"] == []
        assert data["orphaned"] == []
