"""Tests for MCP server tool functions.

FastMCP wraps @mcp.tool functions as FunctionTool objects.
We call .fn to access the underlying function directly.
"""

from __future__ import annotations

from unittest.mock import patch

from things3_blade_mcp.server import (
    get_inbox,
    get_random_inbox,
    get_summary,
    get_today,
    json_export,
    search_todos,
    show_item,
)

# Unwrap FastMCP FunctionTool objects to get the actual functions
_get_inbox = get_inbox.fn
_get_today = get_today.fn
_get_random_inbox = get_random_inbox.fn
_search_todos = search_todos.fn
_show_item = show_item.fn
_get_summary = get_summary.fn
_json_export = json_export.fn


class TestListViewTools:
    @patch("things3_blade_mcp.server.things")
    def test_get_inbox_concise(self, mock_things):
        mock_things.inbox.return_value = [
            {"uuid": "aaa-bbb", "title": "Task 1", "status": "incomplete"},
            {"uuid": "ccc-ddd", "title": "Task 2", "status": "incomplete"},
        ]
        mock_things.projects.return_value = []
        result = _get_inbox(concise=True, limit=10)
        assert "Task 1" in result
        assert "Task 2" in result

    @patch("things3_blade_mcp.server.things")
    def test_get_inbox_empty(self, mock_things):
        mock_things.inbox.return_value = []
        mock_things.projects.return_value = []
        result = _get_inbox(concise=True, limit=10)
        assert "No items found" in result

    @patch("things3_blade_mcp.server.things")
    def test_get_inbox_respects_limit(self, mock_things):
        mock_things.inbox.return_value = [
            {"uuid": f"id-{i}", "title": f"Task {i}", "status": "incomplete"}
            for i in range(50)
        ]
        mock_things.projects.return_value = []
        result = _get_inbox(concise=True, limit=5)
        assert "45 more" in result

    @patch("things3_blade_mcp.server.get_someday_context")
    @patch("things3_blade_mcp.server.things")
    def test_get_today_filters_someday(self, mock_things, mock_ctx):
        mock_ctx.return_value = ({"someday-proj"}, {})
        mock_things.today.return_value = [
            {"uuid": "1", "title": "Active", "status": "incomplete",
             "project": "regular", "heading": None},
            {"uuid": "2", "title": "Hidden", "status": "incomplete",
             "project": "someday-proj", "heading": None},
        ]
        mock_things.projects.return_value = []
        result = _get_today(concise=True, limit=10)
        assert "Active" in result
        assert "Hidden" not in result


class TestRandomSamplingTools:
    @patch("things3_blade_mcp.server.things")
    def test_get_random_inbox(self, mock_things):
        mock_things.inbox.return_value = [
            {"uuid": f"id-{i}", "title": f"Task {i}", "status": "incomplete"}
            for i in range(20)
        ]
        mock_things.projects.return_value = []
        result = _get_random_inbox(count=3)
        assert "Random 3 of 20 inbox items:" in result
        # Should have exactly 3 task lines + 1 header line
        lines = [line for line in result.split("\n") if line.strip()]
        assert len(lines) == 4


class TestSearchTools:
    @patch("things3_blade_mcp.server.things")
    def test_search_todos(self, mock_things):
        mock_things.search.return_value = [
            {"uuid": "found-1", "title": "Meeting notes", "status": "incomplete"},
        ]
        mock_things.projects.return_value = []
        result = _search_todos(query="meeting", concise=True, limit=10)
        assert "Meeting notes" in result


class TestDetailTools:
    @patch("things3_blade_mcp.server.things")
    def test_show_item_todo(self, mock_things):
        mock_things.get.return_value = {
            "uuid": "abc-123",
            "type": "to-do",
            "title": "My Todo",
            "status": "incomplete",
            "notes": "Some notes",
        }
        mock_things.projects.return_value = []
        mock_things.areas.return_value = []
        result = _show_item(uuid="abc-123", include_details=True)
        assert "Title: My Todo" in result
        assert "Notes: Some notes" in result

    @patch("things3_blade_mcp.server.things")
    def test_show_item_not_found(self, mock_things):
        mock_things.get.return_value = None
        result = _show_item(uuid="nonexistent")
        assert "No item found" in result


class TestSummaryTool:
    @patch("things3_blade_mcp.server.get_someday_context", return_value=(set(), {}))
    @patch("things3_blade_mcp.server.things")
    def test_get_summary(self, mock_things, _mock_ctx):
        mock_things.inbox.return_value = [{"uuid": "1"}] * 5
        mock_things.today.return_value = [{"uuid": "2", "project": None, "heading": None}] * 3
        mock_things.upcoming.return_value = []
        mock_things.anytime.return_value = []
        mock_things.someday.return_value = []
        mock_things.projects.return_value = [{"uuid": "p"}] * 2
        mock_things.areas.return_value = [{"uuid": "a"}]
        mock_things.deadlines.return_value = []

        result = _get_summary()
        assert "Inbox: 5 items" in result
        assert "Today: 3 items" in result
        assert "Projects: 2 active" in result
        assert "Areas: 1" in result


class TestExportTool:
    @patch("things3_blade_mcp.server.things")
    def test_json_export(self, mock_things):
        mock_things.todos.return_value = [
            {"uuid": "aaa", "title": "Task 1", "status": "incomplete", "tags": ["work"]},
            {"uuid": "bbb", "title": "Task 2", "status": "incomplete"},
        ]
        result = _json_export(limit=50)
        import json
        data = json.loads(result)
        assert len(data) == 2
        assert data[0]["title"] == "Task 1"
        assert data[0]["tags"] == ["work"]
