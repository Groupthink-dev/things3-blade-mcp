"""AppleScript bridge for Things 3 write operations.

Uses temp-file approach (from rossshannon) for reliable escaping.
All writes go through AppleScript; URL scheme is the fallback.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from datetime import date, datetime

logger = logging.getLogger(__name__)


def escape_applescript_string(s: str) -> str:
    """Escape a string for safe use inside AppleScript double quotes.

    AppleScript doesn't support backslash escaping. We use string concatenation
    with `ASCII character 34` for embedded double quotes.
    """
    if not s:
        return '""'
    # Replace double quotes with AppleScript concatenation
    parts = s.split('"')
    escaped = '" & (ASCII character 34) & "'.join(parts)
    return f'"{escaped}"'


def run_applescript(script: str, timeout: int = 10) -> str:
    """Execute an AppleScript via temp file and return the result."""
    fd, path = tempfile.mkstemp(suffix=".applescript")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(script)
        result = subprocess.run(
            ["osascript", path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if result.returncode != 0:
            logger.error("AppleScript error: %s", stderr)
            raise RuntimeError(f"AppleScript failed: {stderr}")
        return stdout
    except subprocess.TimeoutExpired:
        raise RuntimeError("AppleScript timed out — is Things 3 running?")
    finally:
        os.unlink(path)


def ensure_things_ready() -> bool:
    """Check if Things 3 is running and responsive."""
    script = '''
    tell application "System Events"
        set isRunning to (exists process "Things3")
    end tell
    if isRunning then
        tell application "Things3"
            return name
        end tell
    else
        return "not running"
    end if
    '''
    try:
        result = run_applescript(script, timeout=5)
        return result != "not running"
    except RuntimeError:
        return False


def _days_from_today(date_str: str) -> int:
    """Calculate days from today to a YYYY-MM-DD date string."""
    target = datetime.strptime(date_str, "%Y-%m-%d").date()
    return (target - date.today()).days


def _build_when_script(var_name: str, when: str) -> list[str]:
    """Build AppleScript lines for scheduling a task/project."""
    when_lower = when.lower().strip()
    lines = []

    if when_lower == "today":
        lines.append(f'    move {var_name} to list "Today"')
    elif when_lower == "anytime":
        lines.append(f'    move {var_name} to list "Anytime"')
    elif when_lower == "someday":
        lines.append(f'    move {var_name} to list "Someday"')
    elif when_lower in ("tomorrow", "evening"):
        # Let Things handle these via schedule
        lines.append(f'    schedule {var_name} for "{when_lower}"')
    else:
        # Try as YYYY-MM-DD date
        try:
            days = _days_from_today(when_lower)
            if days == 0:
                lines.append(f'    move {var_name} to list "Today"')
            else:
                lines.append(
                    f"    schedule {var_name} for (current date) + {days} * days"
                )
        except ValueError:
            logger.warning("Unrecognized 'when' value: %s — skipping", when)

    return lines


def _build_deadline_script(var_name: str, deadline: str) -> list[str]:
    """Build AppleScript lines for setting a deadline."""
    try:
        days = _days_from_today(deadline)
        return [f"    set due date of {var_name} to (current date) + {days} * days"]
    except ValueError:
        logger.warning("Invalid deadline format: %s — expected YYYY-MM-DD", deadline)
        return []


def _build_tags_script(var_name: str, tags: list[str]) -> list[str]:
    """Build AppleScript lines for adding tags to a task."""
    lines = []
    for tag in tags:
        escaped = escape_applescript_string(tag)
        lines.append(f"    set tagName to {escaped}")
        lines.append('    set newTag to make new tag with properties {name:tagName}')
        lines.append(f"    add newTag to tags of {var_name}")
    return lines


def _build_list_assignment_script(
    var_name: str, list_id: str | None = None, list_title: str | None = None
) -> list[str]:
    """Build AppleScript for moving task to a project or area."""
    if not list_id and not list_title:
        return []

    target = escape_applescript_string(list_id or list_title or "")
    lines = [
        "    try",
        f"        set targetProject to first project whose id is {target}"
        if list_id
        else f"        set targetProject to first project whose name is {target}",
        f"        move {var_name} to targetProject",
        "    on error",
        "        try",
        f"            set targetArea to first area whose id is {target}"
        if list_id
        else f"            set targetArea to first area whose name is {target}",
        f"            move {var_name} to targetArea",
        "        end try",
        "    end try",
    ]
    return lines


def add_todo(
    title: str,
    notes: str | None = None,
    when: str | None = None,
    deadline: str | None = None,
    tags: list[str] | None = None,
    list_id: str | None = None,
    list_title: str | None = None,
) -> str:
    """Create a new todo in Things 3. Returns the UUID of the created todo."""
    escaped_title = escape_applescript_string(title)

    props = [f"name:{escaped_title}"]
    if notes:
        props.append(f"notes:{escape_applescript_string(notes)}")

    props_str = ", ".join(props)

    script_parts = [
        'tell application "Things3"',
        "    try",
        f"        set newTodo to make new to do with properties {{{props_str}}}",
    ]

    if when:
        script_parts.extend(_build_when_script("newTodo", when))

    if deadline:
        script_parts.extend(_build_deadline_script("newTodo", deadline))

    if tags:
        script_parts.extend(_build_tags_script("newTodo", tags))

    if list_id or list_title:
        script_parts.extend(_build_list_assignment_script("newTodo", list_id, list_title))

    script_parts.append("        return id of newTodo")
    script_parts.append("    on error errMsg")
    script_parts.append('        return "Error: " & errMsg')
    script_parts.append("    end try")
    script_parts.append("end tell")

    return run_applescript("\n".join(script_parts))


def add_project(
    title: str,
    notes: str | None = None,
    when: str | None = None,
    deadline: str | None = None,
    tags: list[str] | None = None,
    area_id: str | None = None,
    area_title: str | None = None,
    todos: list[str] | None = None,
) -> str:
    """Create a new project in Things 3. Returns the UUID."""
    escaped_title = escape_applescript_string(title)

    props = [f"name:{escaped_title}"]
    if notes:
        props.append(f"notes:{escape_applescript_string(notes)}")

    props_str = ", ".join(props)

    script_parts = [
        'tell application "Things3"',
        "    try",
        f"        set newProj to make new project with properties {{{props_str}}}",
    ]

    if when:
        script_parts.extend(_build_when_script("newProj", when))

    if deadline:
        script_parts.extend(_build_deadline_script("newProj", deadline))

    if tags:
        script_parts.extend(_build_tags_script("newProj", tags))

    if area_id or area_title:
        target = escape_applescript_string(area_id or area_title or "")
        script_parts.append("        try")
        if area_id:
            script_parts.append(
                f"            set targetArea to first area whose id is {target}"
            )
        else:
            script_parts.append(
                f"            set targetArea to first area whose name is {target}"
            )
        script_parts.append("            move newProj to targetArea")
        script_parts.append("        end try")

    # Create child todos inside the project
    if todos:
        for todo_title in todos:
            escaped = escape_applescript_string(todo_title)
            script_parts.append(
                f"        make new to do with properties {{name:{escaped}}} at beginning of to dos of newProj"
            )

    script_parts.append("        return id of newProj")
    script_parts.append("    on error errMsg")
    script_parts.append('        return "Error: " & errMsg')
    script_parts.append("    end try")
    script_parts.append("end tell")

    return run_applescript("\n".join(script_parts))


def update_todo(
    todo_id: str,
    title: str | None = None,
    notes: str | None = None,
    when: str | None = None,
    deadline: str | None = None,
    tags: list[str] | None = None,
    completed: bool | None = None,
    canceled: bool | None = None,
    list_id: str | None = None,
    list_name: str | None = None,
) -> str:
    """Update an existing todo in Things 3."""
    escaped_id = escape_applescript_string(todo_id)

    script_parts = [
        'tell application "Things3"',
        "    try",
        f"        set theTodo to to do id {escaped_id}",
    ]

    if title:
        script_parts.append(f"        set name of theTodo to {escape_applescript_string(title)}")

    if notes is not None:
        script_parts.append(
            f"        set notes of theTodo to {escape_applescript_string(notes)}"
        )

    if when:
        script_parts.extend(_build_when_script("theTodo", when))

    if deadline:
        script_parts.extend(_build_deadline_script("theTodo", deadline))

    if tags:
        script_parts.extend(_build_tags_script("theTodo", tags))

    if list_id or list_name:
        script_parts.extend(_build_list_assignment_script("theTodo", list_id, list_name))

    if completed is True:
        script_parts.append("        set status of theTodo to completed")
    elif completed is False:
        script_parts.append("        set status of theTodo to open")

    if canceled is True:
        script_parts.append("        set status of theTodo to canceled")
    elif canceled is False and completed is not True:
        script_parts.append("        set status of theTodo to open")

    script_parts.append('        return "OK"')
    script_parts.append("    on error errMsg")
    script_parts.append('        return "Error: " & errMsg')
    script_parts.append("    end try")
    script_parts.append("end tell")

    return run_applescript("\n".join(script_parts))


def update_project(
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
    """Update an existing project in Things 3."""
    escaped_id = escape_applescript_string(project_id)

    script_parts = [
        'tell application "Things3"',
        "    try",
        f"        set theProj to project id {escaped_id}",
    ]

    if title:
        script_parts.append(f"        set name of theProj to {escape_applescript_string(title)}")

    if notes is not None:
        script_parts.append(
            f"        set notes of theProj to {escape_applescript_string(notes)}"
        )

    if when:
        script_parts.extend(_build_when_script("theProj", when))

    if deadline:
        script_parts.extend(_build_deadline_script("theProj", deadline))

    if tags:
        script_parts.extend(_build_tags_script("theProj", tags))

    if area_id or area_title:
        target = escape_applescript_string(area_id or area_title or "")
        script_parts.append("        try")
        if area_id:
            script_parts.append(
                f"            set targetArea to first area whose id is {target}"
            )
        else:
            script_parts.append(
                f"            set targetArea to first area whose name is {target}"
            )
        script_parts.append("            move theProj to targetArea")
        script_parts.append("        end try")

    if completed is True:
        script_parts.append("        set status of theProj to completed")
    elif completed is False:
        script_parts.append("        set status of theProj to open")

    if canceled is True:
        script_parts.append("        set status of theProj to canceled")
    elif canceled is False and completed is not True:
        script_parts.append("        set status of theProj to open")

    script_parts.append('        return "OK"')
    script_parts.append("    on error errMsg")
    script_parts.append('        return "Error: " & errMsg')
    script_parts.append("    end try")
    script_parts.append("end tell")

    return run_applescript("\n".join(script_parts))


def show_in_things(item_id: str) -> str:
    """Reveal an item in Things 3 UI."""
    escaped_id = escape_applescript_string(item_id)
    script = f'''
    tell application "Things3"
        show to do id {escaped_id}
        activate
    end tell
    '''
    try:
        run_applescript(script)
        return "OK"
    except RuntimeError:
        # Try as project
        script = f'''
        tell application "Things3"
            show project id {escaped_id}
            activate
        end tell
        '''
        try:
            run_applescript(script)
            return "OK"
        except RuntimeError as e:
            return f"Error: {e}"
