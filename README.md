# Things 3 MCP Server

Best-in-class [MCP](https://modelcontextprotocol.io) server for [Things 3](https://culturedcode.com/things/) — token-efficient, full CRUD, AppleScript + URL scheme.

Built to be the most capable and efficient Things integration for Claude Desktop, Claude Code, and any MCP-compatible client.

## Features

- **Token-efficient output** — concise one-line-per-item by default, detailed on demand
- **30+ tools** — full coverage of every Things 3 view and operation
- **Smart Someday filtering** — correctly handles inherited Someday status (matches Things UI exactly)
- **Random sampling** — `get_random_inbox(5)` for manageable LLM context instead of dumping hundreds of items
- **Summary mode** — full GTD overview (`get_summary`) in ~20 lines
- **AppleScript + URL scheme** — reliable writes with UUID feedback; automatic fallback
- **Bulk JSON import/export** — Things URL scheme JSON format
- **HTTP transport** — optional remote access with API key authentication
- **SKILL.md** — self-teaching instructions so Claude uses tools optimally

## Requirements

- **macOS** (Things 3 is macOS/iOS only)
- **Things 3** installed and running
- **Python 3.12+**
- **uv** (recommended) or pip

## Quick Start

### Install and run

```bash
# Clone and install
git clone https://github.com/Groupthink-dev/things3-blade-mcp.git
cd things3-blade-mcp
uv sync

# Run (stdio transport — for Claude Desktop)
uv run things3-blade-mcp
```

### Claude Desktop configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "things3": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/things3-blade-mcp", "things3-blade-mcp"]
    }
  }
}
```

### Claude Code

```bash
# Add as MCP server
claude mcp add things3 -- uv run --directory /path/to/things3-blade-mcp things3-blade-mcp
```

## Token-Saving Tips

The server is designed to minimize LLM context consumption:

1. **Start with `get_summary()`** — 20-line GTD overview, not hundreds of tasks
2. **Use random sampling** — `get_random_inbox(5)` before `get_inbox(limit=100)`
3. **Defaults are efficient** — `concise=True`, `limit=10` on all tools
4. **One-line format**: `□ Buy groceries [3F8A2B1C] | today | deadline:2026-03-01 | #errands`
5. **Null fields omitted** — no "Notes: None" or "Tags: []" clutter
6. **Batch lookups** — no N+1 queries; project/area names resolved in bulk

## All Tools (30)

### List Views (9)
| Tool | Description |
|---|---|
| `get_inbox` | Unprocessed tasks |
| `get_today` | Today's schedule (Someday-filtered) |
| `get_upcoming` | Future scheduled tasks |
| `get_anytime` | Available tasks |
| `get_someday` | Deferred tasks (includes inherited) |
| `get_logbook` | Completed tasks (configurable period) |
| `get_trash` | Trashed tasks |
| `get_deadlines` | All tasks with deadlines, sorted |
| `get_summary` | Full GTD overview in ~20 lines |

### Random Sampling (4) — recommended entry points
| Tool | Description |
|---|---|
| `get_random_inbox` | Random sample from inbox |
| `get_random_today` | Random sample from today |
| `get_random_anytime` | Random sample from anytime |
| `get_random_todos` | Random sample, optional project filter |

### Entity Views (5)
| Tool | Description |
|---|---|
| `get_todos` | All open todos (optional project filter) |
| `get_projects` | Projects with open/done counts |
| `get_areas` | High-level categories |
| `get_tags` | All tags |
| `get_tagged_items` | Todos with a specific tag |

### Search & Detail (4)
| Tool | Description |
|---|---|
| `search_todos` | Search by title/notes |
| `search_advanced` | Multi-filter search (status, date, tag, area) |
| `get_recent` | Recently created items |
| `show_item` | Single item by UUID with full details |

### Write (4) — AppleScript primary, URL scheme fallback
| Tool | Description |
|---|---|
| `add_todo` | Create a todo (returns UUID) |
| `add_project` | Create a project with optional todos |
| `update_todo` | Update any todo field |
| `update_project` | Update any project field |

### Bulk & Navigation (4)
| Tool | Description |
|---|---|
| `json_import` | Bulk create via Things JSON format |
| `json_export` | Export todos as compact JSON |
| `show_in_things` | Reveal item in Things app |
| `search_in_things` | Open Things search UI |

## HTTP Transport

For remote access (e.g., from a different machine or mobile):

```bash
# Set environment variables
export THINGS_MCP_TRANSPORT=http
export THINGS_MCP_HOST=127.0.0.1
export THINGS_MCP_PORT=8765
export THINGS_MCP_API_KEY=your-secret-key-here  # auto-generated if empty

# Run
uv run things3-blade-mcp
```

### Bearer Token Authentication

When exposing the server through a tunnel or reverse proxy, set `THINGS_MCP_API_TOKEN` to require a bearer token on every request:

```bash
export THINGS_MCP_API_TOKEN=your-secret-token-here
```

All HTTP requests must then include the header:

```
Authorization: Bearer your-secret-token-here
```

Requests without a valid token receive `401 Unauthorized`. If the env var is **unset or empty**, bearer auth is disabled and the server behaves as before (suitable for localhost-only access).

### Security Warning

**Never expose the HTTP port directly to the internet.** Use a reverse proxy with TLS:

- [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) (recommended — free, zero-config TLS)
- Caddy (automatic HTTPS)
- Nginx with Let's Encrypt

#### Cloudflare Tunnel example

```bash
# Install cloudflared
brew install cloudflare/cloudflare/cloudflared

# Create tunnel
cloudflared tunnel create things-mcp
cloudflared tunnel route dns things-mcp things-mcp.yourdomain.com

# Run tunnel
cloudflared tunnel --url http://localhost:8765 run things-mcp
```

### Testing the HTTP endpoint

```bash
# Health check
curl http://localhost:8765/

# Call a tool (via MCP protocol)
curl -X POST http://localhost:8765/mcp \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key-here" \
  -d '{"method": "tools/call", "params": {"name": "get_summary", "arguments": {}}}'
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `THINGS_MCP_TRANSPORT` | `stdio` | `stdio` or `http` |
| `THINGS_MCP_HOST` | `127.0.0.1` | HTTP bind address |
| `THINGS_MCP_PORT` | `8765` | HTTP port |
| `THINGS_MCP_API_TOKEN` | (none) | Bearer token for HTTP auth — if set, requires `Authorization: Bearer <token>` |
| `THINGS_MCP_API_KEY` | (auto) | API key for HTTP auth (X-API-Key header) |
| `THINGS_AUTH_TOKEN` | (auto) | Things URL scheme auth token |

## Architecture

```
src/things3_blade_mcp/
├── server.py       # FastMCP instance + all 30 @mcp.tool definitions
├── formatters.py   # Two-tier output: concise (1-line) + detailed
├── someday.py      # Someday filtering (matches Things UI behavior)
├── applescript.py   # AppleScript bridge for writes (temp-file approach)
├── url_scheme.py   # URL scheme builder (fallback writes + checklist items)
├── sampling.py     # Random sampling helpers
├── auth.py         # API key auth for HTTP transport
└── models.py       # Shared constants
```

**Design principles:**
- **Reads** via `things.py` (direct SQLite — fast, no app needed)
- **Writes** via AppleScript (reliable, returns UUIDs, no auth token needed)
- **Fallback writes** via URL scheme (for checklist items or when AppleScript fails)
- **Batch lookups** eliminate N+1 queries in formatters
- **Someday filtering** handles the Things 3 project-inheritance edge case

## Development

```bash
# Install with dev/test dependencies
uv sync --all-extras

# Run tests
uv run pytest tests/ -v

# Lint
uv run ruff check src/ tests/
```

## License

MIT
