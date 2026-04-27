"""Tests for token-efficient formatters."""

from __future__ import annotations

from things3_blade_mcp.formatters import (
    build_area_lookup,
    build_project_lookup,
    format_area_concise,
    format_project_concise,
    format_tag_concise,
    format_todo_concise,
    format_todo_detailed,
    format_todo_list,
)


class TestConciseFormatters:
    """Verify concise output is truly one-line-per-item and omits nulls."""

    def test_todo_concise_full(self, mock_todo, project_lookup):
        result = format_todo_concise(mock_todo, project_lookup)
        assert "\n" not in result
        assert "ABC12345" in result  # Short UUID
        assert "Buy groceries" in result
        assert "2026-02-16" in result  # start_date
        assert "deadline:2026-02-20" in result
        assert "#errands" in result
        assert "#personal" in result
        assert "in:Home Renovation" in result

    def test_todo_concise_minimal(self, mock_todo_minimal):
        result = format_todo_concise(mock_todo_minimal)
        assert "\n" not in result
        assert "Simple task" in result
        assert "MIN12345" in result
        # No deadline, tags, project — should not appear
        assert "deadline:" not in result
        assert "#" not in result
        assert "in:" not in result

    def test_completed_todo_concise(self, mock_completed_todo):
        result = format_todo_concise(mock_completed_todo)
        assert "✓" in result
        assert "Filed taxes" in result

    def test_project_concise(self, mock_project):
        result = format_project_concise(mock_project)
        assert "\n" not in result
        assert "Home Renovation" in result
        assert "PROJ1234" in result

    def test_project_concise_with_counts(self, mock_project):
        counts = {"PROJ1234-5678-90AB-CDEF-1234567890AB": {"open": 5, "done": 3}}
        result = format_project_concise(mock_project, counts)
        assert "open:5" in result
        assert "done:3" in result

    def test_area_concise(self, mock_area):
        result = format_area_concise(mock_area)
        assert "Personal" in result
        assert "AREA1234" in result

    def test_tag_concise(self, mock_tag):
        result = format_tag_concise(mock_tag)
        assert "#urgent" in result
        assert "shortcut:u" in result


class TestDetailedFormatters:
    """Verify detailed output includes all relevant fields."""

    def test_todo_detailed_full(self, mock_todo, project_lookup, area_lookup):
        result = format_todo_detailed(mock_todo, project_lookup, area_lookup)
        assert "Title: Buy groceries" in result
        assert "UUID: ABC12345" in result
        assert "Status: incomplete" in result
        assert "Scheduled: 2026-02-16" in result
        assert "Deadline: 2026-02-20" in result
        assert "Project: Home Renovation" in result
        assert "Tags: errands, personal" in result
        assert "Notes: Milk, eggs, bread" in result
        assert "Checklist:" in result
        assert "□ Milk" in result
        assert "✓ Eggs" in result

    def test_todo_detailed_minimal(self, mock_todo_minimal):
        result = format_todo_detailed(mock_todo_minimal)
        assert "Title: Simple task" in result
        # Should NOT have empty sections
        assert "Notes:" not in result
        assert "Tags:" not in result
        assert "Deadline:" not in result
        assert "Checklist:" not in result


class TestListFormatters:
    """Verify list formatting respects limits and concise mode."""

    def test_list_respects_limit(self, mock_todo):
        todos = [mock_todo] * 25
        result = format_todo_list(todos, concise=True, limit=10)
        lines = [line for line in result.split("\n") if line.strip()]
        # 10 items + 1 "more" line
        assert len(lines) == 11
        assert "15 more" in result

    def test_list_empty(self):
        result = format_todo_list([], concise=True, limit=10)
        assert "No items found" in result

    def test_list_under_limit(self, mock_todo):
        todos = [mock_todo] * 3
        result = format_todo_list(todos, concise=True, limit=10)
        assert "more" not in result


class TestLookupBuilders:
    """Verify batch lookup construction."""

    def test_build_project_lookup(self):
        projects = [
            {"uuid": "aaa", "title": "Project A"},
            {"uuid": "bbb", "title": "Project B"},
            {"uuid": "ccc"},  # Missing title — should be skipped
        ]
        lookup = build_project_lookup(projects)
        assert lookup == {"aaa": "Project A", "bbb": "Project B"}

    def test_build_area_lookup(self):
        areas = [
            {"uuid": "x", "title": "Work"},
            {"uuid": "y", "title": "Personal"},
        ]
        lookup = build_area_lookup(areas)
        assert lookup == {"x": "Work", "y": "Personal"}
