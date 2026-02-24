"""Tests for cli.ops.plan — plan finalization, DAG validation, and execution helpers."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from cli.ops.plan import (
    cascade,
    coverage,
    execution_coverage,
    file_delta,
    finalize,
    finalize_file,
    order,
    scope_check,
    transition,
    unexpected_outputs,
)
from cli.store import atomic

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _role(name: str, deps: list[str] | None = None, **overrides: Any) -> dict[str, Any]:
    """Build a minimal valid role dict."""
    base: dict[str, Any] = {
        "name": name,
        "goal": f"Goal of {name}",
        "contract_ids": [],
        "scope": [f"/tmp/{name}"],
        "expected_outputs": [f"/tmp/{name}/out.txt"],
        "context": "",
        "constraints": [],
        "verification": "",
        "assumptions": [],
        "rollback_triggers": [],
        "fallback": "",
        "model": "sonnet",
        "dependencies": deps if deps is not None else [],
    }
    base.update(overrides)
    return base


def _plan(*roles: dict[str, Any], schema_version: int = 2) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "goal": "Test plan",
        "roles": list(roles),
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestHappyPath:
    def test_valid_single_role(self) -> None:
        plan = _plan(_role("alpha"))
        result = finalize(plan)
        assert result["ok"] is True

    def test_valid_multiple_roles(self) -> None:
        plan = _plan(_role("a"), _role("b"), _role("c"))
        result = finalize(plan)
        assert result["ok"] is True

    def test_status_initialized_to_pending(self) -> None:
        plan = _plan(_role("alpha"), _role("beta"))
        result = finalize(plan)
        for role in result["data"]["roles"]:
            assert role["status"] == "pending"

    def test_dep_indices_resolved(self) -> None:
        plan = _plan(_role("a"), _role("b", deps=["a"]))
        result = finalize(plan)
        assert result["ok"] is True
        roles = result["data"]["roles"]
        assert roles[1]["dep_indices"] == [0]

    def test_input_not_mutated(self) -> None:
        role = _role("alpha")
        plan = _plan(role)
        original = copy.deepcopy(plan)
        finalize(plan)
        assert plan == original

    def test_schema_version_1_accepted(self) -> None:
        plan = _plan(_role("alpha"), schema_version=1)
        result = finalize(plan)
        assert result["ok"] is True

    def test_schema_version_2_accepted(self) -> None:
        plan = _plan(_role("alpha"), schema_version=2)
        result = finalize(plan)
        assert result["ok"] is True


# ---------------------------------------------------------------------------
# Role count
# ---------------------------------------------------------------------------

class TestRoleCount:
    def test_too_few_roles_zero(self) -> None:
        plan = _plan()
        result = finalize(plan)
        assert result["ok"] is False
        assert result["error"] == "PLAN_TOO_FEW_ROLES"

    def test_too_many_roles_nine(self) -> None:
        roles = [_role(f"role{i}") for i in range(9)]
        plan = _plan(*roles)
        result = finalize(plan)
        assert result["ok"] is False
        assert result["error"] == "PLAN_TOO_MANY_ROLES"

    def test_exactly_eight_roles_ok(self) -> None:
        roles = [_role(f"role{i}") for i in range(8)]
        plan = _plan(*roles)
        result = finalize(plan)
        assert result["ok"] is True


# ---------------------------------------------------------------------------
# Unique names
# ---------------------------------------------------------------------------

class TestUniqueNames:
    def test_duplicate_name_rejected(self) -> None:
        plan = _plan(_role("alpha"), _role("alpha"))
        result = finalize(plan)
        assert result["ok"] is False
        assert result["error"] == "PLAN_DUPLICATE_NAME"

    def test_different_names_ok(self) -> None:
        plan = _plan(_role("alpha"), _role("beta"))
        result = finalize(plan)
        assert result["ok"] is True


# ---------------------------------------------------------------------------
# Required fields
# ---------------------------------------------------------------------------

class TestRequiredFields:
    def test_missing_field_rejected(self) -> None:
        role = _role("alpha")
        del role["goal"]
        plan = _plan(role)
        result = finalize(plan)
        assert result["ok"] is False
        assert result["error"] == "PLAN_MISSING_FIELD"
        assert "goal" in result["message"]
        assert "alpha" in result["message"]

    def test_all_fields_present_ok(self) -> None:
        plan = _plan(_role("alpha"))
        result = finalize(plan)
        assert result["ok"] is True


# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

class TestSchemaVersion:
    def test_schema_version_3_rejected(self) -> None:
        plan = _plan(_role("alpha"), schema_version=3)
        result = finalize(plan)
        assert result["ok"] is False
        assert result["error"] == "bad_schema_3"

    def test_schema_version_0_rejected(self) -> None:
        plan = _plan(_role("alpha"), schema_version=0)
        result = finalize(plan)
        assert result["ok"] is False
        assert result["error"] == "bad_schema_0"

    def test_schema_version_none_rejected(self) -> None:
        plan = _plan(_role("alpha"))
        plan["schema_version"] = None
        result = finalize(plan)
        assert result["ok"] is False
        assert "bad_schema" in result["error"]


# ---------------------------------------------------------------------------
# DAG / cycle detection
# ---------------------------------------------------------------------------

class TestCycleDetection:
    def test_self_reference_rejected(self) -> None:
        plan = _plan(_role("alpha", deps=["alpha"]))
        result = finalize(plan)
        assert result["ok"] is False
        assert result["error"] == "PLAN_CIRCULAR_DEPENDENCY"

    def test_two_node_cycle_rejected(self) -> None:
        plan = _plan(_role("a", deps=["b"]), _role("b", deps=["a"]))
        result = finalize(plan)
        assert result["ok"] is False
        assert result["error"] == "PLAN_CIRCULAR_DEPENDENCY"

    def test_three_node_cycle_rejected(self) -> None:
        plan = _plan(
            _role("a", deps=["c"]),
            _role("b", deps=["a"]),
            _role("c", deps=["b"]),
        )
        result = finalize(plan)
        assert result["ok"] is False
        assert result["error"] == "PLAN_CIRCULAR_DEPENDENCY"

    def test_diamond_dependency_valid(self) -> None:
        # a -> b, a -> c, b -> d, c -> d  (diamond shape — valid DAG)
        plan = _plan(
            _role("d"),
            _role("b", deps=["d"]),
            _role("c", deps=["d"]),
            _role("a", deps=["b", "c"]),
        )
        result = finalize(plan)
        assert result["ok"] is True

    def test_independent_nodes_valid(self) -> None:
        plan = _plan(_role("x"), _role("y"), _role("z"))
        result = finalize(plan)
        assert result["ok"] is True


# ---------------------------------------------------------------------------
# Unresolvable dependencies
# ---------------------------------------------------------------------------

class TestUnresolvableDependencies:
    def test_unknown_dep_name_rejected(self) -> None:
        plan = _plan(_role("a", deps=["does_not_exist"]))
        result = finalize(plan)
        assert result["ok"] is False
        assert result["error"] == "PLAN_UNRESOLVABLE_DEPENDENCY"
        assert "does_not_exist" in result["message"]


# ---------------------------------------------------------------------------
# Overlap detection
# ---------------------------------------------------------------------------

class TestOverlapDetection:
    def test_overlapping_scopes_detected(self) -> None:
        r0 = _role("r0", scope=["/shared/dir"])
        r1 = _role("r1", scope=["/shared/dir/sub"])
        plan = _plan(r0, r1)
        result = finalize(plan)
        assert result["ok"] is True
        roles = result["data"]["roles"]
        assert 1 in roles[0]["directory_overlaps"]
        assert 0 in roles[1]["directory_overlaps"]

    def test_non_overlapping_scopes(self) -> None:
        r0 = _role("r0", scope=["/project/frontend"])
        r1 = _role("r1", scope=["/project/backend"])
        plan = _plan(r0, r1)
        result = finalize(plan)
        assert result["ok"] is True
        roles = result["data"]["roles"]
        assert roles[0]["directory_overlaps"] == []
        assert roles[1]["directory_overlaps"] == []


# ---------------------------------------------------------------------------
# Topological order
# ---------------------------------------------------------------------------

class TestTopologicalOrder:
    def test_order_respects_dependencies(self) -> None:
        plan = _plan(_role("a"), _role("b", deps=["a"]))
        result = finalize(plan)
        finalized = result["data"]
        ordered = order(finalized)
        # a (index 0) must come before b (index 1)
        assert ordered.index(0) < ordered.index(1)

    def test_order_linear_chain(self) -> None:
        # a -> b -> c  (c depends on b, b depends on a)
        plan = _plan(_role("a"), _role("b", deps=["a"]), _role("c", deps=["b"]))
        result = finalize(plan)
        ordered = order(result["data"])
        assert ordered == [0, 1, 2]

    def test_order_independent_sorted(self) -> None:
        plan = _plan(_role("x"), _role("y"), _role("z"))
        result = finalize(plan)
        ordered = order(result["data"])
        assert set(ordered) == {0, 1, 2}


# ---------------------------------------------------------------------------
# Transition
# ---------------------------------------------------------------------------

class TestTransition:
    def test_transition_updates_status(self, tmp_path: Path) -> None:
        plan = _plan(_role("alpha"))
        result = finalize(plan)
        plan_path = tmp_path / "plan.json"
        atomic.write(plan_path, result["data"])

        tr_result = transition(plan_path, 0, "in_progress")
        assert tr_result["ok"] is True

        updated = atomic.read(plan_path)
        assert updated["roles"][0]["status"] == "in_progress"

    def test_transition_out_of_range(self, tmp_path: Path) -> None:
        plan = _plan(_role("alpha"))
        result = finalize(plan)
        plan_path = tmp_path / "plan.json"
        atomic.write(plan_path, result["data"])

        tr_result = transition(plan_path, 99, "in_progress")
        assert tr_result["ok"] is False
        assert tr_result["error"] == "PLAN_ROLE_INDEX_OUT_OF_RANGE"


# ---------------------------------------------------------------------------
# Cascade
# ---------------------------------------------------------------------------

class TestCascade:
    def test_cascade_marks_dependents_skipped(self, tmp_path: Path) -> None:
        plan = _plan(_role("a"), _role("b", deps=["a"]), _role("c", deps=["b"]))
        result = finalize(plan)
        plan_path = tmp_path / "plan.json"
        atomic.write(plan_path, result["data"])

        cas_result = cascade(plan_path, 0)
        assert cas_result["ok"] is True
        skipped = cas_result["data"]["skipped_indices"]
        assert 1 in skipped
        assert 2 in skipped

        updated = atomic.read(plan_path)
        assert updated["roles"][1]["status"] == "skipped"
        assert updated["roles"][2]["status"] == "skipped"
        # Role 0 itself should not be changed by cascade
        assert updated["roles"][0]["status"] == "pending"

    def test_cascade_no_dependents(self, tmp_path: Path) -> None:
        plan = _plan(_role("a"), _role("b"))
        result = finalize(plan)
        plan_path = tmp_path / "plan.json"
        atomic.write(plan_path, result["data"])

        cas_result = cascade(plan_path, 0)
        assert cas_result["ok"] is True
        assert cas_result["data"]["skipped_indices"] == []


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------

class TestCoverage:
    def test_coverage_matched_and_unmatched(self) -> None:
        plan_data = {
            "schema_version": 2,
            "goal": "test",
            "roles": [
                {**_role("r0"), "contract_ids": ["c1", "c2"]},
                {**_role("r1"), "contract_ids": ["c3"]},
            ],
        }
        spec_data = {
            "contracts": [
                {"id": "c1"},
                {"id": "c3"},
                {"id": "c4"},
            ]
        }
        result = coverage(plan_data, spec_data)
        assert result["ok"] is True
        data = result["data"]
        assert set(data["matched"]) == {"c1", "c3"}
        assert set(data["unmatched_in_plan"]) == {"c2"}
        assert set(data["uncovered_in_spec"]) == {"c4"}

    def test_coverage_all_matched(self) -> None:
        plan_data = {
            "schema_version": 2,
            "goal": "test",
            "roles": [
                {**_role("r0"), "contract_ids": ["c1"]},
            ],
        }
        spec_data = {"contracts": [{"id": "c1"}]}
        result = coverage(plan_data, spec_data)
        assert result["ok"] is True
        assert result["data"]["matched"] == ["c1"]
        assert result["data"]["unmatched_in_plan"] == []
        assert result["data"]["uncovered_in_spec"] == []

    def test_coverage_empty_plan(self) -> None:
        plan_data = {
            "schema_version": 2,
            "goal": "test",
            "roles": [_role("r0")],  # contract_ids is []
        }
        spec_data = {"contracts": [{"id": "c1"}]}
        result = coverage(plan_data, spec_data)
        assert result["ok"] is True
        assert result["data"]["uncovered_in_spec"] == ["c1"]


# ---------------------------------------------------------------------------
# finalize_file
# ---------------------------------------------------------------------------

class TestFinalizeFile:
    def test_finalize_file_writes_back(self, tmp_path: Path) -> None:
        plan = _plan(_role("alpha"))
        plan_path = tmp_path / "plan.json"
        atomic.write(plan_path, plan)

        result = finalize_file(plan_path)
        assert result["ok"] is True

        stored = atomic.read(plan_path)
        assert stored["roles"][0]["status"] == "pending"

    def test_finalize_file_not_found(self, tmp_path: Path) -> None:
        result = finalize_file(tmp_path / "nonexistent.json")
        assert result["ok"] is False
        assert result["error"] == "PLAN_FILE_NOT_FOUND"


# ---------------------------------------------------------------------------
# file_delta
# ---------------------------------------------------------------------------

class TestFileDelta:
    def test_added_files(self) -> None:
        delta = file_delta(["a.py"], ["a.py", "b.py"])
        assert "b.py" in delta["added"]
        assert delta["removed"] == []

    def test_removed_files(self) -> None:
        delta = file_delta(["a.py", "b.py"], ["a.py"])
        assert "b.py" in delta["removed"]
        assert delta["added"] == []

    def test_no_change(self) -> None:
        delta = file_delta(["a.py"], ["a.py"])
        assert delta["added"] == []
        assert delta["removed"] == []


# ---------------------------------------------------------------------------
# unexpected_outputs
# ---------------------------------------------------------------------------

class TestUnexpectedOutputs:
    def test_unexpected_detected(self) -> None:
        plan = _plan(_role("r0", expected_outputs=["out.txt"]))
        result = finalize(plan)
        finalized = result["data"]
        unexpected = unexpected_outputs(finalized, 0, ["out.txt", "surprise.log"])
        assert "surprise.log" in unexpected
        assert "out.txt" not in unexpected

    def test_all_expected(self) -> None:
        plan = _plan(_role("r0", expected_outputs=["out.txt"]))
        result = finalize(plan)
        finalized = result["data"]
        unexpected = unexpected_outputs(finalized, 0, ["out.txt"])
        assert unexpected == []


# ---------------------------------------------------------------------------
# execution_coverage (SL-46)
# ---------------------------------------------------------------------------


class TestExecutionCoverage:
    """Behavioral contracts for execution_coverage (SL-46)."""

    def _spec_item(self, id: str, status: str) -> dict[str, Any]:
        return {"id": id, "status": status}

    def _cov(self, plan: dict[str, Any], spec_data: list[dict[str, Any]]) -> dict[str, Any]:
        return execution_coverage(plan, spec_data)

    def test_returns_ok_envelope(self) -> None:
        plan = _plan(_role("r0", contract_ids=["c1"]))
        spec_data = [self._spec_item("c1", "pending")]
        result = self._cov(plan, spec_data)
        assert result["ok"] is True
        assert "data" in result

    def test_data_has_required_keys(self) -> None:
        plan = _plan(_role("r0", contract_ids=["c1"]))
        spec_data = [self._spec_item("c1", "pending")]
        data = self._cov(plan, spec_data)["data"]
        assert "missing" in data
        assert "pending" in data
        assert "satisfied" in data
        assert "roles_to_execute" in data
        assert "roles_to_skip" in data
        assert "has_work" in data

    def test_missing_contracts_not_in_spec(self) -> None:
        # c2 is in the plan but not in spec_data
        plan = _plan(_role("r0", contract_ids=["c1", "c2"]))
        spec_data = [self._spec_item("c1", "pending")]
        data = self._cov(plan, spec_data)["data"]
        assert "c2" in data["missing"]
        assert "c1" not in data["missing"]

    def test_pending_contracts_status_not_satisfied(self) -> None:
        plan = _plan(_role("r0", contract_ids=["c1", "c2"]))
        spec_data = [
            self._spec_item("c1", "pending"),
            self._spec_item("c2", "in_progress"),
        ]
        data = self._cov(plan, spec_data)["data"]
        assert "c1" in data["pending"]
        assert "c2" in data["pending"]
        assert data["satisfied"] == []

    def test_satisfied_contracts_status_satisfied(self) -> None:
        plan = _plan(_role("r0", contract_ids=["c1", "c2"]))
        spec_data = [
            self._spec_item("c1", "satisfied"),
            self._spec_item("c2", "satisfied"),
        ]
        data = self._cov(plan, spec_data)["data"]
        assert "c1" in data["satisfied"]
        assert "c2" in data["satisfied"]
        assert data["pending"] == []

    def test_mixed_pending_and_satisfied(self) -> None:
        plan = _plan(_role("r0", contract_ids=["c1", "c2"]))
        spec_data = [
            self._spec_item("c1", "satisfied"),
            self._spec_item("c2", "pending"),
        ]
        data = self._cov(plan, spec_data)["data"]
        assert "c1" in data["satisfied"]
        assert "c2" in data["pending"]

    def test_roles_to_execute_has_pending_contract(self) -> None:
        # Role 0 has a pending contract; role 1 has all satisfied
        plan = _plan(
            _role("r0", contract_ids=["c1"]),
            _role("r1", contract_ids=["c2"]),
        )
        spec_data = [
            self._spec_item("c1", "pending"),
            self._spec_item("c2", "satisfied"),
        ]
        data = self._cov(plan, spec_data)["data"]
        assert 0 in data["roles_to_execute"]
        assert 1 not in data["roles_to_execute"]

    def test_roles_to_skip_all_contracts_satisfied(self) -> None:
        plan = _plan(
            _role("r0", contract_ids=["c1"]),
            _role("r1", contract_ids=["c2"]),
        )
        spec_data = [
            self._spec_item("c1", "pending"),
            self._spec_item("c2", "satisfied"),
        ]
        data = self._cov(plan, spec_data)["data"]
        assert 1 in data["roles_to_skip"]
        assert 0 not in data["roles_to_skip"]

    def test_has_work_true_when_any_pending(self) -> None:
        plan = _plan(_role("r0", contract_ids=["c1"]))
        spec_data = [self._spec_item("c1", "pending")]
        data = self._cov(plan, spec_data)["data"]
        assert data["has_work"] is True

    def test_has_work_false_when_all_satisfied(self) -> None:
        plan = _plan(_role("r0", contract_ids=["c1"]))
        spec_data = [self._spec_item("c1", "satisfied")]
        data = self._cov(plan, spec_data)["data"]
        assert data["has_work"] is False

    def test_role_with_no_contract_ids_is_skipped(self) -> None:
        # A role with no contract_ids has all contracts satisfied vacuously
        plan = _plan(_role("r0", contract_ids=[]))
        spec_data: list[dict[str, Any]] = []
        data = self._cov(plan, spec_data)["data"]
        assert 0 in data["roles_to_skip"]
        assert 0 not in data["roles_to_execute"]

    def test_multiple_roles_some_execute_some_skip(self) -> None:
        plan = _plan(
            _role("r0", contract_ids=["c1", "c2"]),
            _role("r1", contract_ids=["c3"]),
            _role("r2", contract_ids=["c4"]),
        )
        spec_data = [
            self._spec_item("c1", "satisfied"),
            self._spec_item("c2", "pending"),  # r0 has at least one pending
            self._spec_item("c3", "satisfied"),  # r1 all satisfied
            self._spec_item("c4", "satisfied"),  # r2 all satisfied
        ]
        data = self._cov(plan, spec_data)["data"]
        assert 0 in data["roles_to_execute"]
        assert 1 in data["roles_to_skip"]
        assert 2 in data["roles_to_skip"]

    def test_missing_contracts_not_counted_as_pending_or_satisfied(self) -> None:
        plan = _plan(_role("r0", contract_ids=["c_missing"]))
        spec_data: list[dict[str, Any]] = []
        data = self._cov(plan, spec_data)["data"]
        assert "c_missing" in data["missing"]
        assert "c_missing" not in data["pending"]
        assert "c_missing" not in data["satisfied"]

    def test_empty_plan_roles(self) -> None:
        plan = {"schema_version": 2, "goal": "test", "roles": []}
        spec_data: list[dict[str, Any]] = []
        result = self._cov(plan, spec_data)
        assert result["ok"] is True
        data = result["data"]
        assert data["missing"] == []
        assert data["pending"] == []
        assert data["satisfied"] == []
        assert data["roles_to_execute"] == []
        assert data["roles_to_skip"] == []
        assert data["has_work"] is False

    def test_role_with_all_missing_contracts_not_in_skip(self) -> None:
        # If all contracts are missing (not in registry), the role should not
        # be skipped — it cannot be confirmed satisfied
        plan = _plan(_role("r0", contract_ids=["c_missing"]))
        spec_data: list[dict[str, Any]] = []
        data = self._cov(plan, spec_data)["data"]
        assert 0 not in data["roles_to_skip"]


# ---------------------------------------------------------------------------
# model validation (PV-4)
# ---------------------------------------------------------------------------


class TestModelValidation:
    """Behavioral contracts for model field validation (PV-4)."""

    VALID_MODELS = {"opus", "sonnet", "haiku"}

    def test_valid_model_opus_accepted(self) -> None:
        plan = _plan(_role("r0", model="opus"))
        result = finalize(plan)
        assert result["ok"] is True

    def test_valid_model_sonnet_accepted(self) -> None:
        plan = _plan(_role("r0", model="sonnet"))
        result = finalize(plan)
        assert result["ok"] is True

    def test_valid_model_haiku_accepted(self) -> None:
        plan = _plan(_role("r0", model="haiku"))
        result = finalize(plan)
        assert result["ok"] is True

    def test_invalid_model_rejected(self) -> None:
        plan = _plan(_role("r0", model="gpt-4"))
        result = finalize(plan)
        assert result["ok"] is False

    def test_invalid_model_empty_string_rejected(self) -> None:
        plan = _plan(_role("r0", model=""))
        result = finalize(plan)
        assert result["ok"] is False

    def test_invalid_model_unknown_name_rejected(self) -> None:
        plan = _plan(_role("r0", model="gemini"))
        result = finalize(plan)
        assert result["ok"] is False

    def test_invalid_model_case_sensitive(self) -> None:
        # Model names must be lowercase; "Sonnet" is not a valid model
        plan = _plan(_role("r0", model="Sonnet"))
        result = finalize(plan)
        assert result["ok"] is False

    def test_invalid_model_partial_match_rejected(self) -> None:
        # "son" is not a valid model even though it's a prefix of "sonnet"
        plan = _plan(_role("r0", model="son"))
        result = finalize(plan)
        assert result["ok"] is False

    def test_invalid_model_error_code_present(self) -> None:
        plan = _plan(_role("r0", model="invalid-model"))
        result = finalize(plan)
        assert result["ok"] is False
        assert "error" in result

    def test_multiple_roles_one_invalid_model_rejected(self) -> None:
        # If any role has an invalid model, the whole plan is rejected
        plan = _plan(
            _role("r0", model="sonnet"),
            _role("r1", model="bad-model"),
        )
        result = finalize(plan)
        assert result["ok"] is False

    def test_multiple_roles_all_valid_models_accepted(self) -> None:
        plan = _plan(
            _role("r0", model="opus"),
            _role("r1", model="sonnet"),
            _role("r2", model="haiku"),
        )
        result = finalize(plan)
        assert result["ok"] is True

    def test_invalid_model_via_finalize_file(self, tmp_path: Path) -> None:
        plan = _plan(_role("r0", model="not-a-model"))
        plan_path = tmp_path / "plan.json"
        atomic.write(plan_path, plan)
        result = finalize_file(plan_path)
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# EC-6: scope_check
# ---------------------------------------------------------------------------


class TestScopeCheck:
    """Contract EC-6: scope_check(plan, role_index, file) -> bool."""

    def test_in_scope_file_accepted(self, tmp_path: Path) -> None:
        scope_dir = tmp_path / "lib"
        scope_dir.mkdir()
        target = scope_dir / "module.py"
        target.touch()
        plan = _plan(_role("r0", scope=[str(scope_dir)]))
        assert scope_check(plan, 0, str(target)) is True

    def test_out_of_scope_file_rejected(self, tmp_path: Path) -> None:
        scope_dir = tmp_path / "lib"
        scope_dir.mkdir()
        outside = tmp_path / "other" / "module.py"
        outside.parent.mkdir()
        outside.touch()
        plan = _plan(_role("r0", scope=[str(scope_dir)]))
        assert scope_check(plan, 0, str(outside)) is False

    def test_partial_directory_name_does_not_match(self, tmp_path: Path) -> None:
        # scope `lib/` must NOT match `library/foo.py`
        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()
        library_dir = tmp_path / "library"
        library_dir.mkdir()
        outside = library_dir / "foo.py"
        outside.touch()
        plan = _plan(_role("r0", scope=[str(lib_dir)]))
        assert scope_check(plan, 0, str(outside)) is False

    def test_fnmatch_pattern_matches(self, tmp_path: Path) -> None:
        foo = tmp_path / "foo.py"
        foo.touch()
        plan = _plan(_role("r0", scope=["*.py"]))
        assert scope_check(plan, 0, "foo.py") is True

    def test_fnmatch_pattern_rejects_non_matching(self, tmp_path: Path) -> None:
        plan = _plan(_role("r0", scope=["*.py"]))
        assert scope_check(plan, 0, "foo.txt") is False

    def test_nested_subdirectory_accepted(self, tmp_path: Path) -> None:
        src_dir = tmp_path / "src"
        nested = src_dir / "deep" / "nested"
        nested.mkdir(parents=True)
        target = nested / "file.py"
        target.touch()
        plan = _plan(_role("r0", scope=[str(src_dir)]))
        assert scope_check(plan, 0, str(target)) is True
