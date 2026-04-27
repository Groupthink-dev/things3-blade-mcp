"""Someday filtering — matches Things 3 UI behavior.

Things 3 treats tasks inside Someday projects as effectively Someday,
but things.py reports them as Anytime. This module corrects for that.

Usage:
    ctx = get_someday_context()
    filtered = filter_someday_tasks(todos, ctx)  # removes inherited-someday from active lists
    augmented = augment_someday_tasks(todos, ctx) # adds inherited-someday to someday list
"""

from __future__ import annotations

import things


def get_someday_context() -> tuple[set[str], dict[str, str]]:
    """Build Someday filtering context.

    Returns:
        (someday_project_ids, heading_to_project): A set of Someday project UUIDs
        and a mapping of heading UUIDs to their parent Someday project UUID.
    """
    someday_projects = things.projects(start="Someday") or []
    someday_project_ids = {p["uuid"] for p in someday_projects}

    heading_to_project: dict[str, str] = {}
    for proj_id in someday_project_ids:
        headings = things.tasks(type="heading", project=proj_id) or []
        for h in headings:
            heading_to_project[h["uuid"]] = proj_id

    return someday_project_ids, heading_to_project


def _is_in_someday_project(
    todo: dict,
    someday_project_ids: set[str],
    heading_to_project: dict[str, str],
) -> bool:
    """Check if a todo belongs to a Someday project (directly or via heading)."""
    project_uuid = todo.get("project")
    if project_uuid and project_uuid in someday_project_ids:
        return True

    heading_uuid = todo.get("heading")
    if heading_uuid and not project_uuid and heading_uuid in heading_to_project:
        return True

    return False


def filter_someday_tasks(
    todos: list[dict],
    ctx: tuple[set[str], dict[str, str]] | None = None,
) -> list[dict]:
    """Remove tasks that belong to Someday projects from active lists.

    Used by get_today, get_upcoming, get_anytime to match Things UI.
    """
    if ctx is None:
        ctx = get_someday_context()
    someday_ids, heading_map = ctx
    if not someday_ids:
        return todos
    return [t for t in todos if not _is_in_someday_project(t, someday_ids, heading_map)]


def augment_someday_tasks(
    someday_todos: list[dict],
    ctx: tuple[set[str], dict[str, str]] | None = None,
) -> list[dict]:
    """Add tasks from Someday projects that things.py reports as Anytime.

    Used by get_someday to match Things UI.
    """
    if ctx is None:
        ctx = get_someday_context()
    someday_ids, heading_map = ctx
    if not someday_ids:
        return someday_todos

    existing_uuids = {t["uuid"] for t in someday_todos}
    anytime_todos = things.anytime() or []

    for todo in anytime_todos:
        if todo["uuid"] not in existing_uuids and _is_in_someday_project(
            todo, someday_ids, heading_map
        ):
            someday_todos.append(todo)

    return someday_todos
