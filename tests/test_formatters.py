"""Tests for token-efficient formatters."""

from __future__ import annotations

import json

from things3_blade_mcp.formatters import (
    append_meta,
    build_area_lookup,
    build_project_lookup,
    format_area_concise,
    format_meta,
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


# ---------------------------------------------------------------------------
# DD-338 C W4 — _meta envelope helper tests
# ---------------------------------------------------------------------------


class TestFormatMeta:
    """Verify the canonical _meta JSON-tail wire shape (parity with mastodon-blade-mcp)."""

    def test_format_meta_required_keys(self):
        out = format_meta(
            matched_total=10,
            returned=3,
            filtered_by=["pool=inbox", "count=3", "sample=random"],
            latency_ms=42,
        )
        assert out.startswith("_meta: ")
        meta = json.loads(out[len("_meta: ") :])
        for key in ("matched_total", "returned", "filtered_by", "redactions", "next_cursor", "latency_ms"):
            assert key in meta
        assert meta["matched_total"] == 10
        assert meta["returned"] == 3
        assert meta["filtered_by"] == ["pool=inbox", "count=3", "sample=random"]
        assert meta["redactions"] == []
        assert meta["next_cursor"] is None
        assert meta["latency_ms"] == 42

    def test_format_meta_single_line_json(self):
        """Assembler regex `\\n\\n_meta: (\\{.*\\})$` requires single-line JSON."""
        out = format_meta(
            matched_total=5,
            returned=5,
            filtered_by=["limit=5"],
            redactions=["scope=personal_unconfigured"],
            next_cursor="next-99",
            latency_ms=12,
            error_notes=["partial"],
        )
        assert "\n" not in out

    def test_format_meta_error_notes_optional(self):
        # error_notes omitted when None/empty.
        out = format_meta(matched_total=0, returned=0, filtered_by=[], latency_ms=0)
        meta = json.loads(out[len("_meta: ") :])
        assert "error_notes" not in meta

    def test_format_meta_error_notes_included(self):
        out = format_meta(
            matched_total=1,
            returned=1,
            filtered_by=[],
            latency_ms=0,
            error_notes=["partial_success"],
        )
        meta = json.loads(out[len("_meta: ") :])
        assert meta["error_notes"] == ["partial_success"]


class TestAppendMeta:
    """Verify the canonical `\\n\\n` separator between payload and _meta block."""

    def test_append_meta_separator(self):
        body = "Random 3 of 10 inbox items:\n- t1\n- t2\n- t3"
        meta = format_meta(matched_total=10, returned=3, filtered_by=[], latency_ms=1)
        out = append_meta(body, meta)
        assert out == body + "\n\n" + meta
        assert "\n\n_meta: " in out

    def test_assembler_regex_matches(self):
        import re

        body = "payload body"
        meta = format_meta(matched_total=1, returned=1, filtered_by=["k=v"], latency_ms=0)
        out = append_meta(body, meta)
        m = re.search(r"\n\n_meta: (\{.*\})$", out)
        assert m is not None
        parsed = json.loads(m.group(1))
        assert parsed["matched_total"] == 1
