"""Tests for Someday filtering logic."""

from __future__ import annotations

from unittest.mock import patch

from things3_blade_mcp.someday import (
    augment_someday_tasks,
    filter_someday_tasks,
    get_someday_context,
)


class TestSomedayContext:
    @patch("things3_blade_mcp.someday.things")
    def test_builds_context(self, mock_things):
        mock_things.projects.return_value = [
            {"uuid": "someday-proj-1"},
            {"uuid": "someday-proj-2"},
        ]
        # Map each project call to its headings by matching the project kwarg
        def tasks_side_effect(**kwargs):
            proj = kwargs.get("project")
            if proj == "someday-proj-1":
                return [{"uuid": "heading-1"}]
            elif proj == "someday-proj-2":
                return [{"uuid": "heading-2"}, {"uuid": "heading-3"}]
            return []

        mock_things.tasks.side_effect = tasks_side_effect

        project_ids, heading_map = get_someday_context()
        assert project_ids == {"someday-proj-1", "someday-proj-2"}
        assert heading_map == {
            "heading-1": "someday-proj-1",
            "heading-2": "someday-proj-2",
            "heading-3": "someday-proj-2",
        }

    @patch("things3_blade_mcp.someday.things")
    def test_empty_context(self, mock_things):
        mock_things.projects.return_value = []
        project_ids, heading_map = get_someday_context()
        assert project_ids == set()
        assert heading_map == {}


class TestFilterSomedayTasks:
    def test_filters_direct_someday_project_tasks(self):
        ctx = ({"someday-proj"}, {})
        todos = [
            {"uuid": "1", "project": "someday-proj", "heading": None},
            {"uuid": "2", "project": "active-proj", "heading": None},
            {"uuid": "3", "project": None, "heading": None},
        ]
        result = filter_someday_tasks(todos, ctx)
        assert [t["uuid"] for t in result] == ["2", "3"]

    def test_filters_heading_inherited_someday(self):
        ctx = ({"someday-proj"}, {"heading-in-someday": "someday-proj"})
        todos = [
            {"uuid": "1", "heading": "heading-in-someday"},  # No project, but heading maps
            {"uuid": "2", "heading": "other-heading"},
        ]
        result = filter_someday_tasks(todos, ctx)
        assert [t["uuid"] for t in result] == ["2"]

    def test_no_filter_when_no_someday_projects(self):
        ctx = (set(), {})
        todos = [{"uuid": "1", "project": None, "heading": None}]
        result = filter_someday_tasks(todos, ctx)
        assert len(result) == 1


class TestAugmentSomedayTasks:
    @patch("things3_blade_mcp.someday.things")
    def test_adds_anytime_tasks_from_someday_projects(self, mock_things):
        ctx = ({"someday-proj"}, {})
        mock_things.anytime.return_value = [
            {"uuid": "anytime-1", "project": "someday-proj", "heading": None},
            {"uuid": "anytime-2", "project": "regular-proj", "heading": None},
        ]
        existing = [{"uuid": "already-someday", "project": None, "heading": None}]
        result = augment_someday_tasks(existing, ctx)
        uuids = [t["uuid"] for t in result]
        assert "already-someday" in uuids
        assert "anytime-1" in uuids
        assert "anytime-2" not in uuids

    @patch("things3_blade_mcp.someday.things")
    def test_deduplicates(self, mock_things):
        ctx = ({"someday-proj"}, {})
        mock_things.anytime.return_value = [
            {"uuid": "dup", "project": "someday-proj", "heading": None},
        ]
        existing = [{"uuid": "dup", "project": "someday-proj", "heading": None}]
        result = augment_someday_tasks(existing, ctx)
        assert len(result) == 1
