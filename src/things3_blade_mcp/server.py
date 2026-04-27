"""Things 3 MCP Server — token-efficient, full CRUD, AppleScript + URL scheme.

Prioritizes token efficiency: concise output by default, random sampling,
summary modes, and hard limits on all list operations.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Annotated

import things
from fastmcp import FastMCP
from pydantic import Field

from things3_blade_mcp import applescript, url_scheme
from things3_blade_mcp.formatters import (
    build_area_lookup,
    build_project_lookup,
    format_area_concise,
    format_area_detailed,
    format_project_concise,
    format_project_detailed,
    format_project_list,
    format_tag_concise,
    format_todo_concise,
    format_todo_detailed,
    format_todo_list,
)
from things3_blade_mcp.models import DEFAULT_LIMIT, DEFAULT_SAMPLE_COUNT
from things3_blade_mcp.sampling import random_sample
from things3_blade_mcp.someday import augment_someday_tasks, filter_someday_tasks, get_someday_context

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Transport configuration
# ---------------------------------------------------------------------------

TRANSPORT = os.environ.get("THINGS_MCP_TRANSPORT", "stdio")
HTTP_HOST = os.environ.get("THINGS_MCP_HOST", "127.0.0.1")
HTTP_PORT = int(os.environ.get("THINGS_MCP_PORT", "8765"))

# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "Things3",
    instructions=(
        "Things 3 task manager integration. Use concise=True (default) for token efficiency. "
        "Start with get_random_* or get_summary for overviews before requesting full lists. "
        "Use limit= to control output size. See SKILL.md for optimal workflows."
    ),
)


# ---------------------------------------------------------------------------
# Helper: build lookup caches once per call
# ---------------------------------------------------------------------------


def _project_lookup() -> dict[str, str]:
    """Build project UUID→title lookup."""
    return build_project_lookup(things.projects() or [])


def _area_lookup() -> dict[str, str]:
    """Build area UUID→title lookup."""
    return build_area_lookup(things.areas() or [])


def _todo_counts_for_projects() -> dict[str, dict[str, int]]:
    """Build project UUID → {open: N, done: N} counts."""
    counts: dict[str, dict[str, int]] = {}
    all_todos = things.todos() or []
    for t in all_todos:
        proj = t.get("project")
        if proj:
            if proj not in counts:
                counts[proj] = {"open": 0, "done": 0}
            if t.get("status") == "completed":
                counts[proj]["done"] += 1
            else:
                counts[proj]["open"] += 1
    return counts


def _normalise_title(title: str) -> str:
    """Normalise a task title for fuzzy comparison.

    Strips common prefixes, collapses whitespace, lowercases, removes
    trailing punctuation. Designed to catch near-duplicate tasks created
    by different dispatch runs with slightly different wording.
    """
    import re
    t = title.lower().strip()
    # Strip common action prefixes added by skills
    t = re.sub(r"^(review|pay|check|file|schedule|follow up|reply to|open|authorise|verify)\s*:\s*", "", t)
    # Collapse whitespace and strip trailing punctuation
    t = re.sub(r"\s+", " ", t).strip().rstrip(".")
    return t


def _find_duplicate_todo(title: str) -> dict | None:
    """Search open todos for a duplicate of the given title.

    Uses things.search() for candidate retrieval, then normalised title
    comparison. Returns the first matching todo dict, or None.
    """
    normalised = _normalise_title(title)
    if not normalised:
        return None

    try:
        # Search with first few significant words to get candidates
        search_words = normalised.split()[:4]
        candidates = things.search(" ".join(search_words)) or []

        for item in candidates:
            # Only match open (incomplete) todos
            if item.get("status") == "completed" or item.get("status") == "canceled":
                continue
            candidate_norm = _normalise_title(item.get("title", ""))
            if candidate_norm == normalised:
                return item
    except Exception:
        logger.debug("Dedup search failed, proceeding with creation", exc_info=True)

    return None


# ===========================================================================
# LIST VIEW TOOLS
# ===========================================================================


@mcp.tool
def get_inbox(
    concise: Annotated[bool, Field(description="One-line-per-item output (default: true)")] = True,
    limit: Annotated[int, Field(description="Max items to return (default: 10)")] = DEFAULT_LIMIT,
    include_details: Annotated[
        bool, Field(description="Include notes, checklist, timestamps")
    ] = False,
) -> str:
    """Get todos from the Things 3 Inbox.

    The Inbox is where unprocessed tasks live. Start here for GTD capture review.
    For a quick overview, use get_random_inbox instead.
    """
    items = things.inbox(include_items=True) or []
    proj_lookup = _project_lookup() if not concise or include_details else None
    area_lk = _area_lookup() if include_details else None
    return format_todo_list(
        items, concise=concise and not include_details, limit=limit,
        project_lookup=proj_lookup, area_lookup=area_lk,
    )


@mcp.tool
def get_today(
    concise: Annotated[bool, Field(description="One-line-per-item output (default: true)")] = True,
    limit: Annotated[int, Field(description="Max items to return (default: 10)")] = DEFAULT_LIMIT,
    include_details: Annotated[
        bool, Field(description="Include notes, checklist, timestamps")
    ] = False,
) -> str:
    """Get todos scheduled for Today in Things 3.

    Filters out tasks that inherit Someday status from their parent project,
    matching the Things UI exactly.
    """
    items = things.today(include_items=True) or []
    ctx = get_someday_context()
    items = filter_someday_tasks(items, ctx)
    proj_lookup = _project_lookup() if not concise or include_details else None
    area_lk = _area_lookup() if include_details else None
    return format_todo_list(
        items, concise=concise and not include_details, limit=limit,
        project_lookup=proj_lookup, area_lookup=area_lk,
    )


@mcp.tool
def get_upcoming(
    concise: Annotated[bool, Field(description="One-line-per-item output (default: true)")] = True,
    limit: Annotated[int, Field(description="Max items to return (default: 10)")] = DEFAULT_LIMIT,
    include_details: Annotated[
        bool, Field(description="Include notes, checklist, timestamps")
    ] = False,
) -> str:
    """Get upcoming scheduled todos from Things 3.

    Shows tasks scheduled for future dates. Excludes inherited-Someday tasks.
    """
    items = things.upcoming(include_items=True) or []
    ctx = get_someday_context()
    items = filter_someday_tasks(items, ctx)
    proj_lookup = _project_lookup() if not concise or include_details else None
    area_lk = _area_lookup() if include_details else None
    return format_todo_list(
        items, concise=concise and not include_details, limit=limit,
        project_lookup=proj_lookup, area_lookup=area_lk,
    )


@mcp.tool
def get_anytime(
    concise: Annotated[bool, Field(description="One-line-per-item output (default: true)")] = True,
    limit: Annotated[int, Field(description="Max items to return (default: 10)")] = DEFAULT_LIMIT,
    include_details: Annotated[
        bool, Field(description="Include notes, checklist, timestamps")
    ] = False,
) -> str:
    """Get Anytime todos from Things 3.

    Shows tasks available to work on at any time. Excludes inherited-Someday tasks.
    """
    items = things.anytime(include_items=True) or []
    ctx = get_someday_context()
    items = filter_someday_tasks(items, ctx)
    proj_lookup = _project_lookup() if not concise or include_details else None
    area_lk = _area_lookup() if include_details else None
    return format_todo_list(
        items, concise=concise and not include_details, limit=limit,
        project_lookup=proj_lookup, area_lookup=area_lk,
    )


@mcp.tool
def get_someday(
    concise: Annotated[bool, Field(description="One-line-per-item output (default: true)")] = True,
    limit: Annotated[int, Field(description="Max items to return (default: 10)")] = DEFAULT_LIMIT,
    include_details: Annotated[
        bool, Field(description="Include notes, checklist, timestamps")
    ] = False,
) -> str:
    """Get Someday todos from Things 3.

    Includes both directly-Someday tasks AND tasks that inherit Someday status
    from their parent project, matching the Things UI exactly.
    """
    items = things.someday(include_items=True) or []
    ctx = get_someday_context()
    items = augment_someday_tasks(items, ctx)
    proj_lookup = _project_lookup() if not concise or include_details else None
    area_lk = _area_lookup() if include_details else None
    return format_todo_list(
        items, concise=concise and not include_details, limit=limit,
        project_lookup=proj_lookup, area_lookup=area_lk,
    )


@mcp.tool
def get_logbook(
    period: Annotated[
        str, Field(description="Time period: '7d', '2w', '1m', '3m', '1y' (default: '7d')")
    ] = "7d",
    concise: Annotated[bool, Field(description="One-line-per-item output (default: true)")] = True,
    limit: Annotated[int, Field(description="Max items to return (default: 10)")] = DEFAULT_LIMIT,
) -> str:
    """Get completed todos from the Things 3 Logbook.

    Shows recently completed tasks within the given time period.
    """
    items = things.last(period) or []
    items = [t for t in items if t.get("status") == "completed"]
    proj_lookup = _project_lookup() if not concise else None
    return format_todo_list(items, concise=concise, limit=limit, project_lookup=proj_lookup)


@mcp.tool
def get_trash(
    concise: Annotated[bool, Field(description="One-line-per-item output (default: true)")] = True,
    limit: Annotated[int, Field(description="Max items to return (default: 10)")] = DEFAULT_LIMIT,
) -> str:
    """Get trashed todos from Things 3."""
    items = things.trash(include_items=True) or []
    proj_lookup = _project_lookup() if not concise else None
    return format_todo_list(items, concise=concise, limit=limit, project_lookup=proj_lookup)


@mcp.tool
def get_deadlines(
    concise: Annotated[bool, Field(description="One-line-per-item output (default: true)")] = True,
    limit: Annotated[int, Field(description="Max items to return (default: 10)")] = DEFAULT_LIMIT,
) -> str:
    """Get todos with deadlines, sorted chronologically.

    Useful for seeing what's due soonest. Includes tasks from all lists.
    """
    items = things.deadlines() or []
    proj_lookup = _project_lookup() if not concise else None
    return format_todo_list(items, concise=concise, limit=limit, project_lookup=proj_lookup)


# ===========================================================================
# RANDOM SAMPLING TOOLS — recommended entry points for LLM workflows
# ===========================================================================


@mcp.tool
def get_random_inbox(
    count: Annotated[
        int, Field(description="Number of random items to sample (default: 5)")
    ] = DEFAULT_SAMPLE_COUNT,
) -> str:
    """Get a random sample from the Things 3 Inbox.

    RECOMMENDED as the first call when reviewing the inbox — returns a
    manageable batch instead of flooding context with hundreds of items.
    Always uses concise format for token efficiency.
    """
    items = things.inbox(include_items=True) or []
    sampled = random_sample(items, count)
    total = len(items)
    proj_lookup = _project_lookup()
    lines = [format_todo_concise(t, proj_lookup) for t in sampled]
    header = f"Random {len(sampled)} of {total} inbox items:"
    return header + "\n" + "\n".join(lines)


@mcp.tool
def get_random_today(
    count: Annotated[
        int, Field(description="Number of random items to sample (default: 5)")
    ] = DEFAULT_SAMPLE_COUNT,
) -> str:
    """Get a random sample from Today in Things 3.

    Applies Someday filtering. Great for quick daily check-ins.
    """
    items = things.today(include_items=True) or []
    ctx = get_someday_context()
    items = filter_someday_tasks(items, ctx)
    sampled = random_sample(items, count)
    total = len(items)
    proj_lookup = _project_lookup()
    lines = [format_todo_concise(t, proj_lookup) for t in sampled]
    header = f"Random {len(sampled)} of {total} today items:"
    return header + "\n" + "\n".join(lines)


@mcp.tool
def get_random_anytime(
    count: Annotated[
        int, Field(description="Number of random items to sample (default: 5)")
    ] = DEFAULT_SAMPLE_COUNT,
) -> str:
    """Get a random sample from Anytime in Things 3.

    Applies Someday filtering. Useful for finding tasks to work on next.
    """
    items = things.anytime(include_items=True) or []
    ctx = get_someday_context()
    items = filter_someday_tasks(items, ctx)
    sampled = random_sample(items, count)
    total = len(items)
    proj_lookup = _project_lookup()
    lines = [format_todo_concise(t, proj_lookup) for t in sampled]
    header = f"Random {len(sampled)} of {total} anytime items:"
    return header + "\n" + "\n".join(lines)


@mcp.tool
def get_random_todos(
    project_uuid: Annotated[
        str | None, Field(description="Filter to a specific project by UUID")
    ] = None,
    count: Annotated[
        int, Field(description="Number of random items to sample (default: 5)")
    ] = DEFAULT_SAMPLE_COUNT,
) -> str:
    """Get a random sample of todos, optionally filtered by project.

    Use this for LLM enrichment workflows — review and improve tasks in batches.
    """
    items = things.todos(project=project_uuid) or []
    sampled = random_sample(items, count)
    total = len(items)
    proj_lookup = _project_lookup()
    lines = [format_todo_concise(t, proj_lookup) for t in sampled]
    header = f"Random {len(sampled)} of {total} todos:"
    return header + "\n" + "\n".join(lines)


# ===========================================================================
# ENTITY VIEW TOOLS
# ===========================================================================


@mcp.tool
def get_todos(
    project_uuid: Annotated[
        str | None, Field(description="Filter by project UUID")
    ] = None,
    concise: Annotated[bool, Field(description="One-line-per-item output (default: true)")] = True,
    limit: Annotated[int, Field(description="Max items to return (default: 10)")] = DEFAULT_LIMIT,
    include_details: Annotated[
        bool, Field(description="Include notes, checklist, timestamps")
    ] = False,
) -> str:
    """Get all open todos, optionally filtered by project.

    For large lists, prefer get_random_todos first.
    """
    items = things.todos(project=project_uuid, include_items=True) or []
    proj_lookup = _project_lookup() if not concise or include_details else None
    area_lk = _area_lookup() if include_details else None
    return format_todo_list(
        items, concise=concise and not include_details, limit=limit,
        project_lookup=proj_lookup, area_lookup=area_lk,
    )


@mcp.tool
def get_projects(
    concise: Annotated[bool, Field(description="One-line-per-project output (default: true)")] = True,
    limit: Annotated[int, Field(description="Max items to return (default: 10)")] = DEFAULT_LIMIT,
    include_items: Annotated[
        bool, Field(description="Include task list inside each project")
    ] = False,
) -> str:
    """Get all active projects from Things 3.

    Default concise mode shows project name + open/done counts.
    """
    projects = things.projects() or []
    todo_counts = _todo_counts_for_projects() if concise else None
    area_lk = _area_lookup() if not concise else None
    return format_project_list(
        projects, concise=concise, limit=limit,
        todo_counts=todo_counts, area_lookup=area_lk,
    )


@mcp.tool
def get_areas(
    concise: Annotated[bool, Field(description="One-line-per-area output (default: true)")] = True,
    limit: Annotated[int, Field(description="Max items to return (default: 10)")] = DEFAULT_LIMIT,
) -> str:
    """Get all areas from Things 3.

    Areas are high-level categories (e.g., Work, Personal, Health).
    """
    areas = things.areas() or []
    total = len(areas)
    shown = areas[:limit]

    if not shown:
        return "No areas found."

    if concise:
        lines = [format_area_concise(a) for a in shown]
    else:
        lines = [format_area_detailed(a) for a in shown]

    result = "\n".join(lines)
    if total > len(shown):
        result += f"\n… {total - len(shown)} more (use limit= to see more)"
    return result


@mcp.tool
def get_tags(
    concise: Annotated[bool, Field(description="One-line-per-tag output (default: true)")] = True,
    limit: Annotated[int, Field(description="Max items to return (default: 10)")] = DEFAULT_LIMIT,
    include_items: Annotated[
        bool, Field(description="Include tagged items for each tag")
    ] = False,
) -> str:
    """Get all tags from Things 3."""
    tags = things.tags(include_items=include_items) or []
    total = len(tags)
    shown = tags[:limit]

    if not shown:
        return "No tags found."

    lines = [format_tag_concise(t) for t in shown]
    result = "\n".join(lines)
    if total > len(shown):
        result += f"\n… {total - len(shown)} more (use limit= to see more)"
    return result


@mcp.tool
def get_tagged_items(
    tag: Annotated[str, Field(description="Tag name to filter by")],
    concise: Annotated[bool, Field(description="One-line-per-item output (default: true)")] = True,
    limit: Annotated[int, Field(description="Max items to return (default: 10)")] = DEFAULT_LIMIT,
) -> str:
    """Get all todos with a specific tag."""
    items = things.todos(tag=tag, include_items=True) or []
    proj_lookup = _project_lookup() if not concise else None
    return format_todo_list(items, concise=concise, limit=limit, project_lookup=proj_lookup)


# ===========================================================================
# SEARCH & DETAIL TOOLS
# ===========================================================================


@mcp.tool
def search_todos(
    query: Annotated[str, Field(description="Search terms (matches title and notes)")],
    concise: Annotated[bool, Field(description="One-line-per-item output (default: true)")] = True,
    limit: Annotated[int, Field(description="Max items to return (default: 10)")] = DEFAULT_LIMIT,
) -> str:
    """Search todos by title or notes content."""
    items = things.search(query, include_items=True) or []
    proj_lookup = _project_lookup() if not concise else None
    return format_todo_list(items, concise=concise, limit=limit, project_lookup=proj_lookup)


@mcp.tool
def search_advanced(
    status: Annotated[
        str | None, Field(description="Filter: 'incomplete', 'completed', 'canceled'")
    ] = None,
    start_date: Annotated[
        str | None, Field(description="Start date filter, e.g. '2026-01-01' or '>=2026-01-01'")
    ] = None,
    deadline: Annotated[
        str | None, Field(description="Deadline filter, e.g. '<=2026-03-01'")
    ] = None,
    tag: Annotated[str | None, Field(description="Filter by tag name")] = None,
    area: Annotated[str | None, Field(description="Filter by area UUID")] = None,
    item_type: Annotated[
        str | None, Field(description="Filter: 'to-do', 'project', 'heading'")
    ] = None,
    last: Annotated[
        str | None, Field(description="Created within period: '3d', '1w', '2m'")
    ] = None,
    concise: Annotated[bool, Field(description="One-line-per-item output (default: true)")] = True,
    limit: Annotated[int, Field(description="Max items to return (default: 10)")] = DEFAULT_LIMIT,
) -> str:
    """Advanced search with multiple filters.

    Combine any filters to narrow down results. All filters are AND-combined.
    """
    kwargs: dict = {}
    if status:
        kwargs["status"] = status
    if start_date:
        kwargs["start_date"] = start_date
    if deadline:
        kwargs["deadline"] = deadline
    if tag:
        kwargs["tag"] = tag
    if area:
        kwargs["area"] = area
    if item_type:
        kwargs["type"] = item_type
    if last:
        kwargs["last"] = last

    items = things.todos(**kwargs) or []
    proj_lookup = _project_lookup() if not concise else None
    return format_todo_list(items, concise=concise, limit=limit, project_lookup=proj_lookup)


@mcp.tool
def get_recent(
    period: Annotated[str, Field(description="Time period: '3d', '1w', '2m', '1y'")],
    concise: Annotated[bool, Field(description="One-line-per-item output (default: true)")] = True,
    limit: Annotated[int, Field(description="Max items to return (default: 10)")] = DEFAULT_LIMIT,
) -> str:
    """Get recently created todos within a time period."""
    items = things.last(period) or []
    proj_lookup = _project_lookup() if not concise else None
    return format_todo_list(items, concise=concise, limit=limit, project_lookup=proj_lookup)


@mcp.tool
def show_item(
    uuid: Annotated[str, Field(description="UUID of the item to show (or built-in list name)")],
    include_details: Annotated[
        bool, Field(description="Include full details (default: true for single items)")
    ] = True,
) -> str:
    """Get a single item by UUID with full details.

    Also accepts built-in list names: inbox, today, upcoming, anytime, someday, logbook, trash.
    """
    item = things.get(uuid)
    if not item:
        return f"No item found with UUID: {uuid}"

    item_type = item.get("type")
    if include_details:
        proj_lookup = _project_lookup()
        area_lk = _area_lookup()
        if item_type == "project":
            proj_items = things.todos(project=uuid, include_items=True) or []
            return format_project_detailed(item, area_lk, proj_items, proj_lookup)
        return format_todo_detailed(item, proj_lookup, area_lk)
    else:
        proj_lookup = _project_lookup()
        if item_type == "project":
            return format_project_concise(item)
        return format_todo_concise(item, proj_lookup)


# ===========================================================================
# SUMMARY TOOL — GTD overview in minimal tokens
# ===========================================================================


@mcp.tool
def get_summary() -> str:
    """Get a token-efficient GTD overview of your entire Things 3 system.

    Returns item counts per list, upcoming deadlines, and stale inbox items.
    RECOMMENDED as the very first call — gives full context in ~20 lines.
    """
    ctx = get_someday_context()

    inbox = things.inbox() or []
    today_items = filter_someday_tasks(things.today() or [], ctx)
    upcoming = filter_someday_tasks(things.upcoming() or [], ctx)
    anytime = filter_someday_tasks(things.anytime() or [], ctx)
    someday_items = augment_someday_tasks(things.someday() or [], ctx)
    projects = things.projects() or []
    areas = things.areas() or []

    # Deadlines in next 7 days
    deadlines = things.deadlines() or []
    from datetime import date, timedelta
    week_from_now = (date.today() + timedelta(days=7)).isoformat()
    urgent = [d for d in deadlines if d.get("deadline") and d["deadline"] <= week_from_now]

    lines = [
        "=== Things 3 Summary ===",
        f"Inbox: {len(inbox)} items",
        f"Today: {len(today_items)} items",
        f"Upcoming: {len(upcoming)} items",
        f"Anytime: {len(anytime)} items",
        f"Someday: {len(someday_items)} items",
        f"Projects: {len(projects)} active",
        f"Areas: {len(areas)}",
    ]

    if urgent:
        lines.append(f"\nDue this week ({len(urgent)}):")
        for d in urgent[:5]:
            lines.append(f"  ! {d.get('title', 'Untitled')} — deadline:{d.get('deadline')}")
        if len(urgent) > 5:
            lines.append(f"  … and {len(urgent) - 5} more")

    return "\n".join(lines)


# ===========================================================================
# WRITE TOOLS — AppleScript primary, URL scheme fallback
# ===========================================================================


@mcp.tool
def add_todo(
    title: Annotated[str, Field(description="Todo title")],
    notes: Annotated[
        str | None, Field(description="Notes (supports Markdown; use checkboxes for subtasks)")
    ] = None,
    when: Annotated[
        str | None,
        Field(description="Schedule: 'today', 'tomorrow', 'evening', 'anytime', 'someday', or YYYY-MM-DD"),
    ] = None,
    deadline: Annotated[
        str | None, Field(description="Deadline date in YYYY-MM-DD format")
    ] = None,
    tags: Annotated[
        list[str] | None, Field(description="List of tag names to apply")
    ] = None,
    list_id: Annotated[
        str | None, Field(description="UUID of project or area to add to (takes precedence over list_title)")
    ] = None,
    list_title: Annotated[
        str | None, Field(description="Name of project or area to add to")
    ] = None,
    checklist_items: Annotated[
        list[str] | None,
        Field(description="Subtask items (uses URL scheme fallback since AppleScript cannot create checklist items)"),
    ] = None,
    deduplicate: Annotated[
        bool,
        Field(description="Check for existing open todos with similar titles before creating. "
              "Returns existing todo instead of creating a duplicate. Default: true"),
    ] = True,
) -> str:
    """Create a new todo in Things 3.

    Returns the UUID of the created todo. Uses AppleScript for reliability;
    falls back to URL scheme if AppleScript fails.

    Tip: For subtasks, either pass checklist_items (URL scheme) or put Markdown
    checkboxes in notes: '- [ ] subtask 1\\n- [ ] subtask 2'
    """
    # Dedup check: search for existing open todos with similar titles
    if deduplicate:
        existing = _find_duplicate_todo(title)
        if existing:
            uuid = existing.get("uuid", "?")[:8]
            existing_title = existing.get("title", title)
            return (
                f"Skipped — duplicate found: '{existing_title}' (UUID: {uuid}…). "
                f"Use deduplicate=false to force creation."
            )

    # If checklist_items requested, must use URL scheme (AppleScript can't do it)
    if checklist_items:
        result_url = url_scheme.add_todo_url(
            title=title, notes=notes, when=when, deadline=deadline,
            tags=tags, checklist_items=checklist_items,
            list_id=list_id, list_title=list_title,
        )
        return f"Created todo '{title}' via URL scheme (checklist items included). URL: {result_url}"

    try:
        result = applescript.add_todo(
            title=title, notes=notes, when=when, deadline=deadline,
            tags=tags, list_id=list_id, list_title=list_title,
        )
        if result.startswith("Error:"):
            raise RuntimeError(result)
        return f"Created todo '{title}' — UUID: {result}"
    except RuntimeError:
        logger.info("AppleScript failed, falling back to URL scheme")
        result_url = url_scheme.add_todo_url(
            title=title, notes=notes, when=when, deadline=deadline,
            tags=tags, list_id=list_id, list_title=list_title,
        )
        return f"Created todo '{title}' via URL scheme (no UUID available)."


@mcp.tool
def add_project(
    title: Annotated[str, Field(description="Project title")],
    notes: Annotated[str | None, Field(description="Project notes")] = None,
    when: Annotated[
        str | None,
        Field(description="Schedule: 'today', 'tomorrow', 'anytime', 'someday', or YYYY-MM-DD"),
    ] = None,
    deadline: Annotated[
        str | None, Field(description="Deadline date in YYYY-MM-DD format")
    ] = None,
    tags: Annotated[list[str] | None, Field(description="List of tag names")] = None,
    area_id: Annotated[str | None, Field(description="UUID of area to assign to")] = None,
    area_title: Annotated[str | None, Field(description="Name of area to assign to")] = None,
    todos: Annotated[
        list[str] | None, Field(description="List of todo titles to create inside the project")
    ] = None,
) -> str:
    """Create a new project in Things 3.

    Returns the UUID of the created project. Optionally include initial todos.
    """
    try:
        result = applescript.add_project(
            title=title, notes=notes, when=when, deadline=deadline,
            tags=tags, area_id=area_id, area_title=area_title, todos=todos,
        )
        if result.startswith("Error:"):
            raise RuntimeError(result)
        return f"Created project '{title}' — UUID: {result}"
    except RuntimeError:
        logger.info("AppleScript failed, falling back to URL scheme")
        url_scheme.add_project_url(
            title=title, notes=notes, when=when, deadline=deadline,
            tags=tags, area_id=area_id, area_title=area_title, todos=todos,
        )
        return f"Created project '{title}' via URL scheme (no UUID available)."


@mcp.tool
def update_todo(
    todo_id: Annotated[str, Field(description="UUID of the todo to update")],
    title: Annotated[str | None, Field(description="New title")] = None,
    notes: Annotated[str | None, Field(description="New notes (replaces existing)")] = None,
    when: Annotated[
        str | None,
        Field(description="Reschedule: 'today', 'tomorrow', 'anytime', 'someday', or YYYY-MM-DD"),
    ] = None,
    deadline: Annotated[
        str | None, Field(description="New deadline in YYYY-MM-DD format")
    ] = None,
    tags: Annotated[list[str] | None, Field(description="Replace all tags")] = None,
    completed: Annotated[bool | None, Field(description="Mark completed (true) or reopen (false)")] = None,
    canceled: Annotated[bool | None, Field(description="Mark canceled (true) or reopen (false)")] = None,
    list_id: Annotated[str | None, Field(description="Move to project/area by UUID")] = None,
    list_name: Annotated[str | None, Field(description="Move to project/area by name")] = None,
) -> str:
    """Update an existing todo in Things 3.

    Uses AppleScript (no auth token needed). Falls back to URL scheme if needed.
    Pass only the fields you want to change.
    """
    try:
        result = applescript.update_todo(
            todo_id=todo_id, title=title, notes=notes, when=when,
            deadline=deadline, tags=tags, completed=completed, canceled=canceled,
            list_id=list_id, list_name=list_name,
        )
        if result.startswith("Error:"):
            raise RuntimeError(result)
        return f"Updated todo {todo_id}"
    except RuntimeError:
        logger.info("AppleScript failed, falling back to URL scheme")
        url_scheme.update_todo_url(
            todo_id=todo_id, title=title, notes=notes, when=when,
            deadline=deadline, tags=tags, completed=completed, canceled=canceled,
            list_id=list_id, list_title=list_name,
        )
        return f"Updated todo {todo_id} via URL scheme."


@mcp.tool
def update_project(
    project_id: Annotated[str, Field(description="UUID of the project to update")],
    title: Annotated[str | None, Field(description="New title")] = None,
    notes: Annotated[str | None, Field(description="New notes (replaces existing)")] = None,
    when: Annotated[
        str | None,
        Field(description="Reschedule: 'today', 'tomorrow', 'anytime', 'someday', or YYYY-MM-DD"),
    ] = None,
    deadline: Annotated[
        str | None, Field(description="New deadline in YYYY-MM-DD format")
    ] = None,
    tags: Annotated[list[str] | None, Field(description="Replace all tags")] = None,
    completed: Annotated[bool | None, Field(description="Mark completed (true) or reopen (false)")] = None,
    canceled: Annotated[bool | None, Field(description="Mark canceled (true) or reopen (false)")] = None,
    area_id: Annotated[str | None, Field(description="Move to area by UUID")] = None,
    area_title: Annotated[str | None, Field(description="Move to area by name")] = None,
) -> str:
    """Update an existing project in Things 3.

    Uses AppleScript (no auth token needed). Falls back to URL scheme if needed.
    """
    try:
        result = applescript.update_project(
            project_id=project_id, title=title, notes=notes, when=when,
            deadline=deadline, tags=tags, completed=completed, canceled=canceled,
            area_id=area_id, area_title=area_title,
        )
        if result.startswith("Error:"):
            raise RuntimeError(result)
        return f"Updated project {project_id}"
    except RuntimeError:
        logger.info("AppleScript failed, falling back to URL scheme")
        url_scheme.update_project_url(
            project_id=project_id, title=title, notes=notes, when=when,
            deadline=deadline, tags=tags, completed=completed, canceled=canceled,
            area_id=area_id, area_title=area_title,
        )
        return f"Updated project {project_id} via URL scheme."


# ===========================================================================
# NAVIGATION TOOLS
# ===========================================================================


@mcp.tool
def show_in_things(
    item_id: Annotated[
        str, Field(description="UUID of item, or list name: inbox, today, upcoming, someday, logbook, trash")
    ],
) -> str:
    """Reveal an item or list in the Things 3 app window.

    Accepts UUIDs or built-in list names.
    """
    try:
        result = applescript.show_in_things(item_id)
        if result == "OK":
            return f"Revealed {item_id} in Things."
        return result
    except RuntimeError:
        url_scheme.show_url(item_id)
        return f"Revealed {item_id} in Things via URL scheme."


@mcp.tool
def search_in_things(
    query: Annotated[str, Field(description="Search terms to open in Things search UI")],
) -> str:
    """Open the Things 3 search UI with the given query.

    This opens the search in the Things app itself — use search_todos for
    programmatic search that returns results here.
    """
    url_scheme.search_url(query)
    return f"Opened Things search for: {query}"


# ===========================================================================
# BULK / JSON IMPORT-EXPORT
# ===========================================================================


@mcp.tool
def json_import(
    data: Annotated[
        str,
        Field(
            description=(
                "JSON string: array of objects with {type, attributes}. "
                "Types: 'to-do', 'project', 'heading'. "
                "Attributes: title, notes, when, deadline, tags, checklist-items, list, heading. "
                "Example: [{\"type\":\"to-do\",\"attributes\":{\"title\":\"Buy milk\",\"when\":\"today\"}}]"
            )
        ),
    ],
    reveal: Annotated[bool, Field(description="Show first created item in Things")] = False,
) -> str:
    """Bulk import todos and projects via Things JSON format.

    Accepts the Things URL scheme JSON format. Supports nested projects with
    headings and todos. Rate limit: 250 items per 10 seconds.
    """
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e}"

    if not isinstance(parsed, list):
        return "JSON must be an array of objects."

    url_scheme.json_import(parsed, reveal=reveal)
    return f"Imported {len(parsed)} items via JSON."


@mcp.tool
def json_export(
    project_uuid: Annotated[
        str | None, Field(description="Export a specific project by UUID (or all open todos if omitted)")
    ] = None,
    limit: Annotated[int, Field(description="Max items to export (default: 50)")] = 50,
) -> str:
    """Export todos as JSON for backup or transfer.

    Returns compact JSON with title, uuid, status, when, deadline, tags.
    """
    if project_uuid:
        items = things.todos(project=project_uuid, include_items=True) or []
    else:
        items = things.todos(include_items=True) or []

    items = items[:limit]

    export = []
    for t in items:
        entry: dict = {"title": t.get("title"), "uuid": t.get("uuid")}
        if t.get("status"):
            entry["status"] = t["status"]
        if t.get("start_date"):
            entry["when"] = t["start_date"]
        if t.get("deadline"):
            entry["deadline"] = t["deadline"]
        if t.get("tags"):
            entry["tags"] = t["tags"]
        if t.get("notes"):
            entry["notes"] = t["notes"][:200]  # Truncate for token efficiency
        export.append(entry)

    return json.dumps(export, separators=(",", ":"))


# ===========================================================================
# Entry point
# ===========================================================================


def main():
    """Main entry point for the Things 3 MCP server."""
    if TRANSPORT == "http":
        from starlette.middleware import Middleware

        from things3_blade_mcp.auth import BearerAuthMiddleware, get_api_key, get_bearer_token

        bearer = get_bearer_token()
        api_key = get_api_key()
        logger.info("Starting HTTP transport on %s:%s", HTTP_HOST, HTTP_PORT)
        if bearer:
            logger.info("Bearer token auth enabled (THINGS_MCP_API_TOKEN is set)")
        else:
            logger.info("Bearer token auth disabled (no THINGS_MCP_API_TOKEN)")
            logger.info("API Key: %s", api_key)
        mcp.run(
            transport="http",
            host=HTTP_HOST,
            port=int(HTTP_PORT),
            middleware=[Middleware(BearerAuthMiddleware)],
        )
    else:
        mcp.run()
