"""Shared pytest fixtures for Things 3 MCP tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def mock_todo():
    """A representative todo dict as returned by things.py."""
    return {
        "uuid": "ABC12345-6789-DEF0-1234-567890ABCDEF",
        "type": "to-do",
        "title": "Buy groceries",
        "status": "incomplete",
        "start": "Anytime",
        "start_date": "2026-02-16",
        "deadline": "2026-02-20",
        "tags": ["errands", "personal"],
        "notes": "Milk, eggs, bread",
        "project": "PROJ1234-5678-90AB-CDEF-1234567890AB",
        "heading": None,
        "area": None,
        "checklist": [
            {"title": "Milk", "status": "incomplete"},
            {"title": "Eggs", "status": "completed"},
            {"title": "Bread", "status": "incomplete"},
        ],
        "stop_date": None,
        "created": "2026-02-10T10:00:00",
        "modified": "2026-02-15T14:30:00",
    }


@pytest.fixture
def mock_todo_minimal():
    """A minimal todo with only required fields."""
    return {
        "uuid": "MIN12345-6789-0000-0000-000000000000",
        "type": "to-do",
        "title": "Simple task",
        "status": "incomplete",
    }


@pytest.fixture
def mock_project():
    """A representative project dict."""
    return {
        "uuid": "PROJ1234-5678-90AB-CDEF-1234567890AB",
        "type": "project",
        "title": "Home Renovation",
        "status": "incomplete",
        "start": "Anytime",
        "deadline": "2026-06-01",
        "tags": ["home"],
        "notes": "Kitchen and bathroom",
        "area": "AREA1234-5678-90AB-CDEF-1234567890AB",
    }


@pytest.fixture
def mock_area():
    """A representative area dict."""
    return {
        "uuid": "AREA1234-5678-90AB-CDEF-1234567890AB",
        "title": "Personal",
        "tags": [],
    }


@pytest.fixture
def mock_tag():
    """A representative tag dict."""
    return {
        "uuid": "TAG12345-6789-0000-0000-000000000000",
        "title": "urgent",
        "shortcut": "u",
    }


@pytest.fixture
def mock_completed_todo():
    """A completed todo."""
    return {
        "uuid": "DONE1234-5678-90AB-CDEF-1234567890AB",
        "type": "to-do",
        "title": "Filed taxes",
        "status": "completed",
        "stop_date": "2026-02-10",
        "tags": ["finance"],
    }


@pytest.fixture
def mock_completed_todo_old_created():
    """Completed recently (recent stop_date) but created long ago.

    AUD-04-04: proves get_logbook filters on completion (stop) date, not
    creation date — this row must be reachable even though ``created`` predates
    the window by months.
    """
    return {
        "uuid": "OLD12345-6789-90AB-CDEF-1234567890AB",
        "type": "to-do",
        "title": "Long-running task",
        "status": "completed",
        "stop_date": "2026-06-13",
        "created": "2025-12-01T09:00:00",
        "tags": ["finance"],
    }


@pytest.fixture
def project_lookup():
    """Pre-built project lookup dict."""
    return {"PROJ1234-5678-90AB-CDEF-1234567890AB": "Home Renovation"}


@pytest.fixture
def area_lookup():
    """Pre-built area lookup dict."""
    return {"AREA1234-5678-90AB-CDEF-1234567890AB": "Personal"}
