---
name: things3-task-management
description: >
  Manages Things 3 tasks, projects, areas, and tags via MCP tools.
  Use when user mentions 'tasks', 'todos', 'Things', 'Things 3', 'inbox',
  'today list', 'upcoming', 'someday', 'project planning', 'weekly review',
  'daily review', 'task management', 'schedule tasks', 'deadlines',
  'GTD', 'getting things done', or asks to organize, create, update,
  complete, or track work items.
---

# Things 3 MCP Server

Interact with the Things 3 task manager. Read, create, update, and organize
todos, projects, areas, and tags.

## Token Efficiency Rules (MANDATORY)

Follow these rules on EVERY interaction to minimize context usage:

1. **Always start with `get_summary`** — gives full GTD overview in ~20 lines
2. **Use `concise=True` (default)** — never set `concise=False` unless user asks for details
3. **Use `get_random_*` before full lists** — `get_random_inbox(5)` not `get_inbox(limit=100)`
4. **Keep `limit=10` (default)** — only increase when user explicitly needs more
5. **Use `show_item(uuid)` for single-item details** — don't re-fetch entire lists
6. **Use `search_todos` to find specific items** — don't scan full lists manually
7. **Chain tools in this order**: summary → random sample → targeted detail → action

## Quick Start — 5 Most Common Operations

### Check what's on your plate
```
get_summary()
```

### See today's tasks
```
get_today()  # concise=True, limit=10 by default
```

### Create a task
```
add_todo(title="Buy groceries", when="today", tags=["errands"])
```
Dedup is on by default — if an open todo with a similar title exists, the
existing task is returned instead of creating a duplicate. Pass
`deduplicate=false` only when you are certain the task is new.

### Find and update a task
```
search_todos(query="groceries")  → get UUID
update_todo(todo_id="<uuid>", completed=True)
```

### Review inbox in batches
```
get_random_inbox(count=5)  # manageable batch for processing
```

## Workflows

### Daily Review (Morning)
1. `get_summary()` — see counts across all lists
2. `get_today()` — what's already scheduled
3. `get_random_inbox(5)` — process 5 inbox items
4. For each: `update_todo(id, when="today")` or `update_todo(id, when="someday")`
5. `get_deadlines()` — check upcoming due dates

### Project Creation
1. `get_areas()` — find the right area
2. `add_project(title="...", area_title="...", todos=["task1", "task2", "task3"])`
3. `show_item(uuid)` — verify the created project

### Weekly Review
1. `get_summary()` — big picture
2. `get_logbook(period="7d")` — what was completed this week
3. `get_random_anytime(10)` — review available tasks
4. `get_someday()` — any Someday items to activate?
5. `get_deadlines()` — upcoming commitments

### Bulk Import
```
json_import(data='[{"type":"to-do","attributes":{"title":"Task 1","when":"today"}},...]')
```

### Task Enrichment (LLM Workflow)
1. `get_random_todos(count=5)` — sample a batch
2. Review titles, suggest improvements
3. `update_todo(id, title="...", notes="...")` — enhance each one

## Natural Language → Tool Mapping

| User says | Tool call |
|---|---|
| "What's on my plate?" | `get_summary()` |
| "Show my tasks for today" | `get_today()` |
| "What's in my inbox?" | `get_random_inbox(5)` then `get_inbox()` if needed |
| "Create a task to..." | `add_todo(title="...", ...)` |
| "Schedule X for tomorrow" | `update_todo(id, when="tomorrow")` |
| "Mark X as done" | `update_todo(id, completed=True)` |
| "Show my projects" | `get_projects()` |
| "What's due this week?" | `get_deadlines()` |
| "Find my task about..." | `search_todos(query="...")` |
| "Move X to Someday" | `update_todo(id, when="someday")` |
| "Show me task details" | `show_item(uuid, include_details=True)` |
| "Export my tasks" | `json_export()` |

## Tool Categories

### Read Tools (token-efficient by default)
- **List views**: `get_inbox`, `get_today`, `get_upcoming`, `get_anytime`, `get_someday`, `get_logbook`, `get_trash`, `get_deadlines`
- **Sampling**: `get_random_inbox`, `get_random_today`, `get_random_anytime`, `get_random_todos`
- **Entities**: `get_todos`, `get_projects`, `get_areas`, `get_tags`, `get_tagged_items`
- **Search**: `search_todos`, `search_advanced`, `get_recent`
- **Detail**: `show_item`
- **Overview**: `get_summary`

### Write Tools
- **Create**: `add_todo`, `add_project`
- **Update**: `update_todo`, `update_project`
- **Bulk**: `json_import`, `json_export`
- **Navigate**: `show_in_things`, `search_in_things`

## Common Parameters

All read tools support:
- `concise=True` (default) — one-line output
- `limit=10` (default) — cap on returned items
- `include_details=False` (default) — full info when needed

## Subtasks / Checklists

Things 3 checklists cannot be created via AppleScript. Two workarounds:

1. **URL scheme** (real checklist items):
   ```
   add_todo(title="...", checklist_items=["Step 1", "Step 2", "Step 3"])
   ```

2. **Markdown in notes** (rendered as checkboxes in Things):
   ```
   add_todo(title="...", notes="- [ ] Step 1\n- [ ] Step 2\n- [x] Step 3")
   ```

## Scheduling Values

The `when` parameter accepts:
- `today`, `tomorrow`, `evening`, `anytime`, `someday`
- Date: `2026-03-15` (YYYY-MM-DD)

## Troubleshooting

| Issue | Solution |
|---|---|
| "AppleScript failed" | Ensure Things 3 is running on macOS |
| "No auth token" | Set `THINGS_AUTH_TOKEN` env var or enable in Things > Settings > General |
| Empty results | Check if items exist in Things UI; try broader search |
| "unable to open database" | Things 3 must be installed; check `~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/` |
| Someday tasks in Today | This is a filtering bug — report it; the server handles Someday filtering correctly |

## References

For deep dives, see the `references/` folder:
- `references/tool-reference.md` — complete parameter docs for all tools
- `references/workflows.md` — extended workflow patterns
- `references/url-scheme.md` — Things URL scheme reference
