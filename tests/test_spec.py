"""Tests for the behavioral spec registry."""

from __future__ import annotations

import json
from pathlib import Path

from typing import Any

from cli.ops import spec as ops
from cli.store import hash as store_hash

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok(result: dict[str, Any]) -> Any:
    assert result["ok"] is True, f"Expected ok, got: {result}"
    return result["data"]


def _err(result: dict[str, Any]) -> dict[str, Any]:
    assert result["ok"] is False, f"Expected error, got: {result}"
    return result


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------


class TestRegister:
    def test_register_execute_type(self, root: Path) -> None:
        result = ops.register(root, "SL-1", "execute", {"command": "true"})
        data = _ok(result)
        assert data["id"] == "SL-1"
        assert data["status"] == "pending"
        assert "content_hash" in data

    def test_register_review_type(self, root: Path) -> None:
        result = ops.register(
            root,
            "SL-2",
            "review",
            {"question": "Is output correct?", "artifact": "output.txt"},
        )
        data = _ok(result)
        assert data["id"] == "SL-2"

    def test_register_computes_correct_hash(self, root: Path) -> None:
        content = {"command": "echo hello"}
        result = ops.register(root, "SL-3", "execute", content)
        data = _ok(result)
        assert data["content_hash"] == store_hash.content_hash(content)

    def test_register_duplicate_rejected(self, root: Path) -> None:
        ops.register(root, "SL-1", "execute", {"command": "true"})
        result = ops.register(root, "SL-1", "execute", {"command": "false"})
        err = _err(result)
        assert err["error"] == "SPEC_DUPLICATE"

    def test_register_invalid_type(self, root: Path) -> None:
        result = ops.register(root, "SL-1", "invalid_type", {"command": "true"})
        err = _err(result)
        assert err["error"] == "SPEC_INVALID_TYPE"

    def test_register_persists_to_disk(self, root: Path) -> None:
        ops.register(root, "SL-1", "execute", {"command": "true"})
        specs_file = root / "specs.jsonl"
        assert specs_file.exists()
        lines = [json.loads(line) for line in specs_file.read_text().splitlines() if line.strip()]
        assert len(lines) == 1
        assert lines[0]["id"] == "SL-1"


# ---------------------------------------------------------------------------
# list_specs
# ---------------------------------------------------------------------------


class TestListSpecs:
    def test_list_empty(self, root: Path) -> None:
        data = _ok(ops.list_specs(root))
        assert data == []

    def test_list_returns_all(self, root: Path) -> None:
        ops.register(root, "SL-1", "execute", {"command": "true"})
        ops.register(root, "SL-2", "review", {"question": "Is it correct?", "artifact": "out.txt"})
        data = _ok(ops.list_specs(root))
        ids = {r["id"] for r in data}
        assert ids == {"SL-1", "SL-2"}

    def test_list_deduplicates_last_wins(self, root: Path) -> None:
        ops.register(root, "SL-1", "execute", {"command": "true"})
        # Satisfy to create a second record for same ID
        ops.satisfy(root, "SL-1", {"role": "tester"})
        data = _ok(ops.list_specs(root))
        assert len(data) == 1
        assert data[0]["status"] == "satisfied"


# ---------------------------------------------------------------------------
# satisfy
# ---------------------------------------------------------------------------


class TestSatisfy:
    def test_satisfy_pending_contract(self, root: Path) -> None:
        ops.register(root, "SL-1", "execute", {"command": "true"})
        result = ops.satisfy(root, "SL-1", {"role": "tester", "verification": "passed"})
        data = _ok(result)
        assert data["status"] == "satisfied"
        assert data["id"] == "SL-1"
        assert "satisfied_at" in data

    def test_satisfy_not_found(self, root: Path) -> None:
        result = ops.satisfy(root, "MISSING-1", {"role": "tester"})
        err = _err(result)
        assert err["error"] == "SPEC_NOT_FOUND"

    def test_satisfy_already_satisfied(self, root: Path) -> None:
        ops.register(root, "SL-1", "execute", {"command": "true"})
        ops.satisfy(root, "SL-1", {"role": "tester"})
        result = ops.satisfy(root, "SL-1", {"role": "tester"})
        err = _err(result)
        assert err["error"] == "SPEC_ALREADY_SATISFIED"

    def test_satisfy_hash_mismatch_rejected(self, root: Path) -> None:
        """Tampered content produces hash mismatch at satisfy time [SL-16]."""
        ops.register(root, "SL-1", "execute", {"command": "true"})
        # Tamper with the stored content directly in the JSONL
        path = root / "specs.jsonl"
        lines = path.read_text().splitlines()
        record = json.loads(lines[-1])
        record["content"] = {"command": "false"}  # tamper without updating hash
        path.write_text("\n".join(lines[:-1] + [json.dumps(record, separators=(",", ":"))]) + "\n")
        result = ops.satisfy(root, "SL-1", {"role": "tester"})
        err = _err(result)
        assert err["error"] == "SPEC_HASH_MISMATCH"

    def test_satisfy_verifies_hash_automatically(self, root: Path) -> None:
        """Hash verification is automatic — caller does not need to supply hash [SL-16]."""
        ops.register(root, "SL-1", "execute", {"command": "true"})
        result = ops.satisfy(root, "SL-1", {"role": "tester"})
        data = _ok(result)
        assert data["status"] == "satisfied"

    def test_satisfy_persists_proof(self, root: Path) -> None:
        ops.register(root, "SL-1", "execute", {"command": "true"})
        ops.satisfy(root, "SL-1", {"role": "tester", "notes": "all good"})
        data = _ok(ops.list_specs(root))
        contract = data[0]
        assert contract["proof"]["role"] == "tester"


# ---------------------------------------------------------------------------
# preflight
# ---------------------------------------------------------------------------


class TestPreflight:
    def test_preflight_empty(self, root: Path) -> None:
        data = _ok(ops.preflight(root))
        assert data["still_satisfied"] == []
        assert data["revoked"] == []

    def test_preflight_passing_execute_stays_satisfied(self, root: Path) -> None:
        ops.register(root, "SL-1", "execute", {"command": "true"})
        ops.satisfy(root, "SL-1", {"role": "tester"})
        data = _ok(ops.preflight(root))
        assert "SL-1" in data["still_satisfied"]
        assert "SL-1" not in data["revoked"]

    def test_preflight_failing_execute_revoked(self, root: Path) -> None:
        ops.register(root, "SL-1", "execute", {"command": "false"})
        # Satisfy succeeds (hash is consistent), but command fails at preflight
        ops.satisfy(root, "SL-1", {"role": "tester"})
        data = _ok(ops.preflight(root))
        assert "SL-1" in data["revoked"]
        assert "SL-1" not in data["still_satisfied"]

    def test_preflight_revoked_resets_status(self, root: Path) -> None:
        ops.register(root, "SL-1", "execute", {"command": "false"})
        ops.satisfy(root, "SL-1", {"role": "tester"})  # hash ok, command fails at preflight
        ops.preflight(root)
        contracts = _ok(ops.list_specs(root))
        assert contracts[0]["status"] == "pending"

    def test_preflight_skips_pending(self, root: Path) -> None:
        ops.register(root, "SL-1", "execute", {"command": "true"})
        data = _ok(ops.preflight(root))
        assert "SL-1" not in data["still_satisfied"]
        assert "SL-1" not in data["revoked"]

    def test_preflight_review_no_artifact_stays_satisfied(self, root: Path) -> None:
        ops.register(root, "SL-1", "review", {"question": "Is it correct?", "artifact": "out.txt"})
        ops.satisfy(root, "SL-1", {"role": "reviewer"})
        data = _ok(ops.preflight(root))
        assert "SL-1" in data["still_satisfied"]

    def test_preflight_review_changed_artifact_revoked(self, root: Path, tmp_path: Path) -> None:
        artifact = tmp_path / "artifact.txt"
        artifact.write_text("original content")
        ops.register(root, "SL-1", "review", {"question": "Is artifact correct?", "artifact": "artifact.txt"})
        ops.satisfy(root, "SL-1", {"role": "reviewer", "artifact_path": str(artifact)})
        # Change the artifact after satisfaction
        artifact.write_text("changed content")
        data = _ok(ops.preflight(root))
        assert "SL-1" in data["revoked"]


# ---------------------------------------------------------------------------
# divergence
# ---------------------------------------------------------------------------


class TestDivergence:
    def test_divergence_all_match(self, root: Path, tmp_path: Path) -> None:
        ops.register(root, "SL-1", "execute", {"command": "true"})
        doc = tmp_path / "spec.md"
        doc.write_text("See [SL-1] for details.")
        data = _ok(ops.divergence(root, doc))
        assert data["unregistered"] == []
        assert data["orphaned"] == []

    def test_divergence_unregistered(self, root: Path, tmp_path: Path) -> None:
        doc = tmp_path / "spec.md"
        doc.write_text("See [SL-1] for details.")
        data = _ok(ops.divergence(root, doc))
        assert "SL-1" in data["unregistered"]

    def test_divergence_orphaned(self, root: Path, tmp_path: Path) -> None:
        ops.register(root, "SL-1", "execute", {"command": "true"})
        doc = tmp_path / "spec.md"
        doc.write_text("No references here.")
        data = _ok(ops.divergence(root, doc))
        assert "SL-1" in data["orphaned"]

    def test_divergence_missing_doc(self, root: Path) -> None:
        result = ops.divergence(root, Path("/nonexistent/path/spec.md"))
        err = _err(result)
        assert err["error"] == "SPEC_DOC_NOT_FOUND"

    def test_divergence_matches_bracket_pattern(self, root: Path, tmp_path: Path) -> None:
        ops.register(root, "PV-3", "execute", {"command": "true"})
        doc = tmp_path / "spec.md"
        doc.write_text("Requirements: [PV-3] must pass. Also check PV-3 without brackets.")
        data = _ok(ops.divergence(root, doc))
        assert data["unregistered"] == []
        assert data["orphaned"] == []


# ---------------------------------------------------------------------------
# coverage
# ---------------------------------------------------------------------------


class TestCoverage:
    def test_coverage_registered_satisfied(self, root: Path) -> None:
        ops.register(root, "SL-1", "execute", {"command": "true"})
        ops.satisfy(root, "SL-1", {"role": "tester"})
        data = _ok(ops.coverage(root, ["SL-1"]))
        assert len(data) == 1
        r = data[0]
        assert r["id"] == "SL-1"
        assert r["registered"] is True
        assert r["status"] == "satisfied"
        assert r["needs_work"] is False

    def test_coverage_registered_pending(self, root: Path) -> None:
        ops.register(root, "SL-1", "execute", {"command": "true"})
        data = _ok(ops.coverage(root, ["SL-1"]))
        r = data[0]
        assert r["registered"] is True
        assert r["status"] == "pending"
        assert r["needs_work"] is True

    def test_coverage_unregistered(self, root: Path) -> None:
        data = _ok(ops.coverage(root, ["MISSING-1"]))
        r = data[0]
        assert r["registered"] is False
        assert r["status"] is None
        assert r["needs_work"] is True

    def test_coverage_multiple_ids(self, root: Path) -> None:
        ops.register(root, "SL-1", "execute", {"command": "true"})
        ops.satisfy(root, "SL-1", {"role": "tester"})
        ops.register(root, "SL-2", "review", {"question": "Is it done?", "artifact": "report.txt"})
        data = _ok(ops.coverage(root, ["SL-1", "SL-2", "SL-3"]))
        assert len(data) == 3
        by_id = {r["id"]: r for r in data}
        assert by_id["SL-1"]["needs_work"] is False
        assert by_id["SL-2"]["needs_work"] is True
        assert by_id["SL-3"]["registered"] is False

    def test_coverage_empty_ids(self, root: Path) -> None:
        data = _ok(ops.coverage(root, []))
        assert data == []


# ---------------------------------------------------------------------------
# tighten
# ---------------------------------------------------------------------------


class TestTighten:
    def test_tighten_updates_content(self, root: Path) -> None:
        ops.register(root, "SL-1", "execute", {"command": "true"})
        result = ops.tighten(root, "SL-1", {"command": "echo updated"})
        data = _ok(result)
        assert data["status"] == "pending"
        assert data["content_hash"] == store_hash.content_hash({"command": "echo updated"})

    def test_tighten_reverts_satisfied_to_pending(self, root: Path) -> None:
        ops.register(root, "SL-1", "execute", {"command": "true"})
        ops.satisfy(root, "SL-1", {"role": "tester"})
        ops.tighten(root, "SL-1", {"command": "echo new"})
        contracts = _ok(ops.list_specs(root))
        assert contracts[0]["status"] == "pending"

    def test_tighten_not_found(self, root: Path) -> None:
        result = ops.tighten(root, "MISSING-1", {"command": "true"})
        err = _err(result)
        assert err["error"] == "SPEC_NOT_FOUND"

    def test_tighten_updates_hash(self, root: Path) -> None:
        old_content = {"command": "true"}
        new_content = {"command": "echo updated"}
        ops.register(root, "SL-1", "execute", old_content)
        result = ops.tighten(root, "SL-1", new_content)
        data = _ok(result)
        assert data["content_hash"] != store_hash.content_hash(old_content)
        assert data["content_hash"] == store_hash.content_hash(new_content)

    def test_tighten_new_content_visible_in_list(self, root: Path) -> None:
        ops.register(root, "SL-1", "execute", {"command": "true"})
        ops.tighten(root, "SL-1", {"command": "echo tightened"})
        contracts = _ok(ops.list_specs(root))
        assert contracts[0]["content"]["command"] == "echo tightened"


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_full_lifecycle(self, root: Path) -> None:
        # Register
        ops.register(root, "SL-1", "execute", {"command": "true"})
        # Verify pending
        contracts = _ok(ops.list_specs(root))
        assert contracts[0]["status"] == "pending"
        # Satisfy
        ops.satisfy(root, "SL-1", {"role": "ci"})
        contracts = _ok(ops.list_specs(root))
        assert contracts[0]["status"] == "satisfied"
        # Preflight passes
        data = _ok(ops.preflight(root))
        assert "SL-1" in data["still_satisfied"]
        # Tighten reverts
        ops.tighten(root, "SL-1", {"command": "echo new"})
        contracts = _ok(ops.list_specs(root))
        assert contracts[0]["status"] == "pending"

    def test_multiple_contracts_independence(self, root: Path) -> None:
        ops.register(root, "SL-1", "execute", {"command": "true"})
        ops.register(root, "SL-2", "execute", {"command": "false"})
        ops.satisfy(root, "SL-1", {"role": "tester"})
        ops.satisfy(root, "SL-2", {"role": "tester"})
        data = _ok(ops.preflight(root))
        assert "SL-1" in data["still_satisfied"]


# ---------------------------------------------------------------------------
# SL-4: count
# ---------------------------------------------------------------------------


class TestSpecCount:
    def test_count_returns_ok_envelope(self, root: Path) -> None:
        result = ops.count(root)
        assert result["ok"] is True
        assert "data" in result
        assert "count" in result["data"]

    def test_count_zero_when_no_specs_file(self, root: Path) -> None:
        # Fresh root directory with no specs registered
        data = _ok(ops.count(root))
        assert data["count"] == 0

    def test_count_reflects_registered_contracts(self, root: Path) -> None:
        ops.register(root, "SL-1", "execute", {"command": "true"})
        ops.register(root, "SL-2", "execute", {"command": "false"})
        data = _ok(ops.count(root))
        assert data["count"] == 2

    def test_count_deduplicates_same_id(self, root: Path) -> None:
        # Registering the same id twice (last-write-wins) should count as 1
        ops.register(root, "SL-1", "execute", {"command": "true"})
        ops.register(root, "SL-1", "execute", {"command": "echo updated"})
        data = _ok(ops.count(root))
        assert data["count"] == 1

    def test_count_is_int(self, root: Path) -> None:
        ops.register(root, "SL-3", "execute", {"command": "true"})
        data = _ok(ops.count(root))
        assert isinstance(data["count"], int)

    def test_count_increases_with_each_new_id(self, root: Path) -> None:
        for i in range(1, 6):
            ops.register(root, f"SL-{i}", "execute", {"command": "true"})
        data = _ok(ops.count(root))
        assert data["count"] == 5


# ---------------------------------------------------------------------------
# SL-9: review-type registration validation
# ---------------------------------------------------------------------------


class TestReviewTypeValidation:
    def test_review_requires_question_field(self, root: Path) -> None:
        # Missing question — must be rejected
        result = ops.register(
            root,
            "SL-10",
            "review",
            {"artifact": "output.txt"},
        )
        err = _err(result)
        assert "error" in err

    def test_review_requires_artifact_field(self, root: Path) -> None:
        # Missing artifact — must be rejected
        result = ops.register(
            root,
            "SL-11",
            "review",
            {"question": "Is the output correct?"},
        )
        err = _err(result)
        assert "error" in err

    def test_review_missing_both_fields_rejected(self, root: Path) -> None:
        result = ops.register(
            root,
            "SL-12",
            "review",
            {"description": "no required fields"},
        )
        err = _err(result)
        assert "error" in err

    def test_review_with_question_and_artifact_succeeds(self, root: Path) -> None:
        result = ops.register(
            root,
            "SL-13",
            "review",
            {"question": "Is the output correct?", "artifact": "output.txt"},
        )
        data = _ok(result)
        assert data["id"] == "SL-13"

    def test_review_evidence_commands_optional(self, root: Path) -> None:
        # evidence_commands is optional — omitting it must not cause rejection
        result = ops.register(
            root,
            "SL-14",
            "review",
            {"question": "Check this.", "artifact": "report.txt"},
        )
        data = _ok(result)
        assert data["id"] == "SL-14"

    def test_review_evidence_commands_accepted_as_list(self, root: Path) -> None:
        result = ops.register(
            root,
            "SL-15",
            "review",
            {"question": "Check this.", "artifact": "report.txt"},
            evidence_commands=["cat report.txt", "wc -l report.txt"],
        )
        data = _ok(result)
        assert data["id"] == "SL-15"

    def test_execute_type_not_affected_by_review_validation(self, root: Path) -> None:
        # execute-type registration must succeed without question/artifact
        result = ops.register(
            root,
            "SL-16",
            "execute",
            {"command": "true"},
        )
        data = _ok(result)
        assert data["id"] == "SL-16"
