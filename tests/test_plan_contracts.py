"""Tests for plan-hardening behavioral contracts (EM-11, EM-12, EM-13).

These tests assert behavioral contracts for transition() and cascade() in
cli.ops.plan. They are written against the spec only — no implementation
details are assumed beyond the function signatures and result envelope shape.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from cli.ops.plan import cascade, finalize, transition
from cli.store import atomic


# ---------------------------------------------------------------------------
# Helpers
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


def _finalized_plan_file(tmp_path: Path, *roles: dict[str, Any]) -> Path:
    """Write a finalized plan with the given roles to tmp_path/plan.json."""
    plan = _plan(*roles)
    result = finalize(plan)
    assert result["ok"] is True, f"finalize failed: {result}"
    plan_path = tmp_path / "plan.json"
    atomic.write(plan_path, result["data"])
    return plan_path


def _set_role_status(plan_path: Path, role_index: int, status: str) -> None:
    """Directly patch a role's status on disk (bypasses transition guards)."""
    data = atomic.read(plan_path)
    data["roles"][role_index]["status"] = status
    atomic.write(plan_path, data)


# ---------------------------------------------------------------------------
# EM-11: Reject transitions FROM terminal states
# ---------------------------------------------------------------------------


class TestEM11TerminalStateRejection:
    """EM-11: transition() must reject any status change from terminal states."""

    @pytest.mark.parametrize("terminal_status", ["completed", "failed", "skipped"])  # type: ignore[misc]
    def test_reject_transition_from_completed(
        self, tmp_path: Path, terminal_status: str
    ) -> None:
        plan_path = _finalized_plan_file(tmp_path, _role("alpha"))
        _set_role_status(plan_path, 0, terminal_status)

        result = transition(plan_path, 0, "in_progress")

        assert result["ok"] is False
        assert result["error"] == "PLAN_INVALID_TRANSITION"

    def test_reject_completed_to_pending(self, tmp_path: Path) -> None:
        plan_path = _finalized_plan_file(tmp_path, _role("alpha"))
        _set_role_status(plan_path, 0, "completed")

        result = transition(plan_path, 0, "pending")

        assert result["ok"] is False
        assert result["error"] == "PLAN_INVALID_TRANSITION"

    def test_reject_failed_to_pending(self, tmp_path: Path) -> None:
        plan_path = _finalized_plan_file(tmp_path, _role("alpha"))
        _set_role_status(plan_path, 0, "failed")

        result = transition(plan_path, 0, "pending")

        assert result["ok"] is False
        assert result["error"] == "PLAN_INVALID_TRANSITION"

    def test_reject_skipped_to_pending(self, tmp_path: Path) -> None:
        plan_path = _finalized_plan_file(tmp_path, _role("alpha"))
        _set_role_status(plan_path, 0, "skipped")

        result = transition(plan_path, 0, "pending")

        assert result["ok"] is False
        assert result["error"] == "PLAN_INVALID_TRANSITION"

    def test_reject_completed_to_failed(self, tmp_path: Path) -> None:
        plan_path = _finalized_plan_file(tmp_path, _role("alpha"))
        _set_role_status(plan_path, 0, "completed")

        result = transition(plan_path, 0, "failed")

        assert result["ok"] is False
        assert result["error"] == "PLAN_INVALID_TRANSITION"

    def test_reject_failed_to_skipped(self, tmp_path: Path) -> None:
        plan_path = _finalized_plan_file(tmp_path, _role("alpha"))
        _set_role_status(plan_path, 0, "failed")

        result = transition(plan_path, 0, "skipped")

        assert result["ok"] is False
        assert result["error"] == "PLAN_INVALID_TRANSITION"

    def test_reject_skipped_to_completed(self, tmp_path: Path) -> None:
        plan_path = _finalized_plan_file(tmp_path, _role("alpha"))
        _set_role_status(plan_path, 0, "skipped")

        result = transition(plan_path, 0, "completed")

        assert result["ok"] is False
        assert result["error"] == "PLAN_INVALID_TRANSITION"

    def test_plan_file_unchanged_after_rejected_terminal_transition(
        self, tmp_path: Path
    ) -> None:
        """Rejected transitions must not mutate the plan file."""
        plan_path = _finalized_plan_file(tmp_path, _role("alpha"))
        _set_role_status(plan_path, 0, "completed")

        transition(plan_path, 0, "in_progress")

        updated = atomic.read(plan_path)
        assert updated["roles"][0]["status"] == "completed"


# ---------------------------------------------------------------------------
# EM-12: Reject invalid status transitions (non-terminal source states)
# ---------------------------------------------------------------------------


class TestEM12InvalidTransitions:
    """EM-12: Only valid transitions are allowed; all others must be rejected."""

    # --- Valid transitions must succeed ---

    def test_pending_to_in_progress_ok(self, tmp_path: Path) -> None:
        plan_path = _finalized_plan_file(tmp_path, _role("alpha"))

        result = transition(plan_path, 0, "in_progress")

        assert result["ok"] is True

    def test_pending_to_skipped_ok(self, tmp_path: Path) -> None:
        plan_path = _finalized_plan_file(tmp_path, _role("alpha"))

        result = transition(plan_path, 0, "skipped")

        assert result["ok"] is True

    def test_in_progress_to_completed_ok(self, tmp_path: Path) -> None:
        plan_path = _finalized_plan_file(tmp_path, _role("alpha"))
        _set_role_status(plan_path, 0, "in_progress")

        result = transition(plan_path, 0, "completed")

        assert result["ok"] is True

    def test_in_progress_to_failed_ok(self, tmp_path: Path) -> None:
        plan_path = _finalized_plan_file(tmp_path, _role("alpha"))
        _set_role_status(plan_path, 0, "in_progress")

        result = transition(plan_path, 0, "failed")

        assert result["ok"] is True

    # --- Invalid transitions must be rejected ---

    def test_pending_to_completed_rejected(self, tmp_path: Path) -> None:
        plan_path = _finalized_plan_file(tmp_path, _role("alpha"))

        result = transition(plan_path, 0, "completed")

        assert result["ok"] is False
        assert result["error"] == "PLAN_INVALID_TRANSITION"

    def test_pending_to_failed_rejected(self, tmp_path: Path) -> None:
        plan_path = _finalized_plan_file(tmp_path, _role("alpha"))

        result = transition(plan_path, 0, "failed")

        assert result["ok"] is False
        assert result["error"] == "PLAN_INVALID_TRANSITION"

    def test_in_progress_to_skipped_rejected(self, tmp_path: Path) -> None:
        plan_path = _finalized_plan_file(tmp_path, _role("alpha"))
        _set_role_status(plan_path, 0, "in_progress")

        result = transition(plan_path, 0, "skipped")

        assert result["ok"] is False
        assert result["error"] == "PLAN_INVALID_TRANSITION"

    def test_in_progress_to_pending_rejected(self, tmp_path: Path) -> None:
        plan_path = _finalized_plan_file(tmp_path, _role("alpha"))
        _set_role_status(plan_path, 0, "in_progress")

        result = transition(plan_path, 0, "pending")

        assert result["ok"] is False
        assert result["error"] == "PLAN_INVALID_TRANSITION"

    def test_valid_transition_updates_status_on_disk(self, tmp_path: Path) -> None:
        plan_path = _finalized_plan_file(tmp_path, _role("alpha"))

        transition(plan_path, 0, "in_progress")

        updated = atomic.read(plan_path)
        assert updated["roles"][0]["status"] == "in_progress"

    def test_invalid_transition_does_not_update_status_on_disk(
        self, tmp_path: Path
    ) -> None:
        plan_path = _finalized_plan_file(tmp_path, _role("alpha"))

        transition(plan_path, 0, "completed")

        updated = atomic.read(plan_path)
        assert updated["roles"][0]["status"] == "pending"


# ---------------------------------------------------------------------------
# EM-13: Abort signal when >50% of pending roles would be skipped
# ---------------------------------------------------------------------------


class TestEM13AbortThreshold:
    """EM-13: cascade() returns abort:true when strictly >50% of pending roles
    would be skipped, and returns pending_before count."""

    def test_cascade_returns_pending_before_count(self, tmp_path: Path) -> None:
        """cascade() result data must include pending_before."""
        # 2 roles: alpha (failed/cascading), beta (pending, dependent)
        plan_path = _finalized_plan_file(
            tmp_path,
            _role("alpha"),
            _role("beta", deps=["alpha"]),
        )
        result = cascade(plan_path, 0)

        assert result["ok"] is True
        assert "pending_before" in result["data"]

    def test_3_of_6_pending_does_not_abort(self, tmp_path: Path) -> None:
        """Skipping 3 of 6 pending roles (50%) must NOT trigger abort."""
        # roles: a(root), b->a, c->a, d->a, e(independent), f(independent)
        # Cascading from a skips b, c, d = 3 roles out of 6 pending total = 50%
        plan_path = _finalized_plan_file(
            tmp_path,
            _role("a"),
            _role("b", deps=["a"]),
            _role("c", deps=["a"]),
            _role("d", deps=["a"]),
            _role("e"),
            _role("f"),
        )
        result = cascade(plan_path, 0)

        assert result["ok"] is True
        assert result["data"]["pending_before"] == 6
        # 3 skipped / 6 pending = 50%, which is NOT strictly > 50%
        assert result["data"].get("abort", False) is False

    def test_4_of_6_pending_does_abort(self, tmp_path: Path) -> None:
        """Skipping 4 of 6 pending roles (>50%) must trigger abort."""
        # roles: a(root), b->a, c->a, d->a, e->a, f(independent)
        # Cascading from a skips b, c, d, e = 4 roles out of 6 pending total
        plan_path = _finalized_plan_file(
            tmp_path,
            _role("a"),
            _role("b", deps=["a"]),
            _role("c", deps=["a"]),
            _role("d", deps=["a"]),
            _role("e", deps=["a"]),
            _role("f"),
        )
        result = cascade(plan_path, 0)

        assert result["ok"] is True
        assert result["data"]["pending_before"] == 6
        assert result["data"]["abort"] is True

    def test_abort_boundary_exactly_50_percent_no_abort(
        self, tmp_path: Path
    ) -> None:
        """Exactly 50% skipped must NOT abort (contract requires strictly >50%)."""
        # 2 pending roles, 1 would be skipped = 50% — no abort
        plan_path = _finalized_plan_file(
            tmp_path,
            _role("a"),
            _role("b", deps=["a"]),
        )
        result = cascade(plan_path, 0)

        assert result["ok"] is True
        assert result["data"]["pending_before"] == 2
        assert result["data"].get("abort", False) is False

    def test_abort_boundary_one_more_than_half(self, tmp_path: Path) -> None:
        """One more than half (e.g., 2 of 3) must abort."""
        # 3 pending: a(root), b->a, c->a
        # Cascading from a skips b, c = 2 of 3 pending > 50%
        plan_path = _finalized_plan_file(
            tmp_path,
            _role("a"),
            _role("b", deps=["a"]),
            _role("c", deps=["a"]),
        )
        result = cascade(plan_path, 0)

        assert result["ok"] is True
        assert result["data"]["pending_before"] == 3
        assert result["data"]["abort"] is True

    def test_pending_before_excludes_already_completed_roles(
        self, tmp_path: Path
    ) -> None:
        """pending_before must count only roles with status 'pending'."""
        # 4 roles: a(root), b->a(pending), c->a(pending), d(completed already)
        # pending_before should be 3 (a, b, c); d is completed and excluded
        plan_path = _finalized_plan_file(
            tmp_path,
            _role("a"),
            _role("b", deps=["a"]),
            _role("c", deps=["a"]),
            _role("d"),
        )
        _set_role_status(plan_path, 3, "completed")

        result = cascade(plan_path, 0)

        assert result["ok"] is True
        # d is completed, so only a, b, c are pending = 3
        assert result["data"]["pending_before"] == 3

    def test_pending_before_excludes_already_skipped_roles(
        self, tmp_path: Path
    ) -> None:
        """pending_before must not count roles already in terminal states."""
        # 3 roles: a, b->a, c(already skipped)
        # pending_before should be 2 (a, b)
        plan_path = _finalized_plan_file(
            tmp_path,
            _role("a"),
            _role("b", deps=["a"]),
            _role("c"),
        )
        _set_role_status(plan_path, 2, "skipped")

        result = cascade(plan_path, 0)

        assert result["ok"] is True
        assert result["data"]["pending_before"] == 2

    def test_cascade_no_dependents_no_abort(self, tmp_path: Path) -> None:
        """When no dependents exist, cascade skips 0 roles — no abort."""
        plan_path = _finalized_plan_file(
            tmp_path,
            _role("a"),
            _role("b"),
            _role("c"),
        )
        result = cascade(plan_path, 0)

        assert result["ok"] is True
        assert result["data"].get("abort", False) is False

    def test_abort_flag_present_in_data_even_when_false(
        self, tmp_path: Path
    ) -> None:
        """Result data must always carry an 'abort' key (True or False)."""
        plan_path = _finalized_plan_file(
            tmp_path,
            _role("a"),
            _role("b"),
        )
        result = cascade(plan_path, 0)

        assert result["ok"] is True
        assert "abort" in result["data"]
