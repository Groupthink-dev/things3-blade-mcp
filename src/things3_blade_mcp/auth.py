"""Authentication for HTTP transport.

Two independent auth layers:

1. **Bearer token** (remote / tunnel access):
   Set ``THINGS_MCP_API_TOKEN`` env var.  Every HTTP request must include
   ``Authorization: Bearer <token>``.  If the env var is **unset or empty**,
   bearer auth is disabled — this keeps localhost-only setups working without
   any configuration.

2. **X-API-Key** (existing, local convenience):
   Set ``THINGS_MCP_API_KEY`` env var (or let it auto-generate).  Checked via
   ``X-API-Key`` header or ``?api_key=`` query param.  Only enforced when
   bearer auth is *not* active.

Bearer auth takes precedence: when ``THINGS_MCP_API_TOKEN`` is set, only the
``Authorization: Bearer`` header is checked — X-API-Key is bypassed.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bearer token auth (THINGS_MCP_API_TOKEN)
# ---------------------------------------------------------------------------

_BEARER_TOKEN: str | None = None
_BEARER_CHECKED: bool = False


def get_bearer_token() -> str | None:
    """Return the bearer token from env, or None if not configured."""
    global _BEARER_TOKEN, _BEARER_CHECKED  # noqa: PLW0603
    if _BEARER_CHECKED:
        return _BEARER_TOKEN
    _BEARER_CHECKED = True
    token = os.environ.get("THINGS_MCP_API_TOKEN", "").strip()
    _BEARER_TOKEN = token if token else None
    return _BEARER_TOKEN


class BearerAuthMiddleware:
    """Starlette-compatible ASGI middleware that enforces Bearer token auth.

    When ``THINGS_MCP_API_TOKEN`` is set, every request must carry a matching
    ``Authorization: Bearer <token>`` header.  Requests without a valid token
    receive a ``401 Unauthorized`` JSON response.

    If the env var is unset or empty, this middleware is a transparent pass-
    through (no auth enforced).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        expected = get_bearer_token()
        if expected is None:
            # No bearer token configured — pass through
            await self.app(scope, receive, send)
            return

        # Extract Authorization header
        headers = dict(scope.get("headers", []))
        auth_value = headers.get(b"authorization", b"").decode("latin-1")

        provided = ""
        if auth_value.lower().startswith("bearer "):
            provided = auth_value[7:]

        if provided and secrets.compare_digest(provided, expected):
            await self.app(scope, receive, send)
            return

        # Reject
        body = json.dumps({"error": "Unauthorized"}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"content-length", str(len(body)).encode()],
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


# ---------------------------------------------------------------------------
# X-API-Key auth (THINGS_MCP_API_KEY) — existing mechanism
# ---------------------------------------------------------------------------

_API_KEY: str | None = None


def get_api_key() -> str:
    """Get or generate the API key for HTTP transport."""
    global _API_KEY  # noqa: PLW0603
    if _API_KEY is not None:
        return _API_KEY

    key = os.environ.get("THINGS_MCP_API_KEY")
    if key:
        _API_KEY = key
        return _API_KEY

    # Generate a strong random key
    _API_KEY = secrets.token_urlsafe(32)
    logger.warning(
        "No THINGS_MCP_API_KEY set — generated temporary key: %s\n"
        "Set THINGS_MCP_API_KEY env var to persist this key.",
        _API_KEY,
    )
    return _API_KEY


def validate_api_key(provided_key: str | None) -> bool:
    """Validate an API key against the configured key."""
    if not provided_key:
        return False
    return secrets.compare_digest(provided_key, get_api_key())
