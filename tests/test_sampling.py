"""Tests for random sampling helpers."""

from __future__ import annotations

from things3_blade_mcp.sampling import random_sample


class TestRandomSample:
    def test_sample_returns_subset(self):
        items = [{"uuid": str(i)} for i in range(20)]
        result = random_sample(items, 5)
        assert len(result) == 5
        # All results should be from original items
        result_uuids = {r["uuid"] for r in result}
        all_uuids = {str(i) for i in range(20)}
        assert result_uuids.issubset(all_uuids)

    def test_sample_returns_all_when_fewer(self):
        items = [{"uuid": str(i)} for i in range(3)]
        result = random_sample(items, 5)
        assert len(result) == 3

    def test_sample_zero_count(self):
        items = [{"uuid": "1"}]
        result = random_sample(items, 0)
        assert result == []

    def test_sample_negative_count(self):
        items = [{"uuid": "1"}]
        result = random_sample(items, -1)
        assert result == []

    def test_sample_empty_list(self):
        result = random_sample([], 5)
        assert result == []

    def test_sample_exact_count(self):
        items = [{"uuid": str(i)} for i in range(5)]
        result = random_sample(items, 5)
        assert len(result) == 5
