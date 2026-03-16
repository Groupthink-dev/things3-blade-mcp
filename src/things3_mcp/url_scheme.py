"""Things 3 URL scheme builder — fallback for writes when AppleScript is unavailable.

Uses things:/// URLs via macOS `open` command.
Auth token is auto-detected via things.token() or THINGS_AUTH_TOKEN env var.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from urllib.parse import quote, urlencode

import things

logger = logging.getLogger(__name__)


def _get_auth_token() -> str | None:
    """Get Things URL scheme auth token (env var first, then things.py)."""
    token = os.environ.get("THINGS_AUTH_TOKEN")
    if token:
        return token
    try:
        return things.token()
    except Exception:
        return None


def _execute_url(url: str) -> None:
    """Open a things:/// URL in the background."""
    try:
        # Use osascript to open in background (no focus steal)
        subprocess.run(
            ["osascript", "-e", f'open location "{url}"'],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        # Fallback to plain open
        subprocess.run(["open", url], capture_output=True, text=True, timeout=10)


def construct_url(command: str, params: dict) -> str:
    """Build a things:/// URL from command and parameters."""
    # Remove None values
    clean = {k: v for k, v in params.items() if v is not None}

    # Handle list parameters (join with comma or newline as appropriate)
    for key in ("tags", "add-tags"):
        if key in clean and isinstance(clean[key], list):
            clean[key] = ",".join(clean[key])

    for key in ("checklist-items", "prepend-checklist-items", "append-checklist-items", "to-dos"):
        if key in clean and isinstance(clean[key], list):
            clean[key] = "\n".join(clean[key])

    # Add auth token for update commands
    if command in ("update", "update-project") and "auth-token" not in clean:
        token = _get_auth_token()
        if token:
            clean["auth-token"] = token
        else:
            logger.warning("No auth token available for %s — update may fail", command)

    query = urlencode(clean, quote_via=lambda s, *_a, **_kw: quote(s, safe=""))
    return f"things:///{command}?{query}"


def add_todo_url(
    title: str,
    notes: str | None = None,
    when: str | None = None,
    deadline: str | None = None,
    tags: list[str] | None = None,
    checklist_items: list[str] | None = None,
    list_id: str | None = None,
    list_title: str | None = None,
    heading: str | None = None,
    heading_id: str | None = None,
    reveal: bool = False,
) -> str:
    """Create a todo via URL scheme. Returns the constructed URL."""
    params = {
        "title": title,
        "notes": notes,
        "when": when,
        "deadline": deadline,
        "tags": tags,
        "checklist-items": checklist_items,
        "list-id": list_id,
        "list": list_title,
        "heading-id": heading_id,
        "heading": heading,
        "reveal": str(reveal).lower() if reveal else None,
    }
    url = construct_url("add", params)
    _execute_url(url)
    return url


def add_project_url(
    title: str,
    notes: str | None = None,
    when: str | None = None,
    deadline: str | None = None,
    tags: list[str] | None = None,
    area_id: str | None = None,
    area_title: str | None = None,
    todos: list[str] | None = None,
    reveal: bool = False,
) -> str:
    """Create a project via URL scheme."""
    params = {
        "title": title,
        "notes": notes,
        "when": when,
        "deadline": deadline,
        "tags": tags,
        "area-id": area_id,
        "area": area_title,
        "to-dos": todos,
        "reveal": str(reveal).lower() if reveal else None,
    }
    url = construct_url("add-project", params)
    _execute_url(url)
    return url


def update_todo_url(
    todo_id: str,
    title: str | None = None,
    notes: str | None = None,
    when: str | None = None,
    deadline: str | None = None,
    tags: list[str] | None = None,
    add_tags: list[str] | None = None,
    completed: bool | None = None,
    canceled: bool | None = None,
    list_id: str | None = None,
    list_title: str | None = None,
    heading: str | None = None,
    heading_id: str | None = None,
) -> str:
    """Update a todo via URL scheme."""
    params = {
        "id": todo_id,
        "title": title,
        "notes": notes,
        "when": when,
        "deadline": deadline,
        "tags": tags,
        "add-tags": add_tags,
        "completed": str(completed).lower() if completed is not None else None,
        "canceled": str(canceled).lower() if canceled is not None else None,
        "list-id": list_id,
        "list": list_title,
        "heading-id": heading_id,
        "heading": heading,
    }
    url = construct_url("update", params)
    _execute_url(url)
    return url


def update_project_url(
    project_id: str,
    title: str | None = None,
    notes: str | None = None,
    when: str | None = None,
    deadline: str | None = None,
    tags: list[str] | None = None,
    completed: bool | None = None,
    canceled: bool | None = None,
    area_id: str | None = None,
    area_title: str | None = None,
) -> str:
    """Update a project via URL scheme."""
    params = {
        "id": project_id,
        "title": title,
        "notes": notes,
        "when": when,
        "deadline": deadline,
        "tags": tags,
        "completed": str(completed).lower() if completed is not None else None,
        "canceled": str(canceled).lower() if canceled is not None else None,
        "area-id": area_id,
        "area": area_title,
    }
    url = construct_url("update-project", params)
    _execute_url(url)
    return url


def json_import(data: list[dict], reveal: bool = False) -> str:
    """Execute a JSON bulk operation via URL scheme."""
    params = {
        "data": json.dumps(data),
        "reveal": str(reveal).lower() if reveal else None,
    }
    # JSON may contain updates — add auth token if present
    has_updates = any(item.get("operation") == "update" for item in data)
    if has_updates:
        token = _get_auth_token()
        if token:
            params["auth-token"] = token

    url = construct_url("json", params)
    _execute_url(url)
    return url


def show_url(item_id: str | None = None, query: str | None = None) -> str:
    """Navigate to an item or list in Things."""
    params = {"id": item_id, "query": query}
    url = construct_url("show", params)
    _execute_url(url)
    return url


def search_url(query: str) -> str:
    """Open Things search."""
    url = construct_url("search", {"query": query})
    _execute_url(url)
    return url
