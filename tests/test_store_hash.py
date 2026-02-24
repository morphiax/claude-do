"""Tests for cli.store.hash."""

from __future__ import annotations

import pytest

from cli.store.hash import content_hash


class TestContentHash:
    def test_returns_hex_string(self) -> None:
        h = content_hash({"key": "value"})
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 produces 64 hex chars
        assert all(c in "0123456789abcdef" for c in h)

    def test_same_object_same_hash(self) -> None:
        obj = {"a": 1, "b": 2}
        assert content_hash(obj) == content_hash(obj)

    def test_different_key_order_same_hash(self) -> None:
        obj1 = {"a": 1, "b": 2}
        obj2 = {"b": 2, "a": 1}
        assert content_hash(obj1) == content_hash(obj2)

    def test_different_objects_different_hash(self) -> None:
        assert content_hash({"a": 1}) != content_hash({"a": 2})
        assert content_hash({"a": 1}) != content_hash({"b": 1})

    def test_nested_objects_order_independent(self) -> None:
        obj1 = {"outer": {"x": 1, "y": 2}, "z": 3}
        obj2 = {"z": 3, "outer": {"y": 2, "x": 1}}
        assert content_hash(obj1) == content_hash(obj2)

    def test_list_order_matters(self) -> None:
        # Lists are ordered — different order means different hash
        assert content_hash([1, 2, 3]) != content_hash([3, 2, 1])

    def test_empty_object(self) -> None:
        h = content_hash({})
        assert len(h) == 64

    def test_empty_list(self) -> None:
        h = content_hash([])
        assert len(h) == 64

    def test_string_value(self) -> None:
        h = content_hash("hello")
        assert len(h) == 64

    def test_nan_raises(self) -> None:
        import math
        with pytest.raises((ValueError, TypeError)):
            content_hash(math.nan)

    def test_deeply_nested(self) -> None:
        obj1 = {"a": {"b": {"c": {"d": 1, "e": 2}}}}
        obj2 = {"a": {"b": {"c": {"e": 2, "d": 1}}}}
        assert content_hash(obj1) == content_hash(obj2)
