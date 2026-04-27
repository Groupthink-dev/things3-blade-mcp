"""Shared constants and type helpers for Things 3 MCP server."""

from __future__ import annotations

# Fields included in concise (one-line) output — everything else is detail-only
CONCISE_FIELDS = {"title", "uuid", "status", "start", "start_date", "deadline", "tags", "type"}

# Short UUID length for concise display
SHORT_UUID_LEN = 8

# Status icons for concise rendering
STATUS_ICONS = {
    "incomplete": "□",
    "completed": "✓",
    "canceled": "✗",
}

# Things 3 built-in list names (for show_item routing)
BUILTIN_LISTS = {
    "inbox",
    "today",
    "upcoming",
    "anytime",
    "someday",
    "logbook",
    "trash",
}

# Default limits
DEFAULT_LIMIT = 10
DEFAULT_SAMPLE_COUNT = 5
