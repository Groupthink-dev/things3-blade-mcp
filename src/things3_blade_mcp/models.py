"""Shared constants, type helpers, and write/confirm gates for Things 3 MCP server."""

from __future__ import annotations

import os

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


# ---------------------------------------------------------------------------
# Write / confirm gates (AUD-04-18 — sibling-blade *_WRITE_ENABLED convention)
# ---------------------------------------------------------------------------


def is_write_enabled() -> bool:
    """Check if write operations are enabled via env var."""
    return os.environ.get("THINGS_WRITE_ENABLED", "").lower() == "true"


def check_write_gate() -> str | None:
    """Return an error message if writes are disabled, else None."""
    if not is_write_enabled():
        return "Error: Write operations are disabled. Set THINGS_WRITE_ENABLED=true to enable."
    return None


def check_confirm_gate(confirm: bool, action: str) -> str | None:
    """Return an error message if confirm is not set, else None.

    Destructive and bulk write operations require explicit confirm=true.
    """
    if not confirm:
        return (
            f"Error: {action} requires explicit confirmation. "
            "Set confirm=true to proceed. This is a safety gate for destructive/bulk operations."
        )
    return None
