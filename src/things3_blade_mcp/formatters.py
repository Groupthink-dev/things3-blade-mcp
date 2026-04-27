"""Token-efficient formatters for Things 3 data.

Two modes:
  - concise (default): One line per item, null fields omitted.
  - detailed: Multi-line with notes, checklist, timestamps.

Batch-lookup design: caller provides lookup dicts to avoid N+1 queries.
"""

from __future__ import annotations

from things3_blade_mcp.models import SHORT_UUID_LEN, STATUS_ICONS

# ---------------------------------------------------------------------------
# Lookup builders — call once per tool invocation, pass to formatters
# ---------------------------------------------------------------------------


def build_project_lookup(projects: list[dict]) -> dict[str, str]:
    """Map project UUID → title."""
    return {p["uuid"]: p["title"] for p in projects if p.get("uuid") and p.get("title")}


def build_area_lookup(areas: list[dict]) -> dict[str, str]:
    """Map area UUID → title."""
    return {a["uuid"]: a["title"] for a in areas if a.get("uuid") and a.get("title")}


# ---------------------------------------------------------------------------
# Concise formatters — one line per item
# ---------------------------------------------------------------------------


def format_todo_concise(todo: dict, project_lookup: dict | None = None) -> str:
    """Single-line todo: icon Title [short_uuid] | schedule | deadline:X | #tags."""
    icon = STATUS_ICONS.get(todo.get("status", ""), "□")
    title = todo.get("title", "Untitled")
    short_id = todo.get("uuid", "")[:SHORT_UUID_LEN]

    parts = [f"{icon} {title} [{short_id}]"]

    # Schedule / when
    start = todo.get("start")
    start_date = todo.get("start_date")
    if start_date:
        parts.append(start_date)
    elif start and start != "Anytime":
        parts.append(start.lower())

    # Deadline
    deadline = todo.get("deadline")
    if deadline:
        parts.append(f"deadline:{deadline}")

    # Project context
    project_uuid = todo.get("project")
    if project_uuid and project_lookup:
        proj_name = project_lookup.get(project_uuid)
        if proj_name:
            parts.append(f"in:{proj_name}")

    # Tags
    tags = todo.get("tags")
    if tags:
        tag_str = ",".join(f"#{t}" for t in tags)
        parts.append(tag_str)

    return " | ".join(parts)


def format_project_concise(project: dict, todo_counts: dict | None = None) -> str:
    """Single-line project: Title [short_uuid] | schedule | open:N done:N | deadline:X."""
    title = project.get("title", "Untitled")
    short_id = project.get("uuid", "")[:SHORT_UUID_LEN]

    parts = [f"📋 {title} [{short_id}]"]

    start = project.get("start")
    if start and start != "Anytime":
        parts.append(start.lower())

    # Counts if provided
    if todo_counts:
        uuid = project.get("uuid", "")
        counts = todo_counts.get(uuid)
        if counts:
            parts.append(f"open:{counts.get('open', 0)} done:{counts.get('done', 0)}")

    deadline = project.get("deadline")
    if deadline:
        parts.append(f"deadline:{deadline}")

    tags = project.get("tags")
    if tags:
        parts.append(",".join(f"#{t}" for t in tags))

    return " | ".join(parts)


def format_area_concise(area: dict) -> str:
    """Single-line area: Title [short_uuid]."""
    title = area.get("title", "Untitled")
    short_id = area.get("uuid", "")[:SHORT_UUID_LEN]
    return f"📁 {title} [{short_id}]"


def format_tag_concise(tag: dict) -> str:
    """Single-line tag: #name [short_uuid]."""
    title = tag.get("title", "Untitled")
    short_id = tag.get("uuid", "")[:SHORT_UUID_LEN]
    shortcut = tag.get("shortcut")
    base = f"#{title} [{short_id}]"
    if shortcut:
        base += f" shortcut:{shortcut}"
    return base


# ---------------------------------------------------------------------------
# Detailed formatters — multi-line, full info
# ---------------------------------------------------------------------------


def format_todo_detailed(
    todo: dict,
    project_lookup: dict | None = None,
    area_lookup: dict | None = None,
) -> str:
    """Multi-line detailed todo output."""
    lines = []
    lines.append(f"Title: {todo.get('title', 'Untitled')}")
    lines.append(f"UUID: {todo.get('uuid', 'N/A')}")
    lines.append(f"Status: {todo.get('status', 'unknown')}")

    _type = todo.get("type")
    if _type:
        lines.append(f"Type: {_type}")

    start = todo.get("start")
    if start:
        lines.append(f"Start: {start}")

    start_date = todo.get("start_date")
    if start_date:
        lines.append(f"Scheduled: {start_date}")

    deadline = todo.get("deadline")
    if deadline:
        lines.append(f"Deadline: {deadline}")

    # Project
    project_uuid = todo.get("project")
    if project_uuid:
        proj_name = (project_lookup or {}).get(project_uuid, project_uuid)
        lines.append(f"Project: {proj_name}")

    # Area
    area_uuid = todo.get("area")
    if area_uuid:
        area_name = (area_lookup or {}).get(area_uuid, area_uuid)
        lines.append(f"Area: {area_name}")

    tags = todo.get("tags")
    if tags:
        lines.append(f"Tags: {', '.join(tags)}")

    notes = todo.get("notes")
    if notes:
        # Truncate long notes in detailed mode too — 500 chars max
        if len(notes) > 500:
            notes = notes[:500] + "…"
        lines.append(f"Notes: {notes}")

    # Checklist items
    checklist = todo.get("checklist")
    if checklist:
        lines.append("Checklist:")
        for item in checklist:
            check = "✓" if item.get("status") == "completed" else "□"
            lines.append(f"  {check} {item.get('title', '')}")

    stop_date = todo.get("stop_date")
    if stop_date:
        lines.append(f"Completed: {stop_date}")

    created = todo.get("created")
    if created:
        lines.append(f"Created: {created}")

    modified = todo.get("modified")
    if modified:
        lines.append(f"Modified: {modified}")

    return "\n".join(lines)


def format_project_detailed(
    project: dict,
    area_lookup: dict | None = None,
    items: list[dict] | None = None,
    project_lookup: dict | None = None,
) -> str:
    """Multi-line detailed project output."""
    lines = []
    lines.append(f"Title: {project.get('title', 'Untitled')}")
    lines.append(f"UUID: {project.get('uuid', 'N/A')}")
    lines.append(f"Status: {project.get('status', 'unknown')}")

    start = project.get("start")
    if start:
        lines.append(f"Start: {start}")

    deadline = project.get("deadline")
    if deadline:
        lines.append(f"Deadline: {deadline}")

    area_uuid = project.get("area")
    if area_uuid:
        area_name = (area_lookup or {}).get(area_uuid, area_uuid)
        lines.append(f"Area: {area_name}")

    tags = project.get("tags")
    if tags:
        lines.append(f"Tags: {', '.join(tags)}")

    notes = project.get("notes")
    if notes:
        if len(notes) > 500:
            notes = notes[:500] + "…"
        lines.append(f"Notes: {notes}")

    if items:
        lines.append(f"Tasks ({len(items)}):")
        for t in items[:20]:  # Cap at 20 even in detailed mode
            icon = STATUS_ICONS.get(t.get("status", ""), "□")
            lines.append(f"  {icon} {t.get('title', 'Untitled')}")
        if len(items) > 20:
            lines.append(f"  … and {len(items) - 20} more")

    return "\n".join(lines)


def format_area_detailed(
    area: dict,
    projects: list[dict] | None = None,
    todos: list[dict] | None = None,
) -> str:
    """Multi-line detailed area output."""
    lines = []
    lines.append(f"Title: {area.get('title', 'Untitled')}")
    lines.append(f"UUID: {area.get('uuid', 'N/A')}")

    tags = area.get("tags")
    if tags:
        lines.append(f"Tags: {', '.join(tags)}")

    if projects:
        lines.append(f"Projects ({len(projects)}):")
        for p in projects:
            lines.append(f"  📋 {p.get('title', 'Untitled')}")

    if todos:
        lines.append(f"Todos ({len(todos)}):")
        for t in todos[:20]:
            lines.append(f"  □ {t.get('title', 'Untitled')}")
        if len(todos) > 20:
            lines.append(f"  … and {len(todos) - 20} more")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# List formatters — take a list and render with appropriate mode
# ---------------------------------------------------------------------------


def format_todo_list(
    todos: list[dict],
    concise: bool = True,
    limit: int = 10,
    project_lookup: dict | None = None,
    area_lookup: dict | None = None,
) -> str:
    """Format a list of todos with count header."""
    total = len(todos)
    shown = todos[:limit]

    if not shown:
        return "No items found."

    if concise:
        lines = [format_todo_concise(t, project_lookup) for t in shown]
    else:
        lines = [format_todo_detailed(t, project_lookup, area_lookup) for t in shown]
        lines = ["\n---\n".join(lines)] if lines else []
        return f"Showing {len(shown)}/{total} items\n\n" + lines[0] if lines else "No items found."

    result = "\n".join(lines)
    if total > len(shown):
        result += f"\n… {total - len(shown)} more (use limit= to see more)"
    return result


def format_project_list(
    projects: list[dict],
    concise: bool = True,
    limit: int = 10,
    todo_counts: dict | None = None,
    area_lookup: dict | None = None,
) -> str:
    """Format a list of projects."""
    total = len(projects)
    shown = projects[:limit]

    if not shown:
        return "No projects found."

    if concise:
        lines = [format_project_concise(p, todo_counts) for p in shown]
    else:
        lines = []
        for p in shown:
            lines.append(format_project_detailed(p, area_lookup))
        return f"Showing {len(shown)}/{total} projects\n\n" + "\n---\n".join(lines)

    result = "\n".join(lines)
    if total > len(shown):
        result += f"\n… {total - len(shown)} more (use limit= to see more)"
    return result
