"""Tests for MCP server tool functions.

FastMCP 3.x's ``@mcp.tool`` decorator preserves the underlying function as
the module attribute (attaches ``__fastmcp__`` metadata in place rather than
wrapping in a FunctionTool object). We call the functions directly.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from unittest.mock import patch

from things3_blade_mcp.server import (
    add_project as _add_project,
)
from things3_blade_mcp.server import (
    add_todo as _add_todo,
)
from things3_blade_mcp.server import (
    get_inbox as _get_inbox,
)
from things3_blade_mcp.server import (
    get_logbook as _get_logbook,
)
from things3_blade_mcp.server import (
    get_random_anytime as _get_random_anytime,
)
from things3_blade_mcp.server import (
    get_random_inbox as _get_random_inbox,
)
from things3_blade_mcp.server import (
    get_random_today as _get_random_today,
)
from things3_blade_mcp.server import (
    get_random_todos as _get_random_todos,
)
from things3_blade_mcp.server import (
    get_summary as _get_summary,
)
from things3_blade_mcp.server import (
    get_today as _get_today,
)
from things3_blade_mcp.server import (
    json_export as _json_export,
)
from things3_blade_mcp.server import (
    json_import as _json_import,
)
from things3_blade_mcp.server import (
    search_advanced as _search_advanced,
)
from things3_blade_mcp.server import (
    search_todos as _search_todos,
)
from things3_blade_mcp.server import (
    show_item as _show_item,
)
from things3_blade_mcp.server import (
    update_project as _update_project,
)
from things3_blade_mcp.server import (
    update_todo as _update_todo,
)

_W4_REQUIRED_META_KEYS = ("matched_total", "returned", "filtered_by", "redactions", "next_cursor", "latency_ms")


def _parse_meta(result: str) -> dict:
    """Extract trailing _meta JSON block from a tool return string."""
    m = re.search(r"\n\n_meta: (\{.*\})$", result)
    assert m is not None, f"No _meta block found in:\n{result}"
    return json.loads(m.group(1))


def _assert_meta_shape(meta: dict) -> None:
    """Assert the canonical _meta envelope shape for a W4-promoted tool."""
    for key in _W4_REQUIRED_META_KEYS:
        assert key in meta, f"missing _meta key: {key}"
    assert isinstance(meta["matched_total"], int)
    assert isinstance(meta["returned"], int)
    assert isinstance(meta["filtered_by"], list)
    assert isinstance(meta["redactions"], list)
    assert isinstance(meta["latency_ms"], int)


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
            {"uuid": f"id-{i}", "title": f"Task {i}", "status": "incomplete"} for i in range(50)
        ]
        mock_things.projects.return_value = []
        result = _get_inbox(concise=True, limit=5)
        assert "45 more" in result

    @patch("things3_blade_mcp.server.get_someday_context")
    @patch("things3_blade_mcp.server.things")
    def test_get_today_filters_someday(self, mock_things, mock_ctx):
        mock_ctx.return_value = ({"someday-proj"}, {})
        mock_things.today.return_value = [
            {"uuid": "1", "title": "Active", "status": "incomplete", "project": "regular", "heading": None},
            {"uuid": "2", "title": "Hidden", "status": "incomplete", "project": "someday-proj", "heading": None},
        ]
        mock_things.projects.return_value = []
        result = _get_today(concise=True, limit=10)
        assert "Active" in result
        assert "Hidden" not in result


class TestRandomSamplingTools:
    @patch("things3_blade_mcp.server.things")
    def test_get_random_inbox(self, mock_things):
        mock_things.inbox.return_value = [
            {"uuid": f"id-{i}", "title": f"Task {i}", "status": "incomplete"} for i in range(20)
        ]
        mock_things.projects.return_value = []
        result = _get_random_inbox(count=3)
        assert "Random 3 of 20 inbox items:" in result
        # DD-338 C W4: result now includes a trailing _meta envelope line.
        # Strip it before counting payload lines.
        payload = result.split("\n\n_meta: ", 1)[0]
        lines = [line for line in payload.split("\n") if line.strip()]
        # 3 task lines + 1 header line.
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


# ===========================================================================
# DD-338 C W4 — _meta envelope tests (6 W4-promoted tools)
# ===========================================================================


class TestW4GetRandomInbox:
    @patch("things3_blade_mcp.server.things")
    def test_meta_envelope_shape(self, mock_things):
        mock_things.inbox.return_value = [
            {"uuid": f"id-{i}", "title": f"Task {i}", "status": "incomplete"} for i in range(10)
        ]
        mock_things.projects.return_value = []
        result = _get_random_inbox(count=3)
        meta = _parse_meta(result)
        _assert_meta_shape(meta)
        assert meta["matched_total"] == 10
        assert meta["returned"] == 3

    @patch("things3_blade_mcp.server.things")
    def test_filtered_by_content(self, mock_things):
        mock_things.inbox.return_value = []
        mock_things.projects.return_value = []
        result = _get_random_inbox(count=7)
        meta = _parse_meta(result)
        assert "pool=inbox" in meta["filtered_by"]
        assert "count=7" in meta["filtered_by"]
        assert "sample=random" in meta["filtered_by"]
        assert meta["filtered_by"] == sorted(meta["filtered_by"])


class TestW4GetRandomToday:
    @patch("things3_blade_mcp.server.get_someday_context", return_value=(set(), {}))
    @patch("things3_blade_mcp.server.things")
    def test_meta_envelope_shape(self, mock_things, _mock_ctx):
        mock_things.today.return_value = [
            {"uuid": f"id-{i}", "title": f"T{i}", "status": "incomplete"} for i in range(8)
        ]
        mock_things.projects.return_value = []
        result = _get_random_today(count=2)
        meta = _parse_meta(result)
        _assert_meta_shape(meta)
        assert meta["returned"] == 2

    @patch("things3_blade_mcp.server.get_someday_context", return_value=(set(), {}))
    @patch("things3_blade_mcp.server.things")
    def test_filtered_by_content(self, mock_things, _mock_ctx):
        mock_things.today.return_value = []
        mock_things.projects.return_value = []
        result = _get_random_today(count=4)
        meta = _parse_meta(result)
        assert "pool=today" in meta["filtered_by"]
        assert "filter=someday_excluded" in meta["filtered_by"]
        assert "count=4" in meta["filtered_by"]
        assert "sample=random" in meta["filtered_by"]


class TestW4GetRandomAnytime:
    @patch("things3_blade_mcp.server.get_someday_context", return_value=(set(), {}))
    @patch("things3_blade_mcp.server.things")
    def test_meta_envelope_shape(self, mock_things, _mock_ctx):
        mock_things.anytime.return_value = [
            {"uuid": f"id-{i}", "title": f"A{i}", "status": "incomplete"} for i in range(6)
        ]
        mock_things.projects.return_value = []
        result = _get_random_anytime(count=3)
        meta = _parse_meta(result)
        _assert_meta_shape(meta)
        assert meta["matched_total"] == 6

    @patch("things3_blade_mcp.server.get_someday_context", return_value=(set(), {}))
    @patch("things3_blade_mcp.server.things")
    def test_filtered_by_content(self, mock_things, _mock_ctx):
        mock_things.anytime.return_value = []
        mock_things.projects.return_value = []
        result = _get_random_anytime(count=2)
        meta = _parse_meta(result)
        assert "pool=anytime" in meta["filtered_by"]
        assert "filter=someday_excluded" in meta["filtered_by"]


class TestW4GetRandomTodos:
    @patch("things3_blade_mcp.server.things")
    def test_meta_envelope_shape(self, mock_things):
        mock_things.todos.return_value = [
            {"uuid": f"id-{i}", "title": f"X{i}", "status": "incomplete"} for i in range(5)
        ]
        mock_things.projects.return_value = []
        result = _get_random_todos(count=2)
        meta = _parse_meta(result)
        _assert_meta_shape(meta)

    @patch("things3_blade_mcp.server.things")
    def test_filtered_by_with_project(self, mock_things):
        mock_things.todos.return_value = []
        mock_things.projects.return_value = []
        result = _get_random_todos(project_uuid="proj-42", count=3)
        meta = _parse_meta(result)
        assert "count=3" in meta["filtered_by"]
        assert "sample=random" in meta["filtered_by"]
        assert "project_uuid=proj-42" in meta["filtered_by"]

    @patch("things3_blade_mcp.server.things")
    def test_filtered_by_without_project(self, mock_things):
        mock_things.todos.return_value = []
        mock_things.projects.return_value = []
        result = _get_random_todos(count=5)
        meta = _parse_meta(result)
        assert "count=5" in meta["filtered_by"]
        assert "sample=random" in meta["filtered_by"]
        assert not any(f.startswith("project_uuid=") for f in meta["filtered_by"])


class TestW4SearchTodos:
    @patch("things3_blade_mcp.server.things")
    def test_meta_envelope_shape(self, mock_things):
        mock_things.search.return_value = [
            {"uuid": "found-1", "title": "Meeting notes", "status": "incomplete"},
        ]
        mock_things.projects.return_value = []
        result = _search_todos(query="meeting", limit=10)
        meta = _parse_meta(result)
        _assert_meta_shape(meta)

    @patch("things3_blade_mcp.server.things")
    def test_filtered_by_content_verbatim_query(self, mock_things):
        # OQ-7: query verbatim per mastodon precedent.
        mock_things.search.return_value = []
        result = _search_todos(query="renew car rego", limit=10)
        meta = _parse_meta(result)
        assert "query=renew car rego" in meta["filtered_by"]
        assert "limit=10" in meta["filtered_by"]

    @patch("things3_blade_mcp.server.things")
    def test_matched_vs_returned(self, mock_things):
        mock_things.search.return_value = [
            {"uuid": f"id-{i}", "title": f"T{i}", "status": "incomplete"} for i in range(25)
        ]
        mock_things.projects.return_value = []
        result = _search_todos(query="x", limit=10)
        meta = _parse_meta(result)
        assert meta["matched_total"] == 25
        assert meta["returned"] == 10


class TestW4SearchAdvanced:
    @patch("things3_blade_mcp.server.things")
    def test_meta_envelope_shape(self, mock_things):
        mock_things.todos.return_value = []
        result = _search_advanced(status="incomplete", limit=10)
        meta = _parse_meta(result)
        _assert_meta_shape(meta)

    @patch("things3_blade_mcp.server.things")
    def test_filtered_by_subset(self, mock_things):
        mock_things.todos.return_value = []
        result = _search_advanced(status="incomplete", tag="urgent", limit=20)
        meta = _parse_meta(result)
        assert "status=incomplete" in meta["filtered_by"]
        assert "tag=urgent" in meta["filtered_by"]
        assert "limit=20" in meta["filtered_by"]
        # Other filters not set → not in filtered_by
        assert not any(f.startswith("start_date=") for f in meta["filtered_by"])
        assert not any(f.startswith("deadline=") for f in meta["filtered_by"])

    @patch("things3_blade_mcp.server.things")
    def test_matched_vs_returned(self, mock_things):
        mock_things.todos.return_value = [
            {"uuid": f"id-{i}", "title": f"T{i}", "status": "incomplete"} for i in range(15)
        ]
        mock_things.projects.return_value = []
        result = _search_advanced(status="incomplete", limit=5)
        meta = _parse_meta(result)
        assert meta["matched_total"] == 15
        assert meta["returned"] == 5


class TestGetLogbook:
    """AUD-04-04 regression — get_logbook queries the Logbook by completion
    (stop) date over the requested window, supports all advertised periods
    (d/w/m/y), newest-completed first.

    The pre-fix code called ``things.last(period, status="completed")``, which
    filters by CREATION date (so a task created long ago but completed yesterday
    was dropped) and raises ``ValueError`` for month suffixes ('1m'/'3m').  The
    fix queries ``things.completed(stop_date=">=<cutoff>")`` with a locally
    computed cutoff.
    """

    @patch("things3_blade_mcp.server.date")
    @patch("things3_blade_mcp.server.things")
    def test_logbook_queries_completed_by_stop_date(self, mock_things, mock_date, mock_completed_todo):
        mock_date.today.return_value = _dt.date(2026, 6, 14)
        mock_things.completed.return_value = [mock_completed_todo]
        result = _get_logbook(period="7d", concise=True, limit=10)
        expected = (_dt.date(2026, 6, 14) - _dt.timedelta(days=7)).isoformat()
        mock_things.completed.assert_called_once_with(stop_date=f">={expected}")
        mock_things.last.assert_not_called()
        assert "Filed taxes" in result

    @patch("things3_blade_mcp.server.date")
    @patch("things3_blade_mcp.server.things")
    def test_logbook_newest_completion_first(self, mock_things, mock_date):
        mock_date.today.return_value = _dt.date(2026, 6, 14)
        older = {"uuid": "A", "type": "to-do", "title": "Older done", "status": "completed", "stop_date": "2026-06-08"}
        newer = {"uuid": "B", "type": "to-do", "title": "Newer done", "status": "completed", "stop_date": "2026-06-13"}
        # Feed in ascending order; the tool must re-sort to newest-completion first.
        mock_things.completed.return_value = [older, newer]
        result = _get_logbook(period="2w", concise=True, limit=10)
        assert result.index("Newer done") < result.index("Older done")

    @patch("things3_blade_mcp.server.date")
    @patch("things3_blade_mcp.server.things")
    def test_logbook_includes_old_created_recent_stop(self, mock_things, mock_date, mock_completed_todo_old_created):
        # The residual AUD-04-04 defect: a row created months ago but completed
        # inside the window must be reachable — proves the created→stop axis fix.
        mock_date.today.return_value = _dt.date(2026, 6, 14)
        mock_things.completed.return_value = [mock_completed_todo_old_created]
        result = _get_logbook(period="7d")
        expected = (_dt.date(2026, 6, 14) - _dt.timedelta(days=7)).isoformat()
        mock_things.completed.assert_called_once_with(stop_date=f">={expected}")
        mock_things.last.assert_not_called()
        assert "Long-running task" in result

    @patch("things3_blade_mcp.server.date")
    @patch("things3_blade_mcp.server.things")
    def test_logbook_month_periods_do_not_raise(self, mock_things, mock_date):
        # '1m' / '3m' raised ValueError pre-fix (validate_offset rejects month
        # suffixes); the local cutoff computation must accept them.
        mock_date.today.return_value = _dt.date(2026, 6, 14)
        mock_things.completed.return_value = []

        _get_logbook(period="1m")
        expected_1m = (_dt.date(2026, 6, 14) - _dt.timedelta(days=30)).isoformat()
        mock_things.completed.assert_called_once_with(stop_date=f">={expected_1m}")

        mock_things.completed.reset_mock()
        _get_logbook(period="3m")
        expected_3m = (_dt.date(2026, 6, 14) - _dt.timedelta(days=90)).isoformat()
        mock_things.completed.assert_called_once_with(stop_date=f">={expected_3m}")

    @patch("things3_blade_mcp.server.date")
    @patch("things3_blade_mcp.server.things")
    def test_logbook_empty_period(self, mock_things, mock_date):
        mock_date.today.return_value = _dt.date(2026, 6, 14)
        mock_things.completed.return_value = []
        result = _get_logbook(period="7d")
        assert "No items found" in result


class TestWriteGate:
    """AUD-04-18 — mutating tools refuse unless THINGS_WRITE_ENABLED=true."""

    @patch("things3_blade_mcp.server.applescript")
    @patch("things3_blade_mcp.server.things")
    def test_add_todo_refused_when_gate_off(self, mock_things, mock_applescript, monkeypatch):
        monkeypatch.delenv("THINGS_WRITE_ENABLED", raising=False)
        result = _add_todo(title="New task")
        assert "Write operations are disabled" in result
        mock_applescript.add_todo.assert_not_called()

    @patch("things3_blade_mcp.server.applescript")
    def test_add_todo_refused_when_gate_false(self, mock_applescript, monkeypatch):
        monkeypatch.setenv("THINGS_WRITE_ENABLED", "false")
        result = _add_todo(title="New task")
        assert "Write operations are disabled" in result
        mock_applescript.add_todo.assert_not_called()

    @patch("things3_blade_mcp.server.applescript")
    def test_add_project_refused_when_gate_off(self, mock_applescript, monkeypatch):
        monkeypatch.delenv("THINGS_WRITE_ENABLED", raising=False)
        result = _add_project(title="New project")
        assert "Write operations are disabled" in result
        mock_applescript.add_project.assert_not_called()

    @patch("things3_blade_mcp.server.applescript")
    def test_update_todo_refused_when_gate_off(self, mock_applescript, monkeypatch):
        monkeypatch.delenv("THINGS_WRITE_ENABLED", raising=False)
        result = _update_todo(todo_id="abc-123", completed=True)
        assert "Write operations are disabled" in result
        mock_applescript.update_todo.assert_not_called()

    @patch("things3_blade_mcp.server.applescript")
    def test_update_project_refused_when_gate_off(self, mock_applescript, monkeypatch):
        monkeypatch.delenv("THINGS_WRITE_ENABLED", raising=False)
        result = _update_project(project_id="proj-123", title="Renamed")
        assert "Write operations are disabled" in result
        mock_applescript.update_project.assert_not_called()

    @patch("things3_blade_mcp.server.url_scheme")
    def test_json_import_refused_when_gate_off(self, mock_url_scheme, monkeypatch):
        monkeypatch.delenv("THINGS_WRITE_ENABLED", raising=False)
        result = _json_import(data='[{"type":"to-do","attributes":{"title":"x"}}]', confirm=True)
        assert "Write operations are disabled" in result
        mock_url_scheme.json_import.assert_not_called()

    @patch("things3_blade_mcp.server.things")
    def test_json_export_remains_ungated_read(self, mock_things, monkeypatch):
        monkeypatch.delenv("THINGS_WRITE_ENABLED", raising=False)
        mock_things.todos.return_value = []
        result = _json_export()
        assert "Write operations are disabled" not in result

    @patch("things3_blade_mcp.server.applescript")
    @patch("things3_blade_mcp.server.things")
    def test_add_todo_works_when_gate_on(self, mock_things, mock_applescript, monkeypatch):
        monkeypatch.setenv("THINGS_WRITE_ENABLED", "true")
        mock_things.search.return_value = []
        mock_applescript.add_todo.return_value = "NEW-UUID-123"
        result = _add_todo(title="New task")
        assert "Created todo 'New task'" in result
        mock_applescript.add_todo.assert_called_once()

    @patch("things3_blade_mcp.server.applescript")
    def test_update_todo_complete_works_when_gate_on(self, mock_applescript, monkeypatch):
        monkeypatch.setenv("THINGS_WRITE_ENABLED", "true")
        mock_applescript.update_todo.return_value = "OK"
        result = _update_todo(todo_id="abc-123", completed=True)
        assert "Updated todo abc-123" in result
        mock_applescript.update_todo.assert_called_once()


class TestConfirmGate:
    """AUD-04-18 — destructive/bulk operations additionally require confirm=true."""

    @patch("things3_blade_mcp.server.applescript")
    def test_cancel_todo_requires_confirm(self, mock_applescript, monkeypatch):
        monkeypatch.setenv("THINGS_WRITE_ENABLED", "true")
        result = _update_todo(todo_id="abc-123", canceled=True)
        assert "requires explicit confirmation" in result
        mock_applescript.update_todo.assert_not_called()

    @patch("things3_blade_mcp.server.applescript")
    def test_cancel_todo_with_confirm_proceeds(self, mock_applescript, monkeypatch):
        monkeypatch.setenv("THINGS_WRITE_ENABLED", "true")
        mock_applescript.update_todo.return_value = "OK"
        result = _update_todo(todo_id="abc-123", canceled=True, confirm=True)
        assert "Updated todo abc-123" in result
        mock_applescript.update_todo.assert_called_once()

    @patch("things3_blade_mcp.server.applescript")
    def test_non_cancel_update_needs_no_confirm(self, mock_applescript, monkeypatch):
        monkeypatch.setenv("THINGS_WRITE_ENABLED", "true")
        mock_applescript.update_todo.return_value = "OK"
        result = _update_todo(todo_id="abc-123", when="tomorrow")
        assert "Updated todo abc-123" in result

    @patch("things3_blade_mcp.server.applescript")
    def test_cancel_project_requires_confirm(self, mock_applescript, monkeypatch):
        monkeypatch.setenv("THINGS_WRITE_ENABLED", "true")
        result = _update_project(project_id="proj-123", canceled=True)
        assert "requires explicit confirmation" in result
        mock_applescript.update_project.assert_not_called()

    @patch("things3_blade_mcp.server.url_scheme")
    def test_json_import_requires_confirm(self, mock_url_scheme, monkeypatch):
        monkeypatch.setenv("THINGS_WRITE_ENABLED", "true")
        result = _json_import(data='[{"type":"to-do","attributes":{"title":"x"}}]')
        assert "requires explicit confirmation" in result
        mock_url_scheme.json_import.assert_not_called()

    @patch("things3_blade_mcp.server.url_scheme")
    def test_json_import_with_confirm_proceeds(self, mock_url_scheme, monkeypatch):
        monkeypatch.setenv("THINGS_WRITE_ENABLED", "true")
        result = _json_import(data='[{"type":"to-do","attributes":{"title":"x"}}]', confirm=True)
        assert "Imported 1 items" in result
        mock_url_scheme.json_import.assert_called_once()
