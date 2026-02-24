"""Tests for cli.envelope."""

from __future__ import annotations

import json

import pytest

from cli.envelope import err, ok, render


class TestOk:
    def test_ok_structure(self) -> None:
        result = ok({"id": "123"})
        assert result["ok"] is True
        assert result["data"] == {"id": "123"}

    def test_ok_with_none_data(self) -> None:
        result = ok(None)
        assert result["ok"] is True
        assert result["data"] is None

    def test_ok_with_list_data(self) -> None:
        result = ok([1, 2, 3])
        assert result["ok"] is True
        assert result["data"] == [1, 2, 3]

    def test_ok_with_empty_dict(self) -> None:
        result = ok({})
        assert result["ok"] is True
        assert result["data"] == {}

    def test_ok_no_error_key(self) -> None:
        result = ok({"x": 1})
        assert "error" not in result
        assert "message" not in result


class TestErr:
    def test_err_structure(self) -> None:
        result = err("STORE_NOT_FOUND", "Record not found.")
        assert result["ok"] is False
        assert result["error"] == "STORE_NOT_FOUND"
        assert result["message"] == "Record not found."

    def test_err_upper_snake_case_code(self) -> None:
        result = err("MODULE_CONDITION", "Something went wrong.")
        assert result["error"] == "MODULE_CONDITION"

    def test_err_no_data_key(self) -> None:
        result = err("X_Y", "msg")
        assert "data" not in result

    def test_err_ok_is_false_bool(self) -> None:
        result = err("X_Y", "msg")
        assert result["ok"] is False  # explicitly False, not just falsy


class TestRender:
    def test_render_ok_envelope(self) -> None:
        envelope = ok({"id": "abc"})
        rendered = render(envelope)
        parsed = json.loads(rendered)
        assert parsed == envelope

    def test_render_err_envelope(self) -> None:
        envelope = err("STORE_MISSING", "Not found.")
        rendered = render(envelope)
        parsed = json.loads(rendered)
        assert parsed == envelope

    def test_render_compact(self) -> None:
        envelope = ok({"a": 1})
        rendered = render(envelope)
        # Compact JSON: no spaces after separators
        assert ": " not in rendered
        assert ", " not in rendered

    def test_render_returns_string(self) -> None:
        assert isinstance(render(ok({})), str)

    def test_render_valid_json(self) -> None:
        rendered = render(err("A_B", "test"))
        # Should not raise
        json.loads(rendered)
